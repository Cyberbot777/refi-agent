#!/usr/bin/env python3
"""
Test Claude Sonnet against training data to measure accuracy.

Injects the correct evaluation date (2026-02-10) to match the
training data's eval_date, since seasoning calculations are date-dependent.

Usage:
    python tests/accuracy_test_harness.py [--samples N] [--verbose]
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path

import boto3

# ─── CONFIG ─────────────────────────────────────────────────────────────────────

CLAUDE_MODEL = "us.anthropic.claude-sonnet-4-20250514-v1:0"
TRAINING_DATA = "data/nova/refi_training_v7_nova_lite.jsonl"
EVAL_DATE = "2026-02-10"  # Must match scenarios.py EVAL_DATE

# Extract SYSTEM_PROMPT from claude_refi_agent.py without importing (avoids psycopg2)
_agent_src = Path("agents/claude_refi_agent.py").read_text()
_start = _agent_src.index('SYSTEM_PROMPT = """') + len('SYSTEM_PROMPT = """')
_end = _agent_src.index('"""', _start)
_raw_prompt = _agent_src[_start:_end]

# Strip tool references for standalone testing (no agent runtime)
# Replace the process section that mentions tools
_raw_prompt = _raw_prompt.replace(
    """## Your Process
1. Get the loan data using the get_loan_data tool
2. Determine if this is FHA or VA based on the existing_loan_type field
3. Check each applicable rule below
4. Calculate any required values (NTB, seasoning, recoupment)
5. Make a decision: APPROVED, APPROVED WITH CONDITIONS, DENIED, or NEEDS REVIEW
6. Record your decision using the record_decision tool""",
    """## Your Process
1. Analyze the loan data provided in the user message
2. Determine if this is FHA or VA based on the program type
3. Check each applicable rule below
4. Calculate any required values (NTB, seasoning, recoupment)
5. Make a decision: APPROVED, APPROVED WITH CONDITIONS, DENIED, or NEEDS REVIEW"""
)
SYSTEM_PROMPT = _raw_prompt

# Prepend the evaluation date so Claude knows "today"
SYSTEM_PROMPT_WITH_DATE = f"Today's date is {EVAL_DATE}.\n\n" + SYSTEM_PROMPT


# ─── HELPERS ────────────────────────────────────────────────────────────────────

def load_and_classify_records(path: str) -> dict[str, list]:
    """Load training data and group records by expected decision category."""
    with open(path) as f:
        records = [json.loads(line) for line in f]

    groups: dict[str, list] = {}
    for i, r in enumerate(records):
        user = r["messages"][0]["content"][0]["text"]
        asst = r["messages"][1]["content"][0]["text"]

        if "Loan Status: PENDING" in user:
            cat = "PENDING"
        elif "Loan Status: DELINQUENT" in user:
            cat = "DELINQUENT"
        elif "Loan Status: FORBEARANCE" in user:
            cat = "FORBEARANCE"
        elif "APPROVED WITH CONDITIONS" in asst:
            cat = "AWC"
        elif "NEEDS REVIEW" in asst:
            cat = "NEEDS_REVIEW"
        elif "**DECISION: APPROVED**" in asst and "CURRENT" in user:
            cat = "APPROVED"
        elif "**DECISION: DENIED**" in asst and "CURRENT" in user:
            cat = "DENIED_OTHER"
        else:
            cat = "UNKNOWN"
        groups.setdefault(cat, []).append((i, r))

    return groups


def extract_decision(text: str) -> str:
    """Extract decision from model output, handling any format."""
    # First: look for a DECISION line
    for line in text.split("\n"):
        lu = line.upper().strip()
        if "DECISION" not in lu:
            continue
        if "APPROVED WITH CONDITIONS" in lu:
            return "AWC"
        if "NEEDS REVIEW" in lu or "NEEDS_REVIEW" in lu:
            return "NEEDS_REVIEW"
        if "DENIED" in lu:
            return "DENIED"
        if "APPROVED" in lu:
            return "APPROVED"

    # Fallback: search full text
    upper = text.upper()
    if "APPROVED WITH CONDITIONS" in upper:
        return "AWC"
    if "NEEDS REVIEW" in upper:
        return "NEEDS_REVIEW"
    if re.search(r"\bDENIED\b", upper):
        return "DENIED"
    if re.search(r"\bAPPROVED\b", upper):
        return "APPROVED"
    return "UNKNOWN"


def expected_from_completion(text: str) -> str:
    """Extract expected decision from training completion text."""
    if "APPROVED WITH CONDITIONS" in text:
        return "AWC"
    if "NEEDS REVIEW" in text:
        return "NEEDS_REVIEW"
    if "DENIED" in text:
        return "DENIED"
    if "APPROVED" in text:
        return "APPROVED"
    return "UNKNOWN"


def call_claude(rt, user_text: str) -> str:
    """Call Claude with the full system prompt and return the response text."""
    resp = rt.converse(
        modelId=CLAUDE_MODEL,
        system=[{"text": SYSTEM_PROMPT_WITH_DATE}],
        messages=[{"role": "user", "content": [{"text": user_text}]}],
        inferenceConfig={"temperature": 0.0, "maxTokens": 2048},
    )
    return resp["output"]["message"]["content"][0]["text"]


