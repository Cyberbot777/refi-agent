"""
Eligibility Checker Agent
Verifies hard stop criteria for FHA Streamline (B1) and VA IRRRL (C1).
Any hard stop failure results in INELIGIBLE status.
"""

import json
from strands import Agent, tool
from strands.models import BedrockModel

from config.prompts import ELIGIBILITY_CHECKER_PROMPT
from utils.config_loader import get_model_config


def create_eligibility_checker_agent() -> Agent:
    """Create a fast eligibility checker agent with NO tools (formatting only)."""
    model_config = get_model_config()
    
    model = BedrockModel(
        model_id=model_config["specialist_model"],
        temperature=model_config["temperature"],
    )
    
    agent = Agent(
        model=model,
        system_prompt=ELIGIBILITY_CHECKER_PROMPT,
        tools=[],
        callback_handler=None
    )
    
    return agent


@tool
def eligibility_checker(refi_id: str) -> str:
    """
    Check hard stop eligibility requirements (Section B1 for FHA, C1 for VA).
    
    Args:
        refi_id: The refinance application ID (e.g., "REFI-001")
    
    Returns:
        Eligibility check results with pass/fail status
    """
    try:
        # Import tools
        from tools.refi_database_tools import get_refi_application, get_payment_history
        from tools.refi_rules import check_fha_hard_stops, check_va_hard_stops
        
        # PRE-FETCH DATA
        app_data = get_refi_application(refi_id)
        payment_data = get_payment_history(refi_id)
        
        application = json.loads(app_data) if app_data else {}
        payments = json.loads(payment_data) if payment_data else {}
        
        if application.get('error'):
            return f"""**Application:** {refi_id}

### Eligibility Check Error

❌ **Error:** {application.get('error')}

Unable to verify eligibility."""
        
        # Determine program type
        program_type = application.get('existing_loan_type', 'UNKNOWN').upper()
        
        # Check if loan is current (no recent delinquencies)
        late_payments = payments.get('late_60_plus_payments', 0)
        loan_is_current = late_payments == 0
        
        # Get cash to borrower
        cash_to_borrower = float(application.get('cash_to_borrower', 0) or 0)
        
        # Run appropriate hard stop checks
        if program_type == 'FHA':
            fha_case_number = application.get('fha_case_number', '')
            
            results = check_fha_hard_stops(
                existing_loan_type=program_type,
                fha_case_number=fha_case_number,
                loan_is_current=loan_is_current,
                cash_to_borrower=cash_to_borrower
            )
            hard_stop_results = json.loads(results)
            
        elif program_type == 'VA':
            va_loan_number = application.get('va_loan_number', '')
            
            results = check_va_hard_stops(
                existing_loan_type=program_type,
                va_loan_number=va_loan_number,
                same_property=True,  # Assume same property for now
                cash_to_borrower=cash_to_borrower,
                allowable_fees_only=True  # Assume compliant for now
            )
            hard_stop_results = json.loads(results)
        else:
            return f"""**Application:** {refi_id}

### Eligibility Check

❌ **Error:** Unknown loan type: {program_type}

Unable to determine eligibility rules. Loan type must be FHA or VA."""
        
        # Format response
        agent = create_eligibility_checker_agent()
        
        # Build results table
        results_list = hard_stop_results.get('results', [])
        results_formatted = chr(10).join([
            f"- {r['requirement']}: {'✅ PASS' if r['passed'] else '❌ FAIL'} - {r['evidence']}"
            for r in results_list
        ])
        
        eligible = hard_stop_results.get('eligible', False)
        
        prompt = f"""Format this eligibility check data into your standard report format:

**APPLICATION:**
- Refi ID: {refi_id}
- Program: {program_type}
- Borrower: {application.get('borrower_name', 'Unknown')}

**HARD STOP VERIFICATION:**
{results_formatted}

**ELIGIBILITY STATUS:**
- All Hard Stops Passed: {eligible}
- Status: {'✅ ELIGIBLE' if eligible else '❌ INELIGIBLE'}

**SUMMARY:**
{hard_stop_results.get('summary', '')}

Format this into your standard eligibility check report."""

        response = agent(prompt)
        return str(response)
        
    except Exception as e:
        return f"""**Application:** {refi_id}

### Eligibility Check Error

- **Status:** ⚠️ ERROR
- **Error:** {str(e)}
- **Action Required:** Manual eligibility review needed"""
