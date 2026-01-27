"""
Pytest configuration and fixtures for Streamline Refi Agent tests.
"""

import os
import pytest
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set test environment
os.environ["ENV"] = "local"


@pytest.fixture
def sample_fha_application():
    """Sample FHA Streamline application data."""
    return {
        "refi_id": "REFI-FHA-TEST",
        "borrower_name": "Test Borrower",
        "property_address": "123 Test St, Test City, CA 90210",
        "existing_loan_type": "FHA",
        "fha_case_number": "123-4567890",
        "original_closing_date": "2025-01-15",
        "first_payment_due_date": "2025-03-01",
        "current_note_rate": 6.5,
        "current_annual_mip": 0.55,
        "current_monthly_pi": 1896.20,
        "current_monthly_piti": 2350.00,
        "new_note_rate": 5.875,
        "new_annual_mip": 0.55,
        "new_monthly_pi": 1768.45,
        "new_monthly_piti": 2220.00,
        "cash_to_borrower": 250.00
    }


@pytest.fixture
def sample_va_application():
    """Sample VA IRRRL application data."""
    return {
        "refi_id": "REFI-VA-TEST",
        "borrower_name": "Test Veteran",
        "property_address": "456 Veteran Way, Test City, CA 90210",
        "existing_loan_type": "VA",
        "va_loan_number": "VA-2024-TEST",
        "original_closing_date": "2025-02-01",
        "first_payment_due_date": "2025-04-01",
        "current_note_rate": 6.75,
        "current_monthly_pi": 1947.50,
        "current_monthly_piti": 2400.00,
        "new_note_rate": 6.00,
        "new_monthly_pi": 1798.65,
        "new_monthly_piti": 2250.00,
        "total_closing_costs": 6500.00,
        "va_funding_fee": 2500.00,
        "taxes_amount": 500.00,
        "escrow_deposits": 800.00,
        "cash_to_borrower": 0.00
    }


@pytest.fixture
def sample_payment_history():
    """Sample 12-month payment history (all on-time)."""
    from datetime import date, timedelta
    
    payments = []
    base_date = date(2025, 1, 1)
    
    for i in range(12):
        payment_date = base_date + timedelta(days=30 * i)
        payments.append({
            "payment_date": str(payment_date),
            "payment_amount": 2350.00,
            "days_late": 0,
            "status": "CURRENT",
            "forbearance_flag": False
        })
    
    return {
        "payments": payments,
        "total_payments": 12,
        "on_time_payments": 12,
        "late_30_payments": 0,
        "late_60_plus_payments": 0,
        "consecutive_on_time": 12
    }
