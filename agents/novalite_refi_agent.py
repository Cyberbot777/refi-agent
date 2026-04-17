"""
Nova Lite Fine-Tuned Refinance Agent

Uses a fine-tuned Amazon Nova Lite model for FHA Streamline / VA IRRRL
underwriting decisions. Single inference call — no agent loop or tool-calling.

Compared to the Claude Sonnet agent (claude_refi_agent.py):
- ~5-7s latency vs ~29s (no tool round-trips)
- 900-char system prompt vs 6K (rules baked into model weights)
- 87.1% accuracy vs 100% (AWC boundary is the gap)
"""

import json
import re
import time

import boto3

from tools.refi_database_tools import get_all_loan_data, save_decision

# ─── CONFIG ─────────────────────────────────────────────────────────────────────

DEPLOYMENT_ARN = "arn:aws:bedrock:us-east-1:025066260073:custom-model-deployment/7z30sv84mnyu"
REGION = "us-east-1"

SYSTEM_PROMPT = (
    "You are an FHA Streamline / VA IRRRL underwriting assistant. "
    "Evaluate loan applications and output a structured decision report.\n\n"
    "DECISION PRIORITY (apply in this order):\n"
    "1. DENIED: Any required check fails. Non-CURRENT loan status "
    "(PENDING, DELINQUENT, FORBEARANCE) is always an immediate DENY. "
    "A value that does not meet its threshold is a FAIL — never call it an edge case.\n"
    "2. NEEDS REVIEW: VA only — all C1-C4 checks pass but monthly PITI "
    "increases by 20% or more (C5 trigger). This is NOT a denial.\n"
    "3. APPROVED WITH CONDITIONS: ALL checks pass, but one or more edge-case "
    "flags triggered. Edge cases mean the value PASSES its threshold but is "
    "close to the boundary. Examples: cash $400-$500 (passes the $500 limit "
    "but barely), 1x 30-day late (within the 1 allowed), NTB margin < 0.400% "
    "above minimum, recoupment 28-36 months (passes the 36-month limit but "
    "tight), rate reduction within 0.050% above the required minimum.\n"
    "4. APPROVED: All checks pass, no edge-case flags.\n\n"
    "CRITICAL: A check that FAILS cannot be an edge case. Rate reduction "
    "0.125% when the threshold is 0.500% is a FAIL (DENIED), not an edge case. "
    "Recoupment of 40 months when the limit is 36 is a FAIL (DENIED), not an "
    "edge case. Only values that PASS but are near the boundary trigger "
    "APPROVED WITH CONDITIONS.\n\n"
    "Key thresholds:\n"
    "- Seasoning: >= 210 days since closing, >= 6 months since first payment, "
    ">= 6 payments made.\n"
    "- FHA NTB: combined rate reduction >= 0.250% (note rate + annual MIP).\n"
    "- VA Fixed-to-Fixed: rate reduction >= 0.500%. Fixed-to-ARM: >= 2.000%. "
    "ARM-to-Fixed: auto-pass.\n"
    "- VA recoupment: recoupable costs / monthly P&I savings <= 36 months.\n"
    "- FHA cash to borrower: <= $500. VA cash to borrower: $0.\n"
    "- Payment history: <= 1x 30-day late, 0x 60+ day late (FHA). "
    "6 consecutive on-time (VA)."
)


# DATA FORMATTING

