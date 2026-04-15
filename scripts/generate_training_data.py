"""Generate fine-tuning training data for the refi-agent (v7 — Nova Lite v2).

v7 changes from v6:
  - Refined system prompt: explicit decision priority ordering, CRITICAL rule
    that failed checks cannot be edge cases, concrete DENIED vs AWC examples.
  - Same 3000 records, same class balance (25/20/35/20)
  - Targets the AWC/DENIED boundary confusion seen in Nova Lite v1 (83%)

Produces deterministic FHA Streamline and VA IRRRL scenarios with
Python-computed math, validates every record, and writes JSONL files
in bedrock-conversation-2024 format for Amazon Nova Lite fine-tuning.

Usage:
    python -m scripts.generate_training_data [--seed 42] [--output-dir data]
"""

import argparse
import json
import os
import random
import sys
from pathlib import Path

from scripts.lib.scenarios import ScenarioGenerator
from scripts.lib.templates import render_user_prompt, render_completion
from scripts.lib.validators import validate_all

SYSTEM_PROMPT = """You are an FHA Streamline / VA IRRRL underwriting assistant. Evaluate loan applications and output a structured decision report.

DECISION PRIORITY (apply in this order):
1. DENIED: Any required check fails. Non-CURRENT loan status (PENDING, DELINQUENT, FORBEARANCE) is always an immediate DENY. A value that does not meet its threshold is a FAIL — never call it an edge case.
2. NEEDS REVIEW: VA only — all C1-C4 checks pass but monthly PITI increases by 20% or more (C5 trigger). This is NOT a denial.
3. APPROVED WITH CONDITIONS: ALL checks pass, but one or more edge-case flags triggered. Edge cases mean the value PASSES its threshold but is close to the boundary. Examples: cash $400-$500 (passes the $500 limit but barely), 1x 30-day late (within the 1 allowed), NTB margin < 0.400% above minimum, recoupment 28-36 months (passes the 36-month limit but tight), rate reduction within 0.050% above the required minimum.
4. APPROVED: All checks pass, no edge-case flags.

CRITICAL: A check that FAILS cannot be an edge case. Rate reduction 0.125% when the threshold is 0.500% is a FAIL (DENIED), not an edge case. Recoupment of 40 months when the limit is 36 is a FAIL (DENIED), not an edge case. Only values that PASS but are near the boundary trigger APPROVED WITH CONDITIONS.

Key thresholds:
- Seasoning: >= 210 days since closing, >= 6 months since first payment, >= 6 payments made.
- FHA NTB: combined rate reduction >= 0.250% (note rate + annual MIP).
- VA Fixed-to-Fixed: rate reduction >= 0.500%. Fixed-to-ARM: >= 2.000%. ARM-to-Fixed: auto-pass.
- VA recoupment: recoupable costs / monthly P&I savings <= 36 months.
- FHA cash to borrower: <= $500. VA cash to borrower: $0.
- Payment history: <= 1x 30-day late, 0x 60+ day late (FHA). 6 consecutive on-time (VA)."""

# Train/validation split
TRAIN_RATIO = 0.90


def build_records(seed: int = 42):
    """Generate all scenarios, render templates, validate, and return records."""
    gen = ScenarioGenerator(seed=seed)
    pairs = gen.generate_all()

    records = []
    for scenario, result in pairs:
        user_prompt = render_user_prompt(result)
        completion = render_completion(result)
        records.append((scenario, result, user_prompt, completion))

    # Validate every record — raises on any mismatch
    validate_all(records, verbose=True)
    return records


def to_jsonl_entry(user_prompt: str, completion: str) -> dict:
    """Format a single record as a Bedrock fine-tuning JSONL entry (bedrock-conversation-2024)."""
    return {
        "schemaVersion": "bedrock-conversation-2024",
        "system": [{"text": SYSTEM_PROMPT}],
        "messages": [
            {"role": "user", "content": [{"text": user_prompt}]},
            {"role": "assistant", "content": [{"text": completion}]},
        ],
    }


def write_jsonl(entries: list[dict], path: Path):
    """Write a list of dicts as JSONL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Generate refi-agent fine-tuning data (v7 — Nova Lite v2)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--output-dir", type=str, default="data", help="Output directory (default: data)")
    args = parser.parse_args()

    print(f"Generating training data with seed={args.seed}...")
    records = build_records(seed=args.seed)

    total = len(records)
    train_count = int(total * TRAIN_RATIO)
    val_count = total - train_count

    print(f"\nTotal records: {total}")
    print(f"Train: {train_count}, Validation: {val_count}")

    # Class distribution summary
    from collections import Counter
    decisions = Counter(r[1].decision for r in records)
    print(f"\nClass distribution:")
    for cls in sorted(decisions.keys()):
        count = decisions[cls]
        print(f"  {cls}: {count} ({count/total*100:.1f}%)")

    # Convert to JSONL entries
    all_entries = [to_jsonl_entry(up, comp) for _, _, up, comp in records]

    # Deterministic shuffle (already shuffled in scenario generator, but re-shuffle for split)
    rng = random.Random(args.seed)
    indices = list(range(total))
    rng.shuffle(indices)

    train_entries = [all_entries[i] for i in indices[:train_count]]
    val_entries = [all_entries[i] for i in indices[train_count:]]

    # Write files
    output_dir = Path(args.output_dir)
    train_path = output_dir / "nova" / "refi_training_v7_nova_lite.jsonl"
    val_path = output_dir / "nova" / "refi_validation_v7_nova_lite.jsonl"

    write_jsonl(train_entries, train_path)
    write_jsonl(val_entries, val_path)

    print(f"\nFiles written:")
    print(f"  {train_path} ({train_count} records)")
    print(f"  {val_path} ({val_count} records)")

    # Quick sanity check — verify files are valid JSONL
    for path, expected in [(train_path, train_count), (val_path, val_count)]:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == expected, f"{path}: expected {expected} lines, got {len(lines)}"
        for i, line in enumerate(lines):
            obj = json.loads(line)
            assert "schemaVersion" in obj, f"{path} line {i}: missing 'schemaVersion'"
            assert obj["schemaVersion"] == "bedrock-conversation-2024", f"{path} line {i}: wrong schema"
            assert "system" in obj, f"{path} line {i}: missing 'system'"
            assert isinstance(obj["system"], list), f"{path} line {i}: system must be list"
            assert "messages" in obj, f"{path} line {i}: missing 'messages'"
            assert len(obj["messages"]) == 2, f"{path} line {i}: expected 2 messages"
            assert isinstance(obj["messages"][0]["content"], list), f"{path} line {i}: content must be list"

    print("\nSanity check passed. Done!")


if __name__ == "__main__":
    main()
