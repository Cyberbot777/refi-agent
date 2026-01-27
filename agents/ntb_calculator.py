"""
NTB Calculator Agent
Calculates Net Tangible Benefit for FHA Streamline (B5) and VA IRRRL (C3).
"""

import json
from strands import Agent, tool
from strands.models import BedrockModel

from config.prompts import NTB_CALCULATOR_PROMPT
from utils.config_loader import get_model_config


def create_ntb_calculator_agent() -> Agent:
    """Create a fast NTB calculator agent with NO tools (formatting only)."""
    model_config = get_model_config()
    
    model = BedrockModel(
        model_id=model_config["specialist_model"],
        temperature=model_config["temperature"],
    )
    
    agent = Agent(
        model=model,
        system_prompt=NTB_CALCULATOR_PROMPT,
        tools=[],
        callback_handler=None
    )
    
    return agent


@tool
def ntb_calculator(refi_id: str) -> str:
    """
    Calculate Net Tangible Benefit (Section B5 for FHA, C3 for VA).
    
    Args:
        refi_id: The refinance application ID (e.g., "REFI-001")
    
    Returns:
        NTB calculation report with pass/fail status
    """
    try:
        # Import tools
        from tools.refi_database_tools import get_refi_application
        from tools.ntb_tools import calculate_fha_ntb, calculate_va_ntb
        
        # PRE-FETCH DATA
        app_data = get_refi_application(refi_id)
        application = json.loads(app_data) if app_data else {}
        
        if application.get('error'):
            return f"""**Application:** {refi_id}

### NTB Calculation Error

❌ **Error:** {application.get('error')}

Unable to calculate Net Tangible Benefit."""
        
        # Extract loan data
        program_type = application.get('existing_loan_type', 'UNKNOWN').upper()
        
        # Old loan details
        old_note_rate = float(application.get('current_note_rate', 0) or 0)
        old_annual_mip = float(application.get('current_annual_mip', 0) or 0)
        old_monthly_pi = float(application.get('current_monthly_pi', 0) or 0)
        old_monthly_piti = float(application.get('current_monthly_piti', 0) or 0)
        
        # New loan details
        new_note_rate = float(application.get('new_note_rate', 0) or 0)
        new_annual_mip = float(application.get('new_annual_mip', 0) or 0)
        new_monthly_pi = float(application.get('new_monthly_pi', 0) or 0)
        new_monthly_piti = float(application.get('new_monthly_piti', 0) or 0)
        new_loan_term = int(application.get('new_loan_term_months', 360) or 360)
        
        # Rate types (default to FIXED)
        rate_type_current = application.get('rate_type_current', 'FIXED')
        rate_type_new = application.get('rate_type_new', 'FIXED')
        
        # Calculate NTB based on program
        if program_type == 'FHA':
            ntb_result = calculate_fha_ntb(
                old_note_rate=old_note_rate,
                new_note_rate=new_note_rate,
                old_annual_mip=old_annual_mip,
                new_annual_mip=new_annual_mip,
                old_monthly_pi=old_monthly_pi,
                new_monthly_pi=new_monthly_pi,
                old_loan_term_months=360,  # Assume 30-year
                new_loan_term_months=new_loan_term,
                rate_type_current=rate_type_current,
                rate_type_new=rate_type_new
            )
        elif program_type == 'VA':
            ntb_result = calculate_va_ntb(
                old_note_rate=old_note_rate,
                new_note_rate=new_note_rate,
                old_monthly_pi=old_monthly_pi,
                new_monthly_pi=new_monthly_pi,
                rate_type_current=rate_type_current,
                rate_type_new=rate_type_new,
                term_reduction=new_loan_term < 360,
                energy_improvement=False
            )
        else:
            return f"""**Application:** {refi_id}

### NTB Calculation Error

❌ **Error:** Unknown program type: {program_type}

Unable to calculate NTB. Program must be FHA or VA."""
        
        ntb = json.loads(ntb_result)
        
        # Extract key values
        ntb_passed = ntb.get('ntb_confirmed', False)
        scenario = ntb.get('scenario', 'UNKNOWN')
        
        # Calculate savings
        rate_reduction = old_note_rate - new_note_rate
        monthly_savings = old_monthly_pi - new_monthly_pi
        
        # FHA combined rate calculation
        if program_type == 'FHA':
            old_combined = old_note_rate + old_annual_mip
            new_combined = new_note_rate + new_annual_mip
            combined_reduction = old_combined - new_combined
        else:
            old_combined = old_note_rate
            new_combined = new_note_rate
            combined_reduction = rate_reduction
        
        # Format response
        agent = create_ntb_calculator_agent()
        
        prompt = f"""Format this NTB calculation data into your standard report format:

**APPLICATION:**
- Refi ID: {refi_id}
- Program: {program_type}
- Scenario: {scenario}
- Borrower: {application.get('borrower_name', 'Unknown')}

**RATE COMPARISON:**

| Metric | Old Loan | New Loan | Change |
|--------|----------|----------|--------|
| Note Rate | {old_note_rate:.3f}% | {new_note_rate:.3f}% | {rate_reduction:+.3f}% |
| Annual MIP (FHA) | {old_annual_mip:.2f}% | {new_annual_mip:.2f}% | {old_annual_mip - new_annual_mip:+.2f}% |
| Combined Rate | {old_combined:.3f}% | {new_combined:.3f}% | {combined_reduction:+.3f}% |
| Monthly P&I | ${old_monthly_pi:,.2f} | ${new_monthly_pi:,.2f} | ${monthly_savings:+,.2f} |
| Monthly PITI | ${old_monthly_piti:,.2f} | ${new_monthly_piti:,.2f} | ${old_monthly_piti - new_monthly_piti:+,.2f} |

**NTB THRESHOLD:**
{ntb.get('threshold', 'N/A')}

**NTB CALCULATIONS:**
- Rate Reduction: {rate_reduction:.3f}%
- Combined Rate Reduction (FHA): {combined_reduction:.3f}%
- Monthly P&I Savings: ${monthly_savings:,.2f}

**NTB STATUS:**
{'✅ NET TANGIBLE BENEFIT CONFIRMED' if ntb_passed else '❌ NET TANGIBLE BENEFIT NOT CONFIRMED'}

Format this into your standard NTB calculation report."""

        response = agent(prompt)
        return str(response)
        
    except Exception as e:
        return f"""**Application:** {refi_id}

### NTB Calculation Error

- **Status:** ⚠️ ERROR
- **Error:** {str(e)}
- **Action Required:** Manual NTB calculation needed"""
