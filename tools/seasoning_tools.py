"""
Seasoning and payment history validation tools.
Implements Section B2 (FHA) and C2 (VA) requirements.
"""

import json
from datetime import date, datetime
from typing import List, Dict, Any, Optional
from strands import tool


def _parse_date(date_input) -> date:
    """Parse a date from string or date object."""
    if isinstance(date_input, date):
        return date_input
    if isinstance(date_input, datetime):
        return date_input.date()
    if isinstance(date_input, str):
        return datetime.strptime(date_input, "%Y-%m-%d").date()
    raise ValueError(f"Cannot parse date: {date_input}")


@tool
def calculate_seasoning(
    original_closing_date: str,
    first_payment_due_date: str,
    refi_closing_date: str,
    total_payments_made: int,
    program_type: str
) -> str:
    """
    Calculate seasoning requirements for FHA Streamline (B2) or VA IRRRL (C2).
    
    Args:
        original_closing_date: Closing date of existing loan (YYYY-MM-DD)
        first_payment_due_date: First payment due date of existing loan (YYYY-MM-DD)
        refi_closing_date: Expected closing date for refinance (YYYY-MM-DD)
        total_payments_made: Number of payments made on existing loan
        program_type: 'FHA' or 'VA'
    
    Returns:
        JSON string with seasoning validation results
    """
    try:
        closing = _parse_date(original_closing_date)
        first_payment = _parse_date(first_payment_due_date)
        refi_date = _parse_date(refi_closing_date)
    except ValueError as e:
        return json.dumps({"error": f"Date parsing error: {str(e)}"})
    
    # Calculate days since closing
    days_since_closing = (refi_date - closing).days
    
    # Calculate months since first payment
    months_since_first_payment = (
        (refi_date.year - first_payment.year) * 12 + 
        (refi_date.month - first_payment.month)
    )
    
    # For VA: days from first payment due date to IRRRL closing
    days_from_first_payment = (refi_date - first_payment).days
    
    results = []
    all_passed = True
    
    if program_type.upper() == 'FHA':
        # FHA B2.1 - At least 6 payments made
        payments_ok = total_payments_made >= 6
        results.append({
            "requirement": "At least 6 payments made",
            "section": "B2.1",
            "required": 6,
            "actual": total_payments_made,
            "passed": payments_ok,
            "evidence": f"{total_payments_made} payments made"
        })
        if not payments_ok:
            all_passed = False
        
        # FHA B2.2 - At least 6 months since first payment due date
        months_ok = months_since_first_payment >= 6
        results.append({
            "requirement": "At least 6 months since first payment due date",
            "section": "B2.2",
            "required": 6,
            "actual": months_since_first_payment,
            "passed": months_ok,
            "evidence": f"{months_since_first_payment} months since first payment"
        })
        if not months_ok:
            all_passed = False
        
        # FHA B2.3 - At least 210 days since closing
        days_ok = days_since_closing >= 210
        results.append({
            "requirement": "At least 210 days since closing date",
            "section": "B2.3",
            "required": 210,
            "actual": days_since_closing,
            "passed": days_ok,
            "evidence": f"{days_since_closing} days since closing"
        })
        if not days_ok:
            all_passed = False
            
    elif program_type.upper() == 'VA':
        # VA C2.1 - First payment due date at least 210 days prior
        days_ok = days_from_first_payment >= 210
        results.append({
            "requirement": "First payment due date at least 210 days prior to IRRRL closing",
            "section": "C2.1",
            "required": 210,
            "actual": days_from_first_payment,
            "passed": days_ok,
            "evidence": f"{days_from_first_payment} days from first payment to IRRRL closing"
        })
        if not days_ok:
            all_passed = False
        
        # VA C2.2 - At least 6 consecutive payments
        payments_ok = total_payments_made >= 6
        results.append({
            "requirement": "At least 6 consecutive monthly payments made",
            "section": "C2.2",
            "required": 6,
            "actual": total_payments_made,
            "passed": payments_ok,
            "evidence": f"{total_payments_made} payments made"
        })
        if not payments_ok:
            all_passed = False
    else:
        return json.dumps({"error": f"Unknown program type: {program_type}"})
    
    return json.dumps({
        "program": program_type.upper(),
        "section": "B2" if program_type.upper() == 'FHA' else "C2",
        "all_passed": all_passed,
        "seasoning_met": all_passed,
        "results": results,
        "calculations": {
            "days_since_closing": days_since_closing,
            "months_since_first_payment": months_since_first_payment,
            "days_from_first_payment": days_from_first_payment,
            "total_payments_made": total_payments_made
        },
        "summary": "Seasoning requirements met" if all_passed else "Seasoning requirements NOT met"
    }, indent=2)


