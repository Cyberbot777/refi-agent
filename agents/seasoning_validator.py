"""
Seasoning Validator Agent
Validates seasoning requirements and payment history.
Implements Section B2 (FHA) and C2 (VA).
"""

import json
from datetime import date, datetime
from strands import Agent, tool
from strands.models import BedrockModel

from config.prompts import SEASONING_VALIDATOR_PROMPT
from utils.config_loader import get_model_config


def create_seasoning_validator_agent() -> Agent:
    """Create a fast seasoning validator agent with NO tools (formatting only)."""
    model_config = get_model_config()
    
    model = BedrockModel(
        model_id=model_config["specialist_model"],
        temperature=model_config["temperature"],
    )
    
    agent = Agent(
        model=model,
        system_prompt=SEASONING_VALIDATOR_PROMPT,
        tools=[],
        callback_handler=None
    )
    
    return agent


@tool
def seasoning_validator(refi_id: str) -> str:
    """
    Validate seasoning and payment history requirements (Section B2/C2).
    
    Args:
        refi_id: The refinance application ID (e.g., "REFI-001")
    
    Returns:
        Seasoning validation report with payment history analysis
    """
    try:
        # Import tools
        from tools.refi_database_tools import get_refi_application, get_payment_history
        from tools.seasoning_tools import calculate_seasoning, validate_payment_history
        
        # PRE-FETCH DATA
        app_data = get_refi_application(refi_id)
        payment_data = get_payment_history(refi_id)
        
        application = json.loads(app_data) if app_data else {}
        payments = json.loads(payment_data) if payment_data else {}
        
        if application.get('error'):
            return f"""**Application:** {refi_id}

### Seasoning Validation Error

❌ **Error:** {application.get('error')}

Unable to validate seasoning."""
        
        # Get dates and program type
        program_type = application.get('existing_loan_type', 'UNKNOWN').upper()
        original_closing = application.get('original_closing_date', '')
        first_payment = application.get('first_payment_due_date', '')
        total_payments = payments.get('total_payments', 0)
        
        # Use today's date as assumed refi closing date
        refi_closing = date.today().strftime('%Y-%m-%d')
        
        # Calculate seasoning
        seasoning_result = calculate_seasoning(
            original_closing_date=original_closing,
            first_payment_due_date=first_payment,
            refi_closing_date=refi_closing,
            total_payments_made=total_payments,
            program_type=program_type
        )
        seasoning = json.loads(seasoning_result)
        
        # Validate payment history
        history_result = validate_payment_history(
            payments_json=payment_data,
            program_type=program_type
        )
        history = json.loads(history_result)
        
        # Extract calculations
        calcs = seasoning.get('calculations', {})
        seasoning_results = seasoning.get('results', [])
        
        # Format seasoning results
        seasoning_formatted = chr(10).join([
            f"- {r['requirement']}: Required={r['required']}, Actual={r['actual']} - {'✅ PASS' if r['passed'] else '❌ FAIL'}"
            for r in seasoning_results
        ])
        
        # Format payment history
        payment_list = payments.get('payments', [])[:12]  # Last 12 months
        payment_formatted = chr(10).join([
            f"- {p.get('payment_date', 'N/A')}: {p.get('status', 'N/A')} ({p.get('days_late', 0)} days late)"
            for p in payment_list
        ])
        
        seasoning_met = seasoning.get('seasoning_met', False)
        history_passed = history.get('passed', False)
        all_passed = seasoning_met and history_passed
        
        # Format response
        agent = create_seasoning_validator_agent()
        
        prompt = f"""Format this seasoning validation data into your standard report format:

**APPLICATION:**
- Refi ID: {refi_id}
- Program: {program_type}
- Original Closing: {original_closing}
- First Payment Due: {first_payment}

**SEASONING CALCULATIONS:**
- Days Since Closing: {calcs.get('days_since_closing', 'N/A')}
- Months Since First Payment: {calcs.get('months_since_first_payment', 'N/A')}
- Total Payments Made: {total_payments}

**SEASONING REQUIREMENTS:**
{seasoning_formatted}

**PAYMENT HISTORY (Last 12 Months):**
{payment_formatted if payment_formatted else '- No payment history available'}

**PAYMENT HISTORY SUMMARY:**
- On-Time: {payments.get('on_time_payments', 0)}
- Late 30+: {payments.get('late_30_payments', 0)}
- Late 60+: {payments.get('late_60_plus_payments', 0)}
- Consecutive On-Time: {payments.get('consecutive_on_time', 0)}
- History Status: {'✅ ACCEPTABLE' if history_passed else '❌ ISSUES FOUND'}

**SEASONING STATUS:**
- Seasoning Met: {'✅ YES' if seasoning_met else '❌ NO'}
- Payment History: {'✅ ACCEPTABLE' if history_passed else '❌ ISSUES'}
- Overall: {'✅ PASSED' if all_passed else '❌ NOT PASSED'}

Format this into your standard seasoning validation report."""

        response = agent(prompt)
        return str(response)
        
    except Exception as e:
        return f"""**Application:** {refi_id}

### Seasoning Validation Error

- **Status:** ⚠️ ERROR
- **Error:** {str(e)}
- **Action Required:** Manual seasoning review needed"""
