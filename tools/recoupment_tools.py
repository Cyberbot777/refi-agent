"""
VA IRRRL Recoupment and PITI trigger tools.
Implements Section C4 (36-month recoupment) and C5 (20% PITI trigger).
"""

import json
from typing import Optional
from strands import tool


@tool
def calculate_va_recoupment(
    total_closing_costs: float,
    taxes_amount: float,
    escrow_deposits: float,
    va_funding_fee: float,
    old_monthly_pi: float,
    new_monthly_pi: float
) -> str:
    """
    Calculate VA IRRRL fee recoupment (Section C4).
    
    Statutory requirement: All fees must recoup within 36 months.
    
    EXCLUDE from recoupment calculation (numerator):
    - Taxes
    - Escrow deposits
    - VA Funding Fee
    
    Formula: Recoupment Months = Recoupable Fees / Monthly P&I Savings
    
    Args:
        total_closing_costs: Total closing costs
        taxes_amount: Tax amounts to exclude
        escrow_deposits: Escrow deposits to exclude
        va_funding_fee: VA funding fee to exclude
        old_monthly_pi: Old monthly P&I payment
        new_monthly_pi: New monthly P&I payment
    
    Returns:
        JSON string with recoupment calculation and pass/fail
    """
    # Calculate recoupable fees (exclude prohibited items)
    excluded_fees = taxes_amount + escrow_deposits + va_funding_fee
    recoupable_fees = total_closing_costs - excluded_fees
    
    # Calculate monthly P&I savings
    monthly_savings = old_monthly_pi - new_monthly_pi
    
    # Handle edge cases
    if monthly_savings <= 0:
        # P&I doesn't decrease - special handling required
        return json.dumps({
            "program": "VA_IRRRL",
            "section": "C4",
            "fee_breakdown": {
                "total_closing_costs": total_closing_costs,
                "excluded_taxes": taxes_amount,
                "excluded_escrow": escrow_deposits,
                "excluded_va_funding_fee": va_funding_fee,
                "total_excluded": excluded_fees,
                "recoupable_fees": recoupable_fees
            },
            "payment_comparison": {
                "old_monthly_pi": old_monthly_pi,
                "new_monthly_pi": new_monthly_pi,
                "monthly_savings": monthly_savings
            },
            "recoupment_months": None,
            "maximum_allowed": 36,
            "passed": False,
            "special_case": True,
            "message": "P&I does not decrease - see VA guidance for limited exceptions (term reduction, etc.)",
            "summary": "RECOUPMENT CANNOT BE CALCULATED - No P&I savings"
        }, indent=2)
    
    # Calculate recoupment period
    recoupment_months = recoupable_fees / monthly_savings
    recoupment_months = round(recoupment_months, 1)
    
    # Check against 36-month statutory limit
    passed = recoupment_months <= 36
    
    return json.dumps({
        "program": "VA_IRRRL",
        "section": "C4",
        "fee_breakdown": {
            "total_closing_costs": total_closing_costs,
            "excluded_taxes": taxes_amount,
            "excluded_escrow": escrow_deposits,
            "excluded_va_funding_fee": va_funding_fee,
            "total_excluded": excluded_fees,
            "recoupable_fees": recoupable_fees
        },
        "payment_comparison": {
            "old_monthly_pi": old_monthly_pi,
            "new_monthly_pi": new_monthly_pi,
            "monthly_savings": monthly_savings
        },
        "calculation": f"${recoupable_fees:,.2f} ÷ ${monthly_savings:,.2f} = {recoupment_months} months",
        "recoupment_months": recoupment_months,
        "maximum_allowed": 36,
        "passed": passed,
        "special_case": False,
        "summary": f"Recoupment {'PASSES' if passed else 'FAILS'} - {recoupment_months} months vs 36 month limit"
    }, indent=2)