@tool
def validate_payment_history(
    payments_json: str,
    program_type: str
) -> str:
    """
    Validate 12-month payment history for late payment rules.
    
    Args:
        payments_json: JSON string with payment history array
        program_type: 'FHA' or 'VA'
    
    Returns:
        JSON string with payment history validation
    """
    try:
        data = json.loads(payments_json)
        payments = data.get('payments', []) if isinstance(data, dict) else data
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid payments JSON"})
    
    if not payments:
        return json.dumps({
            "error": "No payment history provided",
            "passed": False
        })
    
    # Analyze payment history
    total = len(payments)
    on_time = 0
    late_30 = 0
    late_60 = 0
    late_90_plus = 0
    consecutive_on_time = 0
    forbearance_count = 0
    
    for p in payments:
        days_late = p.get('days_late', 0)
        forbearance = p.get('forbearance_flag', False)
        
        if forbearance:
            forbearance_count += 1
        
        if days_late == 0 or days_late is None:
            on_time += 1
            consecutive_on_time += 1
        elif days_late < 30:
            on_time += 1  # Less than 30 is still considered on-time
            consecutive_on_time += 1
        elif days_late < 60:
            late_30 += 1
            consecutive_on_time = 0  # Reset consecutive
        elif days_late < 90:
            late_60 += 1
            consecutive_on_time = 0
        else:
            late_90_plus += 1
            consecutive_on_time = 0
    
    # Determine if payment history passes
    # FHA: Typically no more than 1 x 30-day late in last 12 months
    # VA: Need 6 consecutive on-time payments
    
    if program_type.upper() == 'FHA':
        # FHA allows some flexibility but generally:
        # - No 60+ day lates
        # - At most 1 x 30-day late
        passed = late_60 == 0 and late_90_plus == 0 and late_30 <= 1
        rule_description = "No 60+ day lates; at most one 30-day late in last 12 months"
    else:  # VA
        # VA needs 6 consecutive payments
        passed = consecutive_on_time >= 6
        rule_description = "At least 6 consecutive on-time payments required"
    
    return json.dumps({
        "program": program_type.upper(),
        "total_payments_reviewed": total,
        "on_time_payments": on_time,
        "late_30_payments": late_30,
        "late_60_payments": late_60,
        "late_90_plus_payments": late_90_plus,
        "consecutive_on_time": consecutive_on_time,
        "forbearance_months": forbearance_count,
        "passed": passed,
        "rule": rule_description,
        "summary": "Payment history acceptable" if passed else "Payment history issues found"
    }, indent=2)


@tool
def check_forbearance_status(
    had_forbearance: bool,
    forbearance_end_date: Optional[str],
    post_forbearance_payments: int,
    program_type: str
) -> str:
    """
    Check forbearance completion and post-forbearance requirements.
    
    Args:
        had_forbearance: Whether the loan had a forbearance period
        forbearance_end_date: When forbearance ended (YYYY-MM-DD)
        post_forbearance_payments: Number of on-time payments after forbearance
        program_type: 'FHA' or 'VA'
    
    Returns:
        JSON string with forbearance validation
    """
    if not had_forbearance:
        return json.dumps({
            "had_forbearance": False,
            "applicable": False,
            "passed": True,
            "message": "No forbearance history - requirement not applicable"
        })
    
    # FHA typically requires 3-6 months of on-time payments post-forbearance
    # VA may have different requirements
    required_payments = 3  # Minimum post-forbearance payments
    
    passed = post_forbearance_payments >= required_payments
    
    return json.dumps({
        "had_forbearance": True,
        "forbearance_end_date": forbearance_end_date,
        "post_forbearance_payments": post_forbearance_payments,
        "required_payments": required_payments,
        "passed": passed,
        "program": program_type.upper(),
        "message": f"Post-forbearance requirement {'met' if passed else 'NOT met'}: {post_forbearance_payments}/{required_payments} payments"
    }, indent=2)
