"""
Net Tangible Benefit (NTB) calculation tools.
Implements Section B5 (FHA) and C3 (VA) requirements.
"""

import json
from typing import Optional
from strands import tool

from config.mip_rates import get_mip_rate


@tool
def calculate_combined_rate(
    note_rate: float,
    annual_mip: Optional[float] = None,
    loan_term_years: int = 30,
    ltv_ratio: float = 95.0
) -> str:
    """
    Calculate the combined rate (note rate + annual MIP) for FHA loans.
    
    Args:
        note_rate: The note interest rate as percentage (e.g., 6.5 for 6.5%)
        annual_mip: Annual MIP rate (if known), otherwise calculated
        loan_term_years: Loan term in years
        ltv_ratio: Loan-to-Value ratio as percentage
    
    Returns:
        JSON string with combined rate calculation
    """
    # If MIP not provided, look it up
    if annual_mip is None:
        annual_mip = get_mip_rate(loan_term_years, ltv_ratio, is_streamline=True)
    
    combined_rate = note_rate + annual_mip
    
    return json.dumps({
        "note_rate": note_rate,
        "annual_mip": annual_mip,
        "combined_rate": round(combined_rate, 3),
        "calculation": f"{note_rate}% + {annual_mip}% = {combined_rate:.3f}%"
    }, indent=2)


@tool
def calculate_fha_ntb(
    old_note_rate: float,
    new_note_rate: float,
    old_annual_mip: float,
    new_annual_mip: float,
    old_monthly_pi: float,
    new_monthly_pi: float,
    old_loan_term_months: int,
    new_loan_term_months: int,
    rate_type_current: str = "FIXED",
    rate_type_new: str = "FIXED"
) -> str:
    """
    Calculate FHA Streamline Net Tangible Benefit (Section B5).
    
    NTB requires the combined rate (note rate + annual MIP) to decrease
    for most scenarios.
    
    Args:
        old_note_rate: Current note rate (percentage)
        new_note_rate: New note rate (percentage)
        old_annual_mip: Current annual MIP rate (percentage)
        new_annual_mip: New annual MIP rate (percentage)
        old_monthly_pi: Current monthly P&I payment
        new_monthly_pi: New monthly P&I payment
        old_loan_term_months: Current loan term in months
        new_loan_term_months: New loan term in months
        rate_type_current: Current rate type (FIXED or ARM)
        rate_type_new: New rate type (FIXED or ARM)
    
    Returns:
        JSON string with NTB calculation and pass/fail status
    """
    # Calculate combined rates
    old_combined = old_note_rate + old_annual_mip
    new_combined = new_note_rate + new_annual_mip
    combined_reduction = old_combined - new_combined
    
    # Calculate note rate change
    note_rate_reduction = old_note_rate - new_note_rate
    
    # Calculate payment change
    monthly_savings = old_monthly_pi - new_monthly_pi
    
    # Determine scenario
    if rate_type_current == "FIXED" and rate_type_new == "FIXED":
        scenario = "FIXED_TO_FIXED"
    elif rate_type_current == "FIXED" and rate_type_new == "ARM":
        scenario = "FIXED_TO_ARM"
    elif rate_type_current == "ARM" and rate_type_new == "FIXED":
        scenario = "ARM_TO_FIXED"
    else:
        scenario = "ARM_TO_ARM"
    
    # Check for term reduction
    term_reduction = old_loan_term_months > new_loan_term_months
    
    # Determine NTB pass/fail based on scenario
    if scenario == "FIXED_TO_FIXED":
        # Combined rate must decrease
        passed = combined_reduction > 0
        threshold = "Combined rate must decrease"
    elif scenario == "FIXED_TO_ARM":
        # Generally must show significant benefit - combined rate decrease
        passed = combined_reduction > 0
        threshold = "Combined rate must decrease (Fixed-to-ARM)"
    elif scenario == "ARM_TO_FIXED":
        # Converting to fixed provides stability benefit
        # Combined rate should still ideally decrease but may be more lenient
        passed = combined_reduction >= 0 or term_reduction
        threshold = "Combined rate must not increase significantly (ARM-to-Fixed provides stability)"
    else:
        passed = combined_reduction > 0
        threshold = "Combined rate must decrease"
    
    # Term reduction can be NTB even if rate doesn't change much
    if term_reduction and not passed:
        # Check if it's a term reduction scenario
        passed = True
        threshold = f"Term reduction from {old_loan_term_months} to {new_loan_term_months} months provides NTB"
    
    return json.dumps({
        "program": "FHA_STREAMLINE",
        "section": "B5",
        "scenario": scenario,
        "old_loan": {
            "note_rate": old_note_rate,
            "annual_mip": old_annual_mip,
            "combined_rate": round(old_combined, 3),
            "monthly_pi": old_monthly_pi,
            "term_months": old_loan_term_months
        },
        "new_loan": {
            "note_rate": new_note_rate,
            "annual_mip": new_annual_mip,
            "combined_rate": round(new_combined, 3),
            "monthly_pi": new_monthly_pi,
            "term_months": new_loan_term_months
        },
        "calculations": {
            "note_rate_reduction": round(note_rate_reduction, 3),
            "combined_rate_reduction": round(combined_reduction, 3),
            "monthly_pi_savings": round(monthly_savings, 2),
            "term_reduction": term_reduction
        },
        "threshold": threshold,
        "passed": passed,
        "ntb_confirmed": passed,
        "summary": "Net Tangible Benefit CONFIRMED" if passed else "Net Tangible Benefit NOT confirmed"
    }, indent=2)


