"""
Streamline Government Refinance Agent - Interactive CLI
Main entry point for testing the multi-agent system interactively.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Ensure we're in local mode
os.environ.setdefault("ENV", "local")


def print_banner():
    """Print the application banner."""
    banner = """
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║   🏠 Streamline Government Refinance Agent                                ║
║   FHA Streamline & VA IRRRL Pre-Qualification System                      ║
║                                                                           ║
║   Kind Lending - AI Automation                                            ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_test_cases():
    """Print available test cases."""
    print("""
📋 Available Test Cases:

┌─────────────────┬────────┬──────────────────────────────────┐
│ Application ID  │ Program│ Expected Outcome                 │
├─────────────────┼────────┼──────────────────────────────────┤
│ REFI-FHA-001    │ FHA    │ ✅ APPROVED                      │
│ REFI-FHA-002    │ FHA    │ ❌ DENIED - Seasoning            │
│ REFI-FHA-003    │ FHA    │ ❌ DENIED - No NTB               │
│ REFI-FHA-004    │ FHA    │ ⚠️  APPROVED WITH CONDITIONS     │
├─────────────────┼────────┼──────────────────────────────────┤
│ REFI-VA-001     │ VA     │ ✅ APPROVED                      │
│ REFI-VA-002     │ VA     │ ❌ DENIED - Rate Reduction       │
│ REFI-VA-003     │ VA     │ ❌ DENIED - Recoupment           │
│ REFI-VA-004     │ VA     │ ⚠️  MANUAL REVIEW - 20% PITI     │
└─────────────────┴────────┴──────────────────────────────────┘

💡 Try: "Process REFI-FHA-001" or "Process REFI-VA-001"
""")


def main():
    """Main interactive loop."""
    print_banner()
    print_test_cases()
    
    # Import the orchestrator
    from agents.refi_orchestrator import process_refinance
    
    print("\n🤖 Agent ready. Type your request or 'quit' to exit.\n")
    print("─" * 75)
    
    while True:
        try:
            # Get user input
            user_input = input("\n📝 You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ('quit', 'exit', 'q'):
                print("\n👋 Goodbye!\n")
                break
            
            if user_input.lower() == 'help':
                print_test_cases()
                continue
            
            if user_input.lower() == 'cases':
                print_test_cases()
                continue
            
            # Process the request
            print("\n" + "─" * 75)
            print("🔄 Processing...\n")
            
            response = process_refinance(user_input)
            
            print("\n🤖 Agent Response:")
            print("─" * 75)
            print(response)
            print("─" * 75)
            
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted. Goodbye!\n")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            print("Please try again or type 'quit' to exit.\n")


if __name__ == "__main__":
    main()
