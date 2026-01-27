"""
Tools module for Streamline Government Refinance Agent.
Contains database queries, calculation tools, and validation logic.
"""

from tools.refi_database_tools import (
    get_refi_application,
    get_payment_history,
    get_refi_documents,
    save_refi_decision,
)
from tools.refi_rules import (
    check_fha_hard_stops,
    check_va_hard_stops,
    check_cash_out_limit,
)
from tools.seasoning_tools import (
    calculate_seasoning,
    validate_payment_history,
    check_forbearance_status,
)
from tools.ntb_tools import (
    calculate_fha_ntb,
    calculate_va_ntb,
    calculate_combined_rate,
)
from tools.recoupment_tools import (
    calculate_va_recoupment,
    check_piti_increase_trigger,
)

__all__ = [
    # Database
    "get_refi_application",
    "get_payment_history",
    "get_refi_documents",
    "save_refi_decision",
    # Rules
    "check_fha_hard_stops",
    "check_va_hard_stops",
    "check_cash_out_limit",
    # Seasoning
    "calculate_seasoning",
    "validate_payment_history",
    "check_forbearance_status",
    # NTB
    "calculate_fha_ntb",
    "calculate_va_ntb",
    "calculate_combined_rate",
    # Recoupment
    "calculate_va_recoupment",
    "check_piti_increase_trigger",
]
