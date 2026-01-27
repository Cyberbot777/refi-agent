"""
Program Router Agent
Determines whether application follows FHA Streamline or VA IRRRL workflow.
Routes to appropriate checklist sections based on existing loan type.
"""

import json
from strands import Agent, tool
from strands.models import BedrockModel

from config.prompts import PROGRAM_ROUTER_PROMPT
from utils.config_loader import get_model_config


def create_program_router_agent() -> Agent:
    """Create a fast program router agent with NO tools (formatting only)."""
    model_config = get_model_config()
    
    model = BedrockModel(
        model_id=model_config["specialist_model"],
        temperature=model_config["temperature"],
    )
    
    agent = Agent(
        model=model,
        system_prompt=PROGRAM_ROUTER_PROMPT,
        tools=[],
        callback_handler=None
    )
    
    return agent


@tool
def program_router(refi_id: str) -> str:
    """
    Determine the refinance program (FHA Streamline or VA IRRRL) and route workflow.
    
    Args:
        refi_id: The refinance application ID (e.g., "REFI-001")
    
    Returns:
        Program routing determination with workflow path
    """
    try:
        # Import database tools
        from tools.refi_database_tools import get_refi_application
        
        # PRE-FETCH DATA
        app_data = get_refi_application(refi_id)
        application = json.loads(app_data) if app_data else {}
        
        if application.get('error'):
            return f"""**Application:** {refi_id}

### Program Routing Error

❌ **Error:** {application.get('error')}

Unable to determine program type."""
        
        # Extract loan type information
        existing_loan_type = application.get('existing_loan_type', 'UNKNOWN').upper()
        fha_case_number = application.get('fha_case_number', '')
        va_loan_number = application.get('va_loan_number', '')
        borrower_name = application.get('borrower_name', 'Unknown')
        
        # Determine program
        if existing_loan_type == 'FHA' and fha_case_number:
            program = 'FHA_STREAMLINE'
            sections = 'B1-B5'
            reference_number = fha_case_number
            special_requirements = [
                'Combined rate (note rate + MIP) calculation required',
                'Maximum $500 cash back',
                'Non-credit-qualifying vs credit-qualifying determination'
            ]
        elif existing_loan_type == 'VA' and va_loan_number:
            program = 'VA_IRRRL'
            sections = 'C1-C6'
            reference_number = va_loan_number
            special_requirements = [
                '36-month fee recoupment test required',
                'No cash-out to Veteran',
                '20% PITI trigger evaluation',
                'VA Form 26-8923 required'
            ]
        else:
            program = 'UNKNOWN'
            sections = 'N/A'
            reference_number = 'N/A'
            special_requirements = ['Unable to determine program - verify loan type']
        
        # Format response
        agent = create_program_router_agent()
        
        prompt = f"""Format this program routing data into your standard report format:

**APPLICATION:**
- Refi ID: {refi_id}
- Borrower: {borrower_name}

**LOAN IDENTIFICATION:**
- Existing Loan Type: {existing_loan_type}
- FHA Case Number: {fha_case_number or 'N/A'}
- VA Loan Number: {va_loan_number or 'N/A'}

**ROUTING DETERMINATION:**
- Program: {program}
- Checklist Sections: {sections}
- Reference Number: {reference_number}

**SPECIAL REQUIREMENTS:**
{chr(10).join(f'- {req}' for req in special_requirements)}

Format this into your standard program routing report with the workflow path."""

        response = agent(prompt)
        return str(response)
        
    except Exception as e:
        return f"""**Application:** {refi_id}

### Program Routing Error

- **Status:** ⚠️ ERROR
- **Error:** {str(e)}
- **Action Required:** Manual program determination needed"""