def format_loan_for_model(loan_json: str) -> str:
    """
    Format DB loan data into the structured text the fine-tuned model expects.
    Matches the exact template used during training data generation.
    """
    data = json.loads(loan_json)

    if "error" in data:
        return None

    app = data["application"]
    ph = data["payment_history"]

    program = "FHA" if app.get("fha_case_number") else "VA"
    program_label = "FHA Streamline" if program == "FHA" else "VA IRRRL"

    lines = [
        f"Analyze the following {program_label} refinance application "
        f"and provide your underwriting decision.",
        "",
        f"Borrower: {app['borrower_name']}",
        f"Property: {app['property_address']}",
        f"Program: {program}{' Streamline Refinance' if program == 'FHA' else ' IRRRL'}",
    ]

    if program == "FHA":
        lines.append(f"FHA Case Number: {app.get('fha_case_number') or 'MISSING'}")
    else:
        lines.append(f"VA Loan Number: {app.get('va_loan_number') or 'MISSING'}")

    lines.extend([
        f"Loan Status: {app['loan_status']}",
        f"Original Closing Date: {app['original_closing_date']}",
        f"First Payment Due Date: {app['first_payment_due_date']}",
        "",
        "Current Loan:",
        f"- Note Rate: {float(app['current_note_rate']):.3f}%",
    ])

    if program == "FHA":
        lines.append(f"- Annual MIP: {float(app['current_annual_mip']):.3f}%")

    lines.extend([
        f"- Monthly P&I: ${float(app['current_monthly_pi']):.2f}",
        f"- Monthly PITI: ${float(app['current_monthly_piti']):.2f}",
        f"- Loan Balance: ${float(app['current_loan_balance']):.2f}",
    ])

    if program == "VA":
        lines.append(f"- Rate Type: {app.get('rate_type_current', 'FIXED')}")

    lines.extend([
        "",
        "New Loan:",
        f"- Note Rate: {float(app['new_note_rate']):.3f}%",
    ])

    if program == "FHA":
        lines.append(f"- Annual MIP: {float(app['new_annual_mip']):.3f}%")

    lines.extend([
        f"- Monthly P&I: ${float(app['new_monthly_pi']):.2f}",
        f"- Monthly PITI: ${float(app['new_monthly_piti']):.2f}",
        f"- Loan Amount: ${float(app['new_loan_amount']):.2f}",
    ])

    if program == "VA":
        lines.append(f"- Rate Type: {app.get('rate_type_new', 'FIXED')}")

    if program == "VA":
        lines.extend([
            "",
            "Closing Costs:",
            f"- Total Closing Costs: ${float(app['total_closing_costs']):.2f}",
            f"- VA Funding Fee: ${float(app['va_funding_fee']):.2f}",
            f"- Taxes: ${float(app['taxes_amount']):.2f}",
            f"- Escrow Deposits: ${float(app['escrow_deposits']):.2f}",
        ])

    lines.extend([
        "",
        f"Cash to Borrower: ${float(app['cash_to_borrower']):.2f}",
        "",
        "Payment History (Last 12 Months):",
        f"- Total Payments: {ph['total_payments']}",
        f"- 30-Day Lates: {ph['late_30_day']}",
        f"- 60+ Day Lates: {ph['late_60_plus']}",
        f"- Consecutive On-Time: {ph['consecutive_on_time']}",
    ])

    return "\n".join(lines)


# INFERENCE

def call_model(user_text: str) -> str:
    """Single inference call to the fine-tuned Nova Lite model."""
    client = boto3.client("bedrock-runtime", region_name=REGION)
    resp = client.converse(
        modelId=DEPLOYMENT_ARN,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": user_text}]}],
        inferenceConfig={"temperature": 0.0, "maxTokens": 2048},
    )
    return resp["output"]["message"]["content"][0]["text"]


def extract_decision(text: str) -> str:
    """Parse the decision from model output."""
    for line in text.split("\n"):
        upper = line.upper().strip()
        if "DECISION" not in upper:
            continue
        if "APPROVED WITH CONDITIONS" in upper:
            return "APPROVED WITH CONDITIONS"
        if "NEEDS REVIEW" in upper:
            return "NEEDS REVIEW"
        if "DENIED" in upper:
            return "DENIED"
        if "APPROVED" in upper:
            return "APPROVED"
    return "UNKNOWN"


# MAIN

def process_application(refi_id: str) -> str:
    """
    Process a refinance application using the fine-tuned Nova Lite model.

    1. Fetch loan data from DB
    2. Format as structured text (matches training format)
    3. Single inference call to fine-tuned model
    4. Parse decision and record to DB

    Returns the model's underwriting report.
    """
    # Fetch data
    loan_json = get_all_loan_data(refi_id)
    user_text = format_loan_for_model(loan_json)

    if user_text is None:
        return f"Error: No application found with ID: {refi_id}"

    # Single inference call
    start = time.time()
    report = call_model(user_text)
    elapsed = time.time() - start

    # Parse and record decision
    decision = extract_decision(report)
    if decision != "UNKNOWN":
        save_decision(refi_id, decision, f"Nova Lite v2 automated decision ({elapsed:.1f}s)")

    return report


if __name__ == "__main__":
    import sys

    refi_id = sys.argv[1] if len(sys.argv) > 1 else "REFI-FHA-001"

    print(f"\n{'='*60}")
    print(f"Processing: {refi_id} (Nova Lite Fine-Tuned)")
    print(f"{'='*60}\n")

    start = time.time()
    result = process_application(refi_id)
    elapsed = time.time() - start

    print(result)
    print(f"\n{'='*60}")
    print(f"Completed in {elapsed:.1f}s")
    print(f"{'='*60}")
