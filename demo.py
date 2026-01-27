"""
Streamline Government Refinance Agent - Demo Script
Runs through test cases to demonstrate the multi-agent system.
"""

import os
import sys
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Ensure we're in local mode
os.environ.setdefault("ENV", "local")


def print_separator(char="═", length=80):
    """Print a separator line."""
    print(char * length)


def print_header(title: str):
    """Print a section header."""
    print_separator()
    print(f"  {title}")
    print_separator()


def run_demo(refi_id: str = None):
    """
    Run the demo for one or all test cases.
    
    Args:
        refi_id: Optional specific application ID to test
    """
    from agents.refi_orchestrator import process_refinance
    
    # Define test cases
    test_cases = [
        {
            "id": "REFI-FHA-001",
            "description": "FHA Streamline - Good loan, should PASS",
            "expected": "APPROVED"
        },
        {
            "id": "REFI-FHA-002",
            "description": "FHA Streamline - Only 4 months old",
            "expected": "DENIED (Seasoning)"
        },
        {
            "id": "REFI-FHA-003",
            "description": "FHA Streamline - Same rate, no benefit",
            "expected": "DENIED (No NTB)"
        },
        {
            "id": "REFI-VA-001",
            "description": "VA IRRRL - Good loan, should PASS",
            "expected": "APPROVED"
        },
        {
            "id": "REFI-VA-002",
            "description": "VA IRRRL - Rate reduction only 0.40%",
            "expected": "DENIED (Rate Reduction)"
        },
        {
            "id": "REFI-VA-003",
            "description": "VA IRRRL - Recoupment > 36 months",
            "expected": "DENIED (Recoupment)"
        },
    ]
    
    # Filter to specific test case if provided
    if refi_id:
        test_cases = [tc for tc in test_cases if tc["id"] == refi_id]
        if not test_cases:
            print(f"❌ Unknown test case: {refi_id}")
            print("\nAvailable test cases:")
            for tc in test_cases:
                print(f"  - {tc['id']}")
            return
    
    # Print banner
    print("""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   🏠 Streamline Government Refinance Agent - DEMO                             ║
║   Testing FHA Streamline & VA IRRRL Scenarios                                 ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"TEST CASE {i}/{len(test_cases)}: {test_case['id']}")
        print(f"Description: {test_case['description']}")
        print(f"Expected: {test_case['expected']}")
        print("="*80 + "\n")
        
        start_time = time.time()
        
        try:
            # Process the application
            prompt = f"Process refinance application {test_case['id']}"
            response = process_refinance(prompt)
            
            elapsed = time.time() - start_time
            
            print(response)
            print(f"\n⏱️  Processing time: {elapsed:.1f} seconds")
            
            # Determine if test passed
            expected_lower = test_case['expected'].lower()
            response_lower = response.lower()
            
            if 'approved' in expected_lower and 'denied' not in expected_lower:
                passed = 'approved' in response_lower and 'denied' not in response_lower
            elif 'denied' in expected_lower:
                passed = 'denied' in response_lower
            else:
                passed = True  # Edge cases
            
            results.append({
                "id": test_case['id'],
                "expected": test_case['expected'],
                "passed": passed,
                "time": elapsed
            })
            
        except Exception as e:
            print(f"\n❌ Error processing {test_case['id']}: {str(e)}")
            results.append({
                "id": test_case['id'],
                "expected": test_case['expected'],
                "passed": False,
                "time": 0,
                "error": str(e)
            })
        
        # Brief pause between tests
        if i < len(test_cases):
            print("\n" + "-"*40)
            print("Proceeding to next test case...")
            time.sleep(1)
    
    # Print summary
    print("\n" + "="*80)
    print("DEMO SUMMARY")
    print("="*80)
    
    passed_count = sum(1 for r in results if r['passed'])
    total_count = len(results)
    
    print(f"\n{'ID':<15} {'Expected':<25} {'Result':<10} {'Time':<10}")
    print("-"*60)
    
    for r in results:
        status = "✅ PASS" if r['passed'] else "❌ FAIL"
        time_str = f"{r['time']:.1f}s" if r['time'] > 0 else "N/A"
        print(f"{r['id']:<15} {r['expected']:<25} {status:<10} {time_str:<10}")
    
    print("-"*60)
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    print("="*80)


if __name__ == "__main__":
    # Check for command line argument
    if len(sys.argv) > 1:
        run_demo(sys.argv[1])
    else:
        run_demo()
