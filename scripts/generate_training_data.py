"""Generate fine-tuning training data for the refi-agent (v4).

v4 changes from v3:
  - 1000 total records (up from 600) for stronger signal
  - Rebalanced: 30% APPROVED, 15% AWC, 45% DENIED, 10% NEEDS REVIEW
  - Hard-stop failures weighted to ~50% of denials (bad_status, missing ID, excess cash)
  - Fixes class imbalance: non-CURRENT loan status now ~15% of dataset

Produces deterministic FHA Streamline and VA IRRRL scenarios with
Python-computed math, validates every record, and writes JSONL files
in bedrock-conversation-2024 format for Amazon Nova Micro fine-tuning.

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

SYSTEM_PROMPT = "You are an FHA/VA underwriting assistant."

# Train/validation split
TRAIN_RATIO = 0.90  # 540 train, 60 validation


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
    parser = argparse.ArgumentParser(description="Generate refi-agent fine-tuning data (v4)")
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
    train_path = output_dir / "nova" / "refi_training_v4_nova.jsonl"
    val_path = output_dir / "nova" / "refi_validation_v4_nova.jsonl"

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