@tool
def check_piti_increase_trigger(
    old_monthly_piti: float,
    new_monthly_piti: float
) -> str:
    """
    Check VA IRRRL 20% PITI increase trigger (Section C5).
    
    If total monthly payment (PITI) increases by 20% or more,
    lender must verify Veteran's ability to pay.
    
    Args:
        old_monthly_piti: Old total monthly payment (P&I + T&I)
        new_monthly_piti: New total monthly payment (P&I + T&I)
    
    Returns:
        JSON string with PITI trigger evaluation
    """
    # Calculate PITI change
    piti_change = new_monthly_piti - old_monthly_piti
    
    # Calculate percentage increase
    if old_monthly_piti > 0:
        piti_increase_percent = (piti_change / old_monthly_piti) * 100
    else:
        piti_increase_percent = 0 if piti_change == 0 else 100
    
    piti_increase_percent = round(piti_increase_percent, 2)
    
    # Check if 20% trigger is hit
    trigger_threshold = 20.0
    triggered = piti_increase_percent >= trigger_threshold
    
    if triggered:
        action_required = "MANUAL REVIEW REQUIRED: Verify Veteran's ability to pay and include lender certification"
        status = "TRIGGERED"
    elif piti_increase_percent > 0:
        action_required = "PITI increases but under 20% - standard processing"
        status = "NOT_TRIGGERED"
    else:
        action_required = "PITI decreases or stays same - no additional verification needed"
        status = "NOT_TRIGGERED"
    
    return json.dumps({
        "program": "VA_IRRRL",
        "section": "C5",
        "payments": {
            "old_monthly_piti": old_monthly_piti,
            "new_monthly_piti": new_monthly_piti,
            "piti_change": round(piti_change, 2),
            "piti_increase_percent": piti_increase_percent
        },
        "trigger": {
            "threshold": f"{trigger_threshold}%",
            "triggered": triggered,
            "status": status
        },
        "action_required": action_required,
        "summary": f"20% PITI Trigger: {status} ({piti_increase_percent}% change)"
    }, indent=2)


def calculate_recoupment_breakdown(
    closing_costs_detail: dict,
    old_monthly_pi: float,
    new_monthly_pi: float
) -> dict:
    """
    Detailed recoupment calculation with itemized fees.
    
    Args:
        closing_costs_detail: Dictionary with itemized closing costs
        old_monthly_pi: Old monthly P&I
        new_monthly_pi: New monthly P&I
    
    Returns:
        Dictionary with detailed recoupment breakdown
    """
    # Fees to INCLUDE in recoupment
    includable_fees = [
        'origination_fee',
        'discount_points',
        'appraisal_fee',
        'credit_report_fee',
        'title_insurance',
        'title_search',
        'recording_fees',
        'survey_fee',
        'attorney_fees',
        'flood_certification',
        'other_lender_fees'
    ]
    
    # Fees to EXCLUDE (per VA Circular 26-19-22 Exhibit B)
    excludable_fees = [
        'taxes',
        'property_taxes',
        'escrow_deposits',
        'prepaid_interest',
        'va_funding_fee',
        'insurance_premiums'
    ]
    
    included_total = 0
    excluded_total = 0
    included_items = {}
    excluded_items = {}
    
    for fee_name, amount in closing_costs_detail.items():
        if amount and amount > 0:
            if fee_name.lower() in includable_fees:
                included_items[fee_name] = amount
                included_total += amount
            elif fee_name.lower() in excludable_fees:
                excluded_items[fee_name] = amount
                excluded_total += amount
            else:
                # Unknown fees default to included
                included_items[fee_name] = amount
                included_total += amount
    
    monthly_savings = old_monthly_pi - new_monthly_pi
    
    if monthly_savings > 0:
        recoupment_months = included_total / monthly_savings
    else:
        recoupment_months = None
    
    return {
        "included_fees": included_items,
        "excluded_fees": excluded_items,
        "included_total": included_total,
        "excluded_total": excluded_total,
        "monthly_pi_savings": monthly_savings,
        "recoupment_months": round(recoupment_months, 1) if recoupment_months else None,
        "passes_36_month_test": recoupment_months is not None and recoupment_months <= 36
    }
