"""
Hard stop eligibility rules for Streamline Government Refinances.
Implements Section B1 (FHA) and C1 (VA) requirements.
"""

import json
from typing import Dict, Any, List
from strands import tool


@tool
def check_fha_hard_stops(
    existing_loan_type: str,
    fha_case_number: str,
    loan_is_current: bool,
    cash_to_borrower: float
) -> str:
    """
    Check FHA Streamline hard stop requirements (Section B1).
    
    Args:
        existing_loan_type: Type of existing loan (should be 'FHA')
        fha_case_number: FHA case number for the existing loan
        loan_is_current: Whether the loan is current (not delinquent)
        cash_to_borrower: Amount of cash back to borrower at closing
    
    Returns:
        JSON string with hard stop validation results
    """
    results = []
    all_passed = True
    
    # B1.1 - Existing loan is FHA-insured
    fha_verified = existing_loan_type.upper() == 'FHA' and bool(fha_case_number)
    results.append({
        "requirement": "Existing loan is FHA-insured",
        "section": "B1.1",
        "passed": fha_verified,
        "evidence": f"Loan type: {existing_loan_type}, Case #: {fha_case_number or 'None'}",
        "failure_reason": None if fha_verified else "Loan is not FHA-insured or missing case number"
    })
    if not fha_verified:
        all_passed = False
    
    # B1.2 - No cash-out (max $500)
    cash_out_ok = cash_to_borrower <= 500
    results.append({
        "requirement": "No cash-out (max $500 incidental)",
        "section": "B1.2",
        "passed": cash_out_ok,
        "evidence": f"Cash to borrower: ${cash_to_borrower:,.2f}",
        "failure_reason": None if cash_out_ok else f"Cash back ${cash_to_borrower:,.2f} exceeds $500 limit"
    })
    if not cash_out_ok:
        all_passed = False
    
    # B1.3 - Loan is current
    results.append({
        "requirement": "Loan is current (not delinquent)",
        "section": "B1.3",
        "passed": loan_is_current,
        "evidence": f"Loan current: {loan_is_current}",
        "failure_reason": None if loan_is_current else "Loan is delinquent"
    })
    if not loan_is_current:
        all_passed = False
    
    # B1.4 - Manual underwriting (always true for streamline process)
    results.append({
        "requirement": "Manual underwriting to FHA Streamline requirements",
        "section": "B1.4",
        "passed": True,
        "evidence": "Using FHA Streamline manual underwriting process",
        "failure_reason": None
    })
    
    return json.dumps({
        "program": "FHA_STREAMLINE",
        "section": "B1",
        "all_passed": all_passed,
        "eligible": all_passed,
        "results": results,
        "summary": "All FHA hard stops passed" if all_passed else "FHA hard stop(s) failed - INELIGIBLE"
    }, indent=2)


@tool
def check_va_hard_stops(
    existing_loan_type: str,
    va_loan_number: str,
    same_property: bool,
    cash_to_borrower: float,
    allowable_fees_only: bool
) -> str:
    """
    Check VA IRRRL hard stop requirements (Section C1).
    
    Args:
        existing_loan_type: Type of existing loan (should be 'VA')
        va_loan_number: VA loan number for the existing loan
        same_property: Whether IRRRL is for the same property
        cash_to_borrower: Amount of cash back to Veteran at closing
        allowable_fees_only: Whether only allowable fees are included
    
    Returns:
        JSON string with hard stop validation results
    """
    results = []
    all_passed = True
    
    # C1.1 - Existing loan is VA-guaranteed
    va_verified = existing_loan_type.upper() == 'VA' and bool(va_loan_number)
    results.append({
        "requirement": "Existing loan is VA-guaranteed",
        "section": "C1.1",
        "passed": va_verified,
        "evidence": f"Loan type: {existing_loan_type}, VA Loan #: {va_loan_number or 'None'}",
        "failure_reason": None if va_verified else "Loan is not VA-guaranteed or missing VA loan number"
    })
    if not va_verified:
        all_passed = False
    
    # C1.2 - Same property
    results.append({
        "requirement": "IRRRL secured by same property",
        "section": "C1.2",
        "passed": same_property,
        "evidence": f"Same property: {same_property}",
        "failure_reason": None if same_property else "IRRRL must be for the same property as existing loan"
    })
    if not same_property:
        all_passed = False
    
    # C1.3 - No improper cash-out
    # VA allows rounding to nearest dollar, so small amounts are OK
    cash_out_ok = cash_to_borrower <= 1  # Allow up to $1 for rounding
    results.append({
        "requirement": "No improper cash-out (per VA Form 26-8923)",
        "section": "C1.3",
        "passed": cash_out_ok,
        "evidence": f"Cash to Veteran: ${cash_to_borrower:,.2f}",
        "failure_reason": None if cash_out_ok else f"Cash back ${cash_to_borrower:,.2f} not allowed for IRRRL"
    })
    if not cash_out_ok:
        all_passed = False
    
    # C1.4 - Allowable costs only
    results.append({
        "requirement": "Only allowable fees/costs included",
        "section": "C1.4",
        "passed": allowable_fees_only,
        "evidence": f"Allowable fees only: {allowable_fees_only}",
        "failure_reason": None if allowable_fees_only else "Non-allowable fees included in loan"
    })
    if not allowable_fees_only:
        all_passed = False
    
    return json.dumps({
        "program": "VA_IRRRL",
        "section": "C1",
        "all_passed": all_passed,
        "eligible": all_passed,
        "results": results,
        "summary": "All VA hard stops passed" if all_passed else "VA hard stop(s) failed - INELIGIBLE"
    }, indent=2)


