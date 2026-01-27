"""
Recoupment Analyzer Agent
Calculates VA IRRRL fee recoupment (C4) and evaluates 20% PITI trigger (C5).
Only applies to VA IRRRL loans.
"""

import json
from strands import Agent, tool
from strands.models import BedrockModel

from config.prompts import RECOUPMENT_ANALYZER_PROMPT
from utils.config_loader import get_model_config


def create_recoupment_analyzer_agent() -> Agent:
    """Create a fast recoupment analyzer agent with NO tools (formatting only)."""
    model_config = get_model_config()
    
    model = BedrockModel(
        model_id=model_config["specialist_model"],
        temperature=model_config["temperature"],
    )
    
    agent = Agent(
        model=model,
        system_prompt=RECOUPMENT_ANALYZER_PROMPT,
        tools=[],
        callback_handler=None
    )
    
    return agent


@tool
def recoupment_analyzer(refi_id: str) -> str:
    """
    Analyze VA IRRRL recoupment (C4) and 20% PITI trigger (C5).
    
    Args:
        refi_id: The refinance application ID (e.g., "REFI-001")
    
    Returns:
        Recoupment analysis report (VA only) or N/A for FHA
    """
    try:
        # Import tools
        from tools.refi_database_tools import get_refi_application
        from tools.recoupment_tools import calculate_va_recoupment, check_piti_increase_trigger
        
        # PRE-FETCH DATA
        app_data = get_refi_application(refi_id)
        application = json.loads(app_data) if app_data else {}
        
        if application.get('error'):
            return f"""**Application:** {refi_id}

### Recoupment Analysis Error

❌ **Error:** {application.get('error')}

Unable to perform recoupment analysis."""
        
        # Check program type
        program_type = application.get('existing_loan_type', 'UNKNOWN').upper()
        
        if program_type != 'VA':
            return f"""**Application:** {refi_id}
**Program:** {program_type}

### Recoupment Analysis

**N/A** - Recoupment analysis only applies to VA IRRRL loans.

FHA Streamline refinances do not have a statutory recoupment requirement."""
        
        # Extract financial data
        total_closing_costs = float(application.get('total_closing_costs', 0) or 0)
        va_funding_fee = float(application.get('va_funding_fee', 0) or 0)
        taxes_amount = float(application.get('taxes_amount', 0) or 0)
        escrow_deposits = float(application.get('escrow_deposits', 0) or 0)
        
        old_monthly_pi = float(application.get('current_monthly_pi', 0) or 0)
        new_monthly_pi = float(application.get('new_monthly_pi', 0) or 0)
        old_monthly_piti = float(application.get('current_monthly_piti', 0) or 0)
        new_monthly_piti = float(application.get('new_monthly_piti', 0) or 0)
        
        # Calculate recoupment (C4)
        recoupment_result = calculate_va_recoupment(
            total_closing_costs=total_closing_costs,
            taxes_amount=taxes_amount,
            escrow_deposits=escrow_deposits,
            va_funding_fee=va_funding_fee,
            old_monthly_pi=old_monthly_pi,
            new_monthly_pi=new_monthly_pi
        )
        recoupment = json.loads(recoupment_result)
        
        # Check PITI trigger (C5)
        piti_result = check_piti_increase_trigger(
            old_monthly_piti=old_monthly_piti,
            new_monthly_piti=new_monthly_piti
        )
        piti_trigger = json.loads(piti_result)
        
        # Extract values
        fee_breakdown = recoupment.get('fee_breakdown', {})
        recoupable_fees = fee_breakdown.get('recoupable_fees', 0)
        monthly_savings = recoupment.get('payment_comparison', {}).get('monthly_savings', 0)
        recoupment_months = recoupment.get('recoupment_months')
        recoupment_passed = recoupment.get('passed', False)
        special_case = recoupment.get('special_case', False)
        
        piti_triggered = piti_trigger.get('trigger', {}).get('triggered', False)
        piti_change = piti_trigger.get('payments', {}).get('piti_increase_percent', 0)
        
        # Format response
        agent = create_recoupment_analyzer_agent()
        
        prompt = f"""Format this recoupment analysis data into your standard report format:

**APPLICATION:**
- Refi ID: {refi_id}
- Program: VA IRRRL
- Borrower: {application.get('borrower_name', 'Unknown')}

**FEE RECOUPMENT CALCULATION (C4):**

| Fee Category | Amount | In Recoupment? |
|--------------|--------|----------------|
| Total Closing Costs | ${total_closing_costs:,.2f} | - |
| Less: Taxes | -${taxes_amount:,.2f} | Excluded |
| Less: Escrow Deposits | -${escrow_deposits:,.2f} | Excluded |
| Less: VA Funding Fee | -${va_funding_fee:,.2f} | Excluded |
| **Recoupable Fees** | **${recoupable_fees:,.2f}** | - |

| P&I Calculation | Amount |
|-----------------|--------|
| Old Monthly P&I | ${old_monthly_pi:,.2f} |
| New Monthly P&I | ${new_monthly_pi:,.2f} |
| **Monthly Savings** | **${monthly_savings:,.2f}** |

**Recoupment Period:** {f'{recoupment_months} months' if recoupment_months else 'Cannot calculate - no P&I savings'}
**Maximum Allowed:** 36 months
**Status:** {'✅ PASSES' if recoupment_passed else '❌ FAILS' if not special_case else '⚠️ SPECIAL CASE'}

**20% PITI TRIGGER (C5):**

| Payment | Old | New | Change |
|---------|-----|-----|--------|
| Total PITI | ${old_monthly_piti:,.2f} | ${new_monthly_piti:,.2f} | {piti_change:+.1f}% |

**Trigger Status:** {'⚠️ TRIGGERED - Manual Review Required' if piti_triggered else '✅ NOT TRIGGERED'}

**OVERALL RECOUPMENT STATUS:**
{recoupment.get('summary', '')}

Format this into your standard recoupment analysis report."""

        response = agent(prompt)
        return str(response)
        
    except Exception as e:
        return f"""**Application:** {refi_id}

### Recoupment Analysis Error

- **Status:** ⚠️ ERROR
- **Error:** {str(e)}
- **Action Required:** Manual recoupment calculation needed"""
