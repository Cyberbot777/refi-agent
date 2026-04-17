#!/usr/bin/env python3
"""
Held-out evaluation runner for the fine-tuned Nova Lite agent.

Runs 20 hand-crafted scenarios from heldout_eval_cases.json that were
NEVER seen in training data. This tests true generalization, not memorization.

Usage:
    python tests/heldout_test_agent.py [--verbose]
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import boto3

# ─── Import model config and inference from the Nova Lite agent ─────────────

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.novalite_refi_agent import (
    DEPLOYMENT_ARN,
    REGION,
    SYSTEM_PROMPT,
    call_model,
    extract_decision,
)

HELDOUT_CASES = Path(__file__).resolve().parent / "heldout_eval_cases.json"


# ─── FORMAT SCENARIO TO MATCH TRAINING INPUT FORMAT ─────────────────────────

def format_scenario_for_model(scenario: dict, eval_date: str) -> str:
    """
    Convert a heldout scenario dict into the exact text format
    the fine-tuned model was trained on.
    """
    program = scenario["program"]
    program_label = "FHA Streamline" if program == "FHA" else "VA IRRRL"

    lines = [
        f"Analyze the following {program_label} refinance application "
        f"and provide your underwriting decision.",
        "",
        f"Borrower: {scenario['borrower_name']}",
        f"Property: {scenario['property_address']}",
        f"Program: {program}{' Streamline Refinance' if program == 'FHA' else ' IRRRL'}",
    ]

    if program == "FHA":
        lines.append(f"FHA Case Number: {scenario.get('fha_case_number', 'MISSING')}")
    else:
        lines.append(f"VA Loan Number: {scenario.get('va_loan_number', 'MISSING')}")

    lines.extend([
        f"Loan Status: {scenario['loan_status']}",
        f"Original Closing Date: {scenario['closing_date']}",
        f"First Payment Due Date: {scenario['first_payment_date']}",
        "",
        "Current Loan:",
        f"- Note Rate: {float(scenario['current_note_rate']):.3f}%",
    ])

    if program == "FHA":
        lines.append(f"- Annual MIP: {float(scenario['current_annual_mip']):.3f}%")

    lines.extend([
        f"- Monthly P&I: ${float(scenario['current_monthly_pi']):.2f}",
        f"- Monthly PITI: ${float(scenario['current_monthly_piti']):.2f}",
        f"- Loan Balance: ${float(scenario['current_loan_balance']):.2f}",
    ])

    if program == "VA":
        lines.append(f"- Rate Type: {scenario.get('rate_type_current', 'FIXED')}")

    lines.extend([
        "",
        "New Loan:",
        f"- Note Rate: {float(scenario['new_note_rate']):.3f}%",
    ])

    if program == "FHA":
        lines.append(f"- Annual MIP: {float(scenario['new_annual_mip']):.3f}%")

    lines.extend([
        f"- Monthly P&I: ${float(scenario['new_monthly_pi']):.2f}",
        f"- Monthly PITI: ${float(scenario['new_monthly_piti']):.2f}",
        f"- Loan Amount: ${float(scenario['new_loan_amount']):.2f}",
    ])

    if program == "VA":
        lines.append(f"- Rate Type: {scenario.get('rate_type_new', 'FIXED')}")

    if program == "VA":
        lines.extend([
            "",
            "Closing Costs:",
            f"- Total Closing Costs: ${float(scenario['total_closing_costs']):.2f}",
            f"- VA Funding Fee: ${float(scenario['va_funding_fee']):.2f}",
            f"- Taxes: ${float(scenario['taxes_amount']):.2f}",
            f"- Escrow Deposits: ${float(scenario['escrow_deposits']):.2f}",
        ])

    lines.extend([
        "",
        f"Cash to Borrower: ${float(scenario['cash_to_borrower']):.2f}",
        "",
        "Payment History (Last 12 Months):",
        f"- Total Payments: {scenario['total_payments']}",
        f"- 30-Day Lates: {scenario.get('late_30_day', 0)}",
        f"- 60+ Day Lates: {scenario.get('late_60_plus', 0)}",
        f"- Consecutive On-Time: {scenario['consecutive_on_time']}",
    ])

    return "\n".join(lines)


# ─── NORMALIZE DECISIONS FOR COMPARISON ─────────────────────────────────────

def normalize_decision(dec: str) -> str:
    """Normalize decision strings for comparison."""
    dec = dec.upper().strip()
    if "APPROVED WITH CONDITIONS" in dec:
        return "AWC"
    if "NEEDS REVIEW" in dec or "NEEDS_REVIEW" in dec:
        return "NEEDS_REVIEW"
    if "DENIED" in dec:
        return "DENIED"
    if "APPROVED" in dec:
        return "APPROVED"
    return "UNKNOWN"


# ─── MAIN ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run held-out eval cases against Nova Lite")
    parser.add_argument("--verbose", action="store_true", help="Print full model output on failures")
    args = parser.parse_args()

    with open(HELDOUT_CASES) as f:
        data = json.load(f)

    eval_date = data["eval_date"]
    cases = data["cases"]

    print(f"\n{'='*70}")
    print(f"  HELD-OUT EVALUATION — Nova Lite Fine-Tuned")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Model: {DEPLOYMENT_ARN.split('/')[-1]}")
    print(f"  Eval date: {eval_date}")
    print(f"  Cases: {len(cases)} (never seen in training)")
    print(f"{'='*70}\n")

    results = []

    for i, case in enumerate(cases):
        case_id = case["id"]
        expected_raw = case["expected_decision"]
        expected = normalize_decision(expected_raw)
        description = case["description"]

        print(f"  [{i+1:2d}/{len(cases)}] {case_id:20s} ", end="", flush=True)

        try:
            user_text = format_scenario_for_model(case["scenario"], eval_date)
            start = time.time()
            output = call_model(user_text)
            elapsed = time.time() - start

            actual_raw = extract_decision(output)
            actual = normalize_decision(actual_raw)

            correct = actual == expected
            results.append({
                "id": case_id,
                "description": description,
                "expected": expected,
                "actual": actual,
                "correct": correct,
                "time_sec": round(elapsed, 1),
            })

            tag = "OK" if correct else "X "
            print(f"{tag}  expected={expected:12s} got={actual:12s} ({elapsed:.1f}s)")

            if not correct and args.verbose:
                print(f"         Description: {description}")
                print(f"         Model output:")
                for line in output.split("\n")[:10]:
                    print(f"           {line}")
                print()

        except Exception as e:
            results.append({
                "id": case_id,
                "description": description,
                "expected": expected,
                "actual": "ERROR",
                "correct": False,
                "time_sec": 0,
            })
            print(f"ERROR  {e}")

    # ─── SUMMARY ────────────────────────────────────────────────────────

    correct_count = sum(1 for r in results if r["correct"])
    total = len(results)
    accuracy = (correct_count / total * 100) if total > 0 else 0
    total_time = sum(r["time_sec"] for r in results)

    # Per-category breakdown
    categories = {}
    for r in results:
        cat = r["expected"]
        categories.setdefault(cat, {"correct": 0, "total": 0})
        categories[cat]["total"] += 1
        if r["correct"]:
            categories[cat]["correct"] += 1

    print(f"\n{'='*70}")
    print(f"  RESULTS: {correct_count}/{total} ({accuracy:.1f}%)")
    print(f"  Total time: {total_time:.1f}s ({total_time/total:.1f}s avg)")
    print(f"{'='*70}")

    print(f"\n  Per-Category Breakdown:")
    for cat in ["APPROVED", "AWC", "DENIED", "NEEDS_REVIEW"]:
        if cat in categories:
            c = categories[cat]
            pct = c["correct"] / c["total"] * 100
            print(f"    {cat:15s}: {c['correct']}/{c['total']} ({pct:.0f}%)")

    # Show failures
    failures = [r for r in results if not r["correct"]]
    if failures:
        print(f"\n  Failures:")
        for f in failures:
            print(f"    {f['id']:20s} expected={f['expected']:12s} got={f['actual']:12s} — {f['description']}")

    print()
    return 0 if accuracy == 100.0 else 1


if __name__ == "__main__":
    sys.exit(main())
