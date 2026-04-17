"""
Evaluation script for the Streamline Refi Agent.
Runs all test cases, checks the decision saved to DB, compares to expected.
"""

import time
import json
import io
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Expected correct outcomes (manually verified from DB data + rules)
EXPECTED = {
    "REFI-FHA-001": {"decision": "APPROVED",      "reason": "All FHA checks pass"},
    "REFI-FHA-002": {"decision": "DENIED",         "reason": "B1: loan_status=PENDING"},
    "REFI-FHA-003": {"decision": "DENIED",         "reason": "B1: loan_status=PENDING + no NTB"},
    "REFI-FHA-004": {"decision": "DENIED",         "reason": "B1: loan_status=PENDING"},
    "REFI-VA-001":  {"decision": "APPROVED",       "reason": "All VA checks pass"},
    "REFI-VA-002":  {"decision": "DENIED",         "reason": "C3: 0.40% < 0.50% NTB"},
    "REFI-VA-003":  {"decision": "DENIED",         "reason": "C4: 89.8mo > 36mo recoupment"},
    "REFI-VA-004":  {"decision": "NEEDS_REVIEW",   "reason": "C5: PITI +22.7% > 20%"},
}


def get_latest_decision(refi_id: str) -> dict:
    """Query the DB for the most recent decision the agent recorded."""
    conn = psycopg2.connect("postgresql://refiuser:localdev@localhost:5432/refi_agent")
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT decision, reasoning, created_at 
        FROM refi_decision_log 
        WHERE refi_id = %s 
        ORDER BY created_at DESC LIMIT 1
    """, (refi_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def clear_old_decisions():
    """Clear previous eval decisions so we get fresh results."""
    conn = psycopg2.connect("postgresql://refiuser:localdev@localhost:5432/refi_agent")
    cur = conn.cursor()
    cur.execute("DELETE FROM refi_decision_log")
    conn.commit()
    cur.close()
    conn.close()
    print("  Cleared old decisions from refi_decision_log")


def run_eval():
    """Run the agent against all test cases and grade results."""
    from agents.claude_refi_agent import process_application

    cases = sorted(EXPECTED.keys())

    print(f"\n{'='*70}")
    print(f"  REFI AGENT EVALUATION - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Running {len(cases)} test cases against Sonnet agent")
    print(f"{'='*70}")

    clear_old_decisions()
    print()

    results = []
    for refi_id in cases:
        expected = EXPECTED[refi_id]
        print(f"  {refi_id} (expected: {expected['decision']})...", end=" ", flush=True)

        start = time.time()
        try:
            # Suppress agent's verbose streaming output
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                process_application(refi_id)
            finally:
                sys.stdout = old_stdout
            elapsed = time.time() - start

            # Get what the agent actually recorded
            db_decision = get_latest_decision(refi_id)
            if db_decision:
                actual = db_decision["decision"]
                reasoning = db_decision["reasoning"]
            else:
                actual = "NO_DECISION"
                reasoning = "Agent did not call record_decision"

            # Normalize spacing variants (e.g., "NEEDS REVIEW" vs "NEEDS_REVIEW")
            actual_norm = actual.upper().replace(" ", "_")
            expected_norm = expected["decision"].upper().replace(" ", "_")
            correct = actual_norm == expected_norm
            results.append({
                "refi_id": refi_id,
                "expected": expected["decision"],
                "actual": actual,
                "correct": correct,
                "time_sec": round(elapsed, 1),
                "reasoning": reasoning,
                "expected_reason": expected["reason"],
            })

            status = "CORRECT" if correct else "WRONG"
            print(f"{actual} | {status} | {elapsed:.1f}s")
            if not correct:
                print(f"    >>> Expected {expected['decision']} ({expected['reason']})")
                print(f"    >>> Agent reasoning: {reasoning[:150]}")

        except Exception as e:
            elapsed = time.time() - start
            results.append({
                "refi_id": refi_id,
                "expected": expected["decision"],
                "actual": "ERROR",
                "correct": False,
                "time_sec": round(elapsed, 1),
                "reasoning": str(e),
                "expected_reason": expected["reason"],
            })
            print(f"ERROR | {elapsed:.1f}s | {e}")

    # Summary
    correct_count = sum(1 for r in results if r["correct"])
    total = len(results)
    accuracy = (correct_count / total * 100) if total > 0 else 0
    total_time = sum(r["time_sec"] for r in results)

    print(f"\n{'='*70}")
    print(f"  RESULTS: {correct_count}/{total} correct ({accuracy:.0f}%)")
    print(f"  Time: {total_time:.0f}s total ({total_time/total:.0f}s avg)")

    failures = [r for r in results if not r["correct"]]
    if failures:
        print(f"\n  FAILURES ({len(failures)}):")
        for f in failures:
            print(f"    {f['refi_id']}: got {f['actual']}, expected {f['expected']}")
    else:
        print("\n  ALL CORRECT!")

    # Save
    report_file = f"eval_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w") as fp:
        json.dump({"accuracy": accuracy, "results": results}, fp, indent=2, default=str)
    print(f"\n  Saved to: {report_file}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    run_eval()