@tool
def check_cash_out_limit(
    program_type: str,
    cash_to_borrower: float
) -> str:
    """
    Check cash-out limits for both FHA and VA programs.
    
    Args:
        program_type: 'FHA' or 'VA'
        cash_to_borrower: Amount of cash back at closing
    
    Returns:
        JSON string with cash-out validation
    """
    if program_type.upper() == 'FHA':
        limit = 500.0
        passed = cash_to_borrower <= limit
        rule = "FHA Streamline allows max $500 incidental cash back"
    elif program_type.upper() == 'VA':
        limit = 1.0  # Rounding tolerance
        passed = cash_to_borrower <= limit
        rule = "VA IRRRL prohibits cash-out (rounding to nearest dollar allowed)"
    else:
        return json.dumps({
            "error": f"Unknown program type: {program_type}",
            "valid_types": ["FHA", "VA"]
        })
    
    return json.dumps({
        "program": program_type.upper(),
        "cash_to_borrower": cash_to_borrower,
        "limit": limit,
        "passed": passed,
        "rule": rule,
        "message": "Cash-out within limits" if passed else f"Cash-out ${cash_to_borrower:,.2f} exceeds ${limit:,.2f} limit"
    }, indent=2)


def check_borrower_changes(
    old_borrowers: List[str],
    new_borrowers: List[str],
    change_reason: str = None
) -> Dict[str, Any]:
    """
    Check FHA borrower change rules (Section B3).
    
    Args:
        old_borrowers: List of borrowers on existing loan
        new_borrowers: List of borrowers on new loan
        change_reason: Reason for change (DEATH, DIVORCE, or None)
    
    Returns:
        Dictionary with borrower change analysis
    """
    old_set = set(old_borrowers)
    new_set = set(new_borrowers)
    
    removed = old_set - new_set
    added = new_set - old_set
    
    # Determine if non-credit-qualifying is allowed
    if old_set == new_set:
        # No changes - non-credit-qualifying allowed
        non_credit_qualifying_allowed = True
        credit_qualifying_required = False
        reason = "All borrowers remain on loan"
    elif removed and not added:
        # Only removals - check for permitted exceptions
        if change_reason in ['DEATH', 'DIVORCE']:
            non_credit_qualifying_allowed = True
            credit_qualifying_required = False
            reason = f"Borrower removal permitted due to {change_reason}"
        else:
            non_credit_qualifying_allowed = False
            credit_qualifying_required = True
            reason = "Borrower removal without permitted exception requires credit-qualifying"
    else:
        # Additions or other changes - credit-qualifying required
        non_credit_qualifying_allowed = False
        credit_qualifying_required = True
        reason = "Borrower additions require credit-qualifying underwriting"
    
    return {
        "old_borrowers": list(old_set),
        "new_borrowers": list(new_set),
        "borrowers_removed": list(removed),
        "borrowers_added": list(added),
        "change_reason": change_reason,
        "non_credit_qualifying_allowed": non_credit_qualifying_allowed,
        "credit_qualifying_required": credit_qualifying_required,
        "determination_reason": reason
    }