# ─── MAIN ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Test Claude accuracy on training data")
    parser.add_argument("--samples", type=int, default=5, help="Samples per category (default 5)")
    parser.add_argument("--verbose", action="store_true", help="Print Claude's full output on failures")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    print(f"Model:     {CLAUDE_MODEL}")
    print(f"Eval date: {EVAL_DATE}")
    print(f"Prompt:    {len(SYSTEM_PROMPT_WITH_DATE)} chars")
    print(f"Samples:   {args.samples} per category")
    print()

    groups = load_and_classify_records(TRAINING_DATA)
    categories = ["PENDING", "DELINQUENT", "FORBEARANCE", "APPROVED", "DENIED_OTHER", "AWC", "NEEDS_REVIEW"]

    print("Dataset distribution:")
    for cat in categories:
        print(f"  {cat:15s}: {len(groups.get(cat, []))} records")
    print()

    rng = random.Random(args.seed)
    test_set = []
    for cat in categories:
        available = groups.get(cat, [])
        if not available:
            continue
        sample = rng.sample(available, min(args.samples, len(available)))
        for idx, rec in sample:
            test_set.append((cat, idx, rec))

    rt = boto3.client("bedrock-runtime", region_name="us-east-1")

    scores: dict[str, list[bool]] = {}
    failures_detail = []

    for i, (cat, idx, rec) in enumerate(test_set):
        user_text = rec["messages"][0]["content"][0]["text"]
        expected_text = rec["messages"][1]["content"][0]["text"]
        expected = expected_from_completion(expected_text)

        try:
            claude_text = call_claude(rt, user_text)
            claude_dec = extract_decision(claude_text)
        except Exception as e:
            claude_dec = "ERROR"
            claude_text = str(e)

        ok = claude_dec == expected
        scores.setdefault(cat, []).append(ok)

        tag = "OK" if ok else "X "
        print(f"  [{i+1:2d}/{len(test_set)}] {cat:15s} {tag}  expected={expected:20s} got={claude_dec}")

        if not ok:
            failures_detail.append({
                "test_num": i + 1,
                "category": cat,
                "record_idx": idx,
                "expected": expected,
                "got": claude_dec,
                "user_text": user_text,
                "claude_text": claude_text,
            })

    # ─── SUMMARY ────────────────────────────────────────────────────────────

    print()
    print(f"{'Category':20s} {'Score':15s}")
    print("=" * 40)
    for cat in categories:
        s = scores.get(cat, [])
        if not s:
            print(f"{cat:20s} {'N/A':15s}")
            continue
        pct = sum(s) / len(s) * 100
        marker = " <-- BELOW 90%" if pct < 90 else ""
        print(f"{cat:20s} {sum(s)}/{len(s)} ({pct:.0f}%){marker}")

    total_ok = sum(sum(v) for v in scores.values())
    total = sum(len(v) for v in scores.values())
    overall = total_ok / total * 100 if total else 0
    print(f"\n{'OVERALL':20s} {total_ok}/{total} ({overall:.0f}%)")

    # ─── FAILURE DETAILS ────────────────────────────────────────────────────

    if failures_detail:
        print(f"\n{'='*60}")
        print(f"FAILURE ANALYSIS ({len(failures_detail)} failures)")
        print(f"{'='*60}")

        for f in failures_detail:
            print(f"\n--- Test #{f['test_num']} | {f['category']} | Record #{f['record_idx']} ---")
            print(f"Expected: {f['expected']}  |  Got: {f['got']}")

            # Extract key fields for diagnosis
            user = f["user_text"]
            program = "VA" if "VA IRRRL" in user else "FHA"
            status = re.search(r"Loan Status:\s*(\w+)", user)
            closing = re.search(r"Original Closing Date:\s*(\S+)", user)
            rates = re.findall(r"Note Rate:\s*([\d.]+)%", user)
            rate_types = re.findall(r"Rate Type:\s*(\w+)", user)
            cash = re.search(r"Cash to Borrower:\s*\$([\d.]+)", user)

            print(f"  Program: {program}, Status: {status.group(1) if status else '?'}")
            if closing:
                from datetime import date
                cd = date.fromisoformat(closing.group(1))
                ed = date.fromisoformat(EVAL_DATE)
                days = (ed - cd).days
                print(f"  Closing: {closing.group(1)}, Days since (eval_date): {days}, >=210: {'PASS' if days >= 210 else 'FAIL'}")
            if len(rates) >= 2:
                print(f"  Rates: {rates[0]}% -> {rates[1]}%, reduction: {float(rates[0])-float(rates[1]):.3f}%")
            if rate_types:
                print(f"  Rate types: {' -> '.join(rate_types)}")
            if cash:
                print(f"  Cash to borrower: ${cash.group(1)}")

            if args.verbose:
                print(f"\n  CLAUDE OUTPUT (first 1000 chars):")
                for line in f["claude_text"][:1000].split("\n"):
                    print(f"    {line}")

    # Exit code
    sys.exit(0 if overall >= 90 else 1)


if __name__ == "__main__":
    main()
