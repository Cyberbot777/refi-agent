"""
FHA Mortgage Insurance Premium (MIP) Rates Configuration.

POC NOTE: These rates are hardcoded for the proof-of-concept.
In production, MIP rates should come from:
  1. The Loan Origination System (LOS) - already calculated per loan
  2. An internal MIP lookup API that stays current with HUD updates
  3. Input fields where the underwriter enters verified values

Current rates are based on HUD guidelines as of January 2026.
See: https://www.hud.gov/program_offices/housing/comp/premiums/sfpcmort
"""

from typing import Dict, Any


# Annual MIP rates by loan term and LTV
# Format: (term_years, ltv_threshold) -> annual_mip_rate
MIP_RATES: Dict[str, Any] = {
    # Standard FHA loans (new purchases/refis)
    "standard": {
        # Loans > 15 years
        "long_term": {
            "high_ltv": {  # LTV > 95%
                "annual_mip": 0.55,
                "description": "Loans >15 years, LTV >95%"
            },
            "standard_ltv": {  # LTV <= 95%
                "annual_mip": 0.50,
                "description": "Loans >15 years, LTV ≤95%"
            }
        },
        # Loans <= 15 years
        "short_term": {
            "high_ltv": {  # LTV > 90%
                "annual_mip": 0.40,
                "description": "Loans ≤15 years, LTV >90%"
            },
            "standard_ltv": {  # LTV <= 90%
                "annual_mip": 0.15,
                "description": "Loans ≤15 years, LTV ≤90%"
            }
        }
    },
    
    # FHA Streamline Refinance - uses same MIP structure
    # The existing loan's MIP rate is known from servicer data
    "streamline_refi": {
        "annual_mip": 0.55,  # Most common rate (>15yr, >90% LTV)
        "description": "Default for streamline calculations"
    },
    
    # Upfront MIP (UFMIP)
    "upfront": {
        "standard": 1.75,  # 1.75% for most FHA loans
        "streamline_within_3_years": 0.01,  # Reduced UFMIP if refinancing within 3 years
        "description": "Upfront MIP financed into loan amount"
    }
}


def get_mip_rate(
    loan_term_years: int = 30,
    ltv_ratio: float = 95.0,
    is_streamline: bool = True
) -> float:
    """
    Get the annual MIP rate based on loan characteristics.
    
    Args:
        loan_term_years: Loan term in years (typically 15 or 30)
        ltv_ratio: Loan-to-Value ratio as percentage
        is_streamline: Whether this is a streamline refinance
    
    Returns:
        Annual MIP rate as a percentage (e.g., 0.55 for 0.55%)
    
    Note:
        For production, this should be replaced with actual MIP data
        from the loan file or pricing engine.
    """
    if is_streamline:
        # For streamline refis, use the default rate
        # In production, this would come from the loan data
        return MIP_RATES["streamline_refi"]["annual_mip"]
    
    # Determine term category
    if loan_term_years > 15:
        term_key = "long_term"
        ltv_threshold = 95.0
    else:
        term_key = "short_term"
        ltv_threshold = 90.0
    
    # Determine LTV category
    ltv_key = "high_ltv" if ltv_ratio > ltv_threshold else "standard_ltv"
    
    return MIP_RATES["standard"][term_key][ltv_key]["annual_mip"]


def get_upfront_mip_rate(is_streamline_within_3_years: bool = False) -> float:
    """
    Get the upfront MIP (UFMIP) rate.
    
    Args:
        is_streamline_within_3_years: True if refinancing within 3 years of original FHA loan
    
    Returns:
        UFMIP rate as a percentage (e.g., 1.75 for 1.75%)
    """
    if is_streamline_within_3_years:
        return MIP_RATES["upfront"]["streamline_within_3_years"]
    return MIP_RATES["upfront"]["standard"]