@tool
def calculate_va_ntb(
    old_note_rate: float,
    new_note_rate: float,
    old_monthly_pi: float,
    new_monthly_pi: float,
    rate_type_current: str = "FIXED",
    rate_type_new: str = "FIXED",
    term_reduction: bool = False,
    energy_improvement: bool = False
) -> str:
    """
    Calculate VA IRRRL Net Tangible Benefit (Section C3).
    
    VA NTB Requirements:
    - Fixed-to-Fixed: Rate must be at least 0.50% lower
    - Fixed-to-ARM: Rate must be at least 2.00% lower
    - P&I must decrease (unless exception applies)
    
    Args:
        old_note_rate: Current note rate (percentage)
        new_note_rate: New note rate (percentage)
        old_monthly_pi: Current monthly P&I payment
        new_monthly_pi: New monthly P&I payment
        rate_type_current: Current rate type (FIXED or ARM)
        rate_type_new: New rate type (FIXED or ARM)
        term_reduction: Whether this is a term reduction refinance
        energy_improvement: Whether this includes energy improvements
    
    Returns:
        JSON string with NTB calculation and pass/fail status
    """
    # Calculate rate reduction
    rate_reduction = old_note_rate - new_note_rate
    
    # Calculate payment change
    monthly_savings = old_monthly_pi - new_monthly_pi
    pi_decreases = new_monthly_pi < old_monthly_pi
    
    # Determine scenario and required threshold
    if rate_type_current == "FIXED" and rate_type_new == "FIXED":
        scenario = "FIXED_TO_FIXED"
        required_reduction = 0.50
        threshold_description = "Rate must be at least 0.50% lower"
    elif rate_type_current == "FIXED" and rate_type_new == "ARM":
        scenario = "FIXED_TO_ARM"
        required_reduction = 2.00
        threshold_description = "Rate must be at least 2.00% lower"
    elif rate_type_current == "ARM":
        scenario = "ARM_REFINANCE"
        required_reduction = 0.0  # ARM refinances have different rules
        threshold_description = "ARM refinance - rate reduction not required"
    else:
        scenario = "OTHER"
        required_reduction = 0.50
        threshold_description = "Rate must decrease"
    
    # Check rate reduction threshold
    rate_threshold_met = rate_reduction >= required_reduction
    
    # Check P&I decrease requirement
    # P&I must decrease unless exception applies
    pi_exception_applies = term_reduction or energy_improvement or scenario == "ARM_REFINANCE"
    pi_requirement_met = pi_decreases or pi_exception_applies
    
    # Overall NTB determination
    passed = rate_threshold_met and pi_requirement_met
    
    return json.dumps({
        "program": "VA_IRRRL",
        "section": "C3",
        "scenario": scenario,
        "old_loan": {
            "note_rate": old_note_rate,
            "monthly_pi": old_monthly_pi,
            "rate_type": rate_type_current
        },
        "new_loan": {
            "note_rate": new_note_rate,
            "monthly_pi": new_monthly_pi,
            "rate_type": rate_type_new
        },
        "calculations": {
            "rate_reduction": round(rate_reduction, 3),
            "required_reduction": required_reduction,
            "monthly_pi_savings": round(monthly_savings, 2),
            "pi_decreases": pi_decreases
        },
        "thresholds": {
            "rate_threshold": threshold_description,
            "rate_threshold_met": rate_threshold_met,
            "pi_decrease_required": not pi_exception_applies,
            "pi_requirement_met": pi_requirement_met,
            "exceptions_applied": {
                "term_reduction": term_reduction,
                "energy_improvement": energy_improvement
            }
        },
        "passed": passed,
        "ntb_confirmed": passed,
        "summary": "Net Tangible Benefit CONFIRMED" if passed else "Net Tangible Benefit NOT confirmed"
    }, indent=2)
