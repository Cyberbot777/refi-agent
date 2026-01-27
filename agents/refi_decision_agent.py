"""
Refi Decision Agent
Makes final pre-qualification decision for streamline government refinances.
Synthesizes all validation results into approval/denial/conditions.
"""

import json
from strands import Agent, tool
from strands.models import BedrockModel

from config.prompts import REFI_DECISION_AGENT_PROMPT
from utils.config_loader import get_model_config


def create_refi_decision_agent() -> Agent:
    """Create a decision agent with NO tools (synthesis and formatting only)."""
    model_config = get_model_config()
    
    model = BedrockModel(
        model_id=model_config["specialist_model"],
        temperature=model_config["temperature"],
    )
    
    agent = Agent(
        model=model,
        system_prompt=REFI_DECISION_AGENT_PROMPT,
        tools=[],
        callback_handler=None
    )
    
    return agent


@tool
def refi_decision_agent(refi_id: str) -> str:
    """
    Make final refinance pre-qualification decision.
    
    Args:
        refi_id: The refinance application ID (e.g., "REFI-001")
    
    Returns:
        Final decision report with approval/denial status and conditions
    """
    try:
        # Import tools
        from tools.refi_database_tools import (
            get_refi_application, 
            get_payment_history,
            get_refi_documents,
            save_refi_decision
        )
        from tools.seasoning_tools import calculate_seasoning, validate_payment_history
        from tools.ntb_tools import calculate_fha_ntb, calculate_va_ntb
        from tools.recoupment_tools import calculate_va_recoupment, check_piti_increase_trigger
        from tools.refi_rules import check_fha_hard_stops, check_va_hard_stops
        
        # PRE-FETCH ALL DATA
        app_data = get_refi_application(refi_id)
        payment_data = get_payment_history(refi_id)
        docs_data = get_refi_documents(refi_id)
        
        application = json.loads(app_data) if app_data else {}
        payments = json.loads(payment_data) if payment_data else {}
        documents = json.loads(docs_data) if docs_data else {}
        
        if application.get('error'):
            return f"""**Application:** {refi_id}

### Decision Error

❌ **Error:** {application.get('error')}

Unable to make decision."""
        
        # Extract key data
        program_type = application.get('existing_loan_type', 'UNKNOWN').upper()
        borrower_name = application.get('borrower_name', 'Unknown')
        property_address = application.get('property_address', 'Unknown')
        
        # Track all validation results
        validations = {
            'package_complete': len(documents.get('missing_required', [])) == 0,
            'eligibility_passed': True,  # Will be updated
            'seasoning_met': True,  # Will be updated
            'ntb_confirmed': True,  # Will be updated
            'recoupment_passed': True,  # VA only
            'piti_trigger': False  # VA only
        }
        
        conditions = []
        denial_reasons = []
        
        # Check eligibility (hard stops)
        cash_to_borrower = float(application.get('cash_to_borrower', 0) or 0)
        late_60_plus = payments.get('late_60_plus_payments', 0)
        loan_is_current = late_60_plus == 0
        
        if program_type == 'FHA':
            fha_result = check_fha_hard_stops(
                existing_loan_type=program_type,
                fha_case_number=application.get('fha_case_number', ''),
                loan_is_current=loan_is_current,
                cash_to_borrower=cash_to_borrower
            )
            eligibility = json.loads(fha_result)
            validations['eligibility_passed'] = eligibility.get('eligible', False)
            if not validations['eligibility_passed']:
                denial_reasons.append("Failed FHA hard stop requirements")
                
        elif program_type == 'VA':
            va_result = check_va_hard_stops(
                existing_loan_type=program_type,
                va_loan_number=application.get('va_loan_number', ''),
                same_property=True,
                cash_to_borrower=cash_to_borrower,
                allowable_fees_only=True
            )
            eligibility = json.loads(va_result)
            validations['eligibility_passed'] = eligibility.get('eligible', False)
            if not validations['eligibility_passed']:
                denial_reasons.append("Failed VA hard stop requirements")
        
        # Check seasoning
        from datetime import date
        if application.get('original_closing_date'):
            seasoning_result = calculate_seasoning(
                original_closing_date=application.get('original_closing_date'),
                first_payment_due_date=application.get('first_payment_due_date'),
                refi_closing_date=date.today().strftime('%Y-%m-%d'),
                total_payments_made=payments.get('total_payments', 0),
                program_type=program_type
            )
            seasoning = json.loads(seasoning_result)
            validations['seasoning_met'] = seasoning.get('seasoning_met', False)
            if not validations['seasoning_met']:
                denial_reasons.append("Seasoning requirements not met")
        
        # Check payment history
        history_result = validate_payment_history(payment_data, program_type)
        history = json.loads(history_result)
        if not history.get('passed', True):
            conditions.append("Payment history requires review")
        
        # Calculate NTB
        old_rate = float(application.get('current_note_rate', 0) or 0)
        new_rate = float(application.get('new_note_rate', 0) or 0)
        old_pi = float(application.get('current_monthly_pi', 0) or 0)
        new_pi = float(application.get('new_monthly_pi', 0) or 0)
        old_mip = float(application.get('current_annual_mip', 0) or 0)
        new_mip = float(application.get('new_annual_mip', 0) or 0)
        
        if program_type == 'FHA':
            ntb_result = calculate_fha_ntb(
                old_note_rate=old_rate,
                new_note_rate=new_rate,
                old_annual_mip=old_mip,
                new_annual_mip=new_mip,
                old_monthly_pi=old_pi,
                new_monthly_pi=new_pi,
                old_loan_term_months=360,
                new_loan_term_months=int(application.get('new_loan_term_months', 360) or 360)
            )
        else:
            ntb_result = calculate_va_ntb(
                old_note_rate=old_rate,
                new_note_rate=new_rate,
                old_monthly_pi=old_pi,
                new_monthly_pi=new_pi
            )
        
        ntb = json.loads(ntb_result)
        validations['ntb_confirmed'] = ntb.get('ntb_confirmed', False)
        if not validations['ntb_confirmed']:
            denial_reasons.append("Net Tangible Benefit not confirmed")
        
        # VA-specific: Recoupment and PITI trigger
        if program_type == 'VA':
            recoup_result = calculate_va_recoupment(
                total_closing_costs=float(application.get('total_closing_costs', 0) or 0),
                taxes_amount=float(application.get('taxes_amount', 0) or 0),
                escrow_deposits=float(application.get('escrow_deposits', 0) or 0),
                va_funding_fee=float(application.get('va_funding_fee', 0) or 0),
                old_monthly_pi=old_pi,
                new_monthly_pi=new_pi
            )
            recoup = json.loads(recoup_result)
            validations['recoupment_passed'] = recoup.get('passed', False)
            if not validations['recoupment_passed']:
                denial_reasons.append("Fee recoupment exceeds 36-month limit")
            
            piti_result = check_piti_increase_trigger(
                old_monthly_piti=float(application.get('current_monthly_piti', 0) or 0),
                new_monthly_piti=float(application.get('new_monthly_piti', 0) or 0)
            )
            piti = json.loads(piti_result)
            validations['piti_trigger'] = piti.get('trigger', {}).get('triggered', False)
            if validations['piti_trigger']:
                conditions.append("20% PITI trigger - verify ability to pay")
        
        # Determine decision
        critical_failures = not all([
            validations['eligibility_passed'],
            validations['seasoning_met'],
            validations['ntb_confirmed'],
            validations['recoupment_passed'] if program_type == 'VA' else True
        ])
        
        if critical_failures:
            decision = 'DENIED'
            confidence = 95
        elif conditions or validations['piti_trigger']:
            decision = 'APPROVED_WITH_CONDITIONS' if validations['package_complete'] else 'MANUAL_REVIEW_REQUIRED'
            confidence = 85
        elif not validations['package_complete']:
            decision = 'MANUAL_REVIEW_REQUIRED'
            confidence = 75
            conditions.append("Complete document package required")
        else:
            decision = 'APPROVED'
            confidence = 95
        
        # Calculate key metrics
        rate_reduction = old_rate - new_rate
        monthly_savings = old_pi - new_pi
        
        # Save decision
        try:
            save_refi_decision(
                refi_id=refi_id,
                decision=decision,
                decision_type='PREQUALIFICATION',
                confidence_score=confidence,
                reasoning=f"Program: {program_type}. " + (denial_reasons[0] if denial_reasons else "All requirements met."),
                conditions=conditions if conditions else None,
                agent_name='refi_decision_agent'
            )
        except Exception:
            pass  # Don't fail decision if save fails
        
        # Format response
        agent = create_refi_decision_agent()
        
        prompt = f"""Format this decision data into your standard report format:

**APPLICATION:**
- Refi ID: {refi_id}
- Program: {program_type}
- Borrower: {borrower_name}
- Property: {property_address}

**VALIDATION SUMMARY:**
| Category | Status |
|----------|--------|
| Package Complete | {'✅' if validations['package_complete'] else '❌'} |
| Eligibility (Hard Stops) | {'✅' if validations['eligibility_passed'] else '❌'} |
| Seasoning Met | {'✅' if validations['seasoning_met'] else '❌'} |
| Net Tangible Benefit | {'✅' if validations['ntb_confirmed'] else '❌'} |
| Recoupment (VA) | {'✅' if validations['recoupment_passed'] else '❌' if program_type == 'VA' else 'N/A'} |
| 20% PITI Trigger | {'⚠️' if validations['piti_trigger'] else '✅' if program_type == 'VA' else 'N/A'} |

**DECISION:** {decision}
**Confidence:** {confidence}%

**KEY METRICS:**
- Rate Reduction: {rate_reduction:.3f}%
- Monthly Savings: ${monthly_savings:,.2f}
- Payments Made: {payments.get('total_payments', 0)}

**CONDITIONS:** {chr(10).join(f'- {c}' for c in conditions) if conditions else 'None'}

**DENIAL REASONS:** {chr(10).join(f'- {r}' for r in denial_reasons) if denial_reasons else 'None'}

Format this into your standard refinance decision report with next steps."""

        response = agent(prompt)
        return str(response)
        
    except Exception as e:
        return f"""**Application:** {refi_id}

### Decision Error

- **Status:** ⚠️ ERROR
- **Error:** {str(e)}
- **Action Required:** Manual underwriting review required"""
