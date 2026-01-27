"""
Package Validator Agent
Validates document completeness and readability for refinance applications.
Implements Section A of the Streamline Government Refinance Checklist.
"""

import json
from strands import Agent, tool
from strands.models import BedrockModel

from config.prompts import PACKAGE_VALIDATOR_PROMPT
from utils.config_loader import get_model_config


def create_package_validator_agent() -> Agent:
    """Create a fast package validator agent with NO tools (formatting only)."""
    model_config = get_model_config()
    
    model = BedrockModel(
        model_id=model_config["specialist_model"],
        temperature=model_config["temperature"],
    )
    
    # NO TOOLS = single LLM call, just formatting
    agent = Agent(
        model=model,
        system_prompt=PACKAGE_VALIDATOR_PROMPT,
        tools=[],
        callback_handler=None
    )
    
    return agent


@tool
def package_validator(refi_id: str) -> str:
    """
    Validate document completeness for a refinance application (Section A).
    Pre-fetches all data, then uses single LLM call for analysis.
    
    Args:
        refi_id: The refinance application ID (e.g., "REFI-001")
    
    Returns:
        Formatted package validation report
    """
    try:
        # Import database tools
        from tools.refi_database_tools import get_refi_application, get_refi_documents
        
        # PRE-FETCH ALL DATA (fast SQL, no LLM)
        app_data = get_refi_application(refi_id)
        docs_data = get_refi_documents(refi_id)
        
        # Parse JSON responses
        application = json.loads(app_data) if app_data else {}
        documents = json.loads(docs_data) if docs_data else {}
        
        # Check for errors
        if application.get('error'):
            return f"""**Application:** {refi_id}

### Package Validation Error

❌ **Error:** {application.get('error')}

Unable to retrieve application data. Please verify the application ID."""
        
        # Extract key information
        program_type = application.get('existing_loan_type', 'UNKNOWN')
        borrower_name = application.get('borrower_name', 'Unknown')
        property_address = application.get('property_address', 'Unknown')
        
        # Get document list
        doc_list = documents.get('documents', [])
        doc_types = documents.get('document_types_present', [])
        missing_docs = documents.get('missing_required', [])
        
        # Required documents per Section A
        required_docs = {
            'PAYOFF_STATEMENT': 'Payoff statement for loan being refinanced',
            'PAYMENT_HISTORY': '12-month mortgage payment history/ledger',
            'CLOSING_DISCLOSURE': 'Closing disclosure / fee worksheet',
            'TITLE_EVIDENCE': 'Title/vesting evidence (prelim title)',
            'INSURANCE_DECLARATION': 'Hazard insurance declarations page',
            'BORROWER_ID': 'Borrower identity documentation'
        }
        
        # Build document status
        doc_status = []
        for doc_type, description in required_docs.items():
            present = doc_type in doc_types
            verified = any(d.get('verified') for d in doc_list if d.get('document_type') == doc_type)
            doc_status.append({
                'type': doc_type,
                'description': description,
                'present': present,
                'verified': verified
            })
        
        present_count = sum(1 for d in doc_status if d['present'])
        total_required = len(required_docs)
        is_complete = present_count == total_required
        
        # SINGLE LLM CALL - format the pre-computed data
        agent = create_package_validator_agent()
        
        prompt = f"""Format this package validation data into your standard report format:

**APPLICATION DATA:**
- Refi ID: {refi_id}
- Program Type: {program_type}
- Borrower: {borrower_name}
- Property: {property_address}

**DOCUMENT STATUS:**
{chr(10).join(f"- {d['type']}: {'✅ Present' if d['present'] else '❌ Missing'} {'(Verified)' if d['verified'] else ''}" for d in doc_status)}

**SUMMARY:**
- Documents Present: {present_count}/{total_required}
- Package Status: {'✅ COMPLETE' if is_complete else '❌ INCOMPLETE'}
- Missing Documents: {', '.join(missing_docs) if missing_docs else 'None'}

Format this into your standard package validation report."""

        response = agent(prompt)
        return str(response)
        
    except Exception as e:
        return f"""**Application:** {refi_id}

### Package Validation

| Document | Status | Details |
|----------|--------|---------|
| System Error | ❌ | Unable to retrieve documents |

### Summary
- **Status:** ⚠️ VALIDATION ERROR
- **Error:** {str(e)}
- **Action Required:** Manual document review needed

*Technical issue encountered during validation. Please verify documents manually.*"""
