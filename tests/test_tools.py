"""
Unit tests for Streamline Refi Agent tools.
"""

import json
import pytest
from datetime import date


class TestSeasoningTools:
    """Tests for seasoning calculation tools."""
    
    def test_fha_seasoning_passes(self):
        """Test FHA seasoning passes with valid dates."""
        from tools.seasoning_tools import calculate_seasoning
        
        result = calculate_seasoning(
            original_closing_date="2025-01-15",
            first_payment_due_date="2025-03-01",
            refi_closing_date="2026-01-27",  # Today
            total_payments_made=10,
            program_type="FHA"
        )
        
        data = json.loads(result)
        assert data["seasoning_met"] is True
        assert data["calculations"]["days_since_closing"] >= 210
        assert data["calculations"]["total_payments_made"] >= 6
    
    def test_fha_seasoning_fails_days(self):
        """Test FHA seasoning fails with insufficient days."""
        from tools.seasoning_tools import calculate_seasoning
        
        result = calculate_seasoning(
            original_closing_date="2025-10-01",  # Only ~4 months ago
            first_payment_due_date="2025-11-01",
            refi_closing_date="2026-01-27",
            total_payments_made=3,
            program_type="FHA"
        )
        
        data = json.loads(result)
        assert data["seasoning_met"] is False
    
    def test_va_seasoning_passes(self):
        """Test VA IRRRL seasoning passes."""
        from tools.seasoning_tools import calculate_seasoning
        
        result = calculate_seasoning(
            original_closing_date="2025-02-01",
            first_payment_due_date="2025-04-01",
            refi_closing_date="2026-01-27",
            total_payments_made=9,
            program_type="VA"
        )
        
        data = json.loads(result)
        assert data["seasoning_met"] is True
    
    def test_payment_history_validation_passes(self):
        """Test payment history validation passes."""
        from tools.seasoning_tools import validate_payment_history
        
        payments = {
            "payments": [
                {"days_late": 0, "forbearance_flag": False} for _ in range(12)
            ]
        }
        
        result = validate_payment_history(
            payments_json=json.dumps(payments),
            program_type="FHA"
        )
        
        data = json.loads(result)
        assert data["passed"] is True
        assert data["on_time_payments"] == 12


class TestNTBTools:
    """Tests for Net Tangible Benefit calculation tools."""
    
    def test_fha_ntb_passes(self):
        """Test FHA NTB passes with rate reduction."""
        from tools.ntb_tools import calculate_fha_ntb
        
        result = calculate_fha_ntb(
            old_note_rate=6.5,
            new_note_rate=5.875,
            old_annual_mip=0.55,
            new_annual_mip=0.55,
            old_monthly_pi=1896.20,
            new_monthly_pi=1768.45,
            old_loan_term_months=360,
            new_loan_term_months=360
        )
        
        data = json.loads(result)
        assert data["ntb_confirmed"] is True
        assert data["calculations"]["combined_rate_reduction"] > 0
    
    def test_fha_ntb_fails_no_reduction(self):
        """Test FHA NTB fails with same rate."""
        from tools.ntb_tools import calculate_fha_ntb
        
        result = calculate_fha_ntb(
            old_note_rate=5.75,
            new_note_rate=5.75,  # Same rate
            old_annual_mip=0.55,
            new_annual_mip=0.55,
            old_monthly_pi=1751.95,
            new_monthly_pi=1751.95,
            old_loan_term_months=360,
            new_loan_term_months=360
        )
        
        data = json.loads(result)
        assert data["ntb_confirmed"] is False
    
    def test_va_ntb_passes(self):
        """Test VA NTB passes with 0.75% reduction."""
        from tools.ntb_tools import calculate_va_ntb
        
        result = calculate_va_ntb(
            old_note_rate=6.75,
            new_note_rate=6.00,  # 0.75% reduction (> 0.50% required)
            old_monthly_pi=1947.50,
            new_monthly_pi=1798.65
        )
        
        data = json.loads(result)
        assert data["ntb_confirmed"] is True
        assert data["calculations"]["rate_reduction"] >= 0.50
    
    def test_va_ntb_fails_insufficient_reduction(self):
        """Test VA NTB fails with only 0.40% reduction."""
        from tools.ntb_tools import calculate_va_ntb
        
        result = calculate_va_ntb(
            old_note_rate=6.25,
            new_note_rate=5.85,  # Only 0.40% reduction (< 0.50% required)
            old_monthly_pi=1845.00,
            new_monthly_pi=1775.00
        )
        
        data = json.loads(result)
        assert data["ntb_confirmed"] is False


class TestRecoupmentTools:
    """Tests for VA recoupment calculation tools."""
    
    def test_recoupment_passes(self):
        """Test recoupment passes within 36 months."""
        from tools.recoupment_tools import calculate_va_recoupment
        
        result = calculate_va_recoupment(
            total_closing_costs=6500.00,
            taxes_amount=500.00,
            escrow_deposits=800.00,
            va_funding_fee=2500.00,
            old_monthly_pi=1947.50,
            new_monthly_pi=1798.65  # ~$149 savings
        )
        # Recoupable: 6500 - 500 - 800 - 2500 = 2700
        # Recoupment: 2700 / 149 = ~18 months
        
        data = json.loads(result)
        assert data["passed"] is True
        assert data["recoupment_months"] <= 36
    
    def test_recoupment_fails(self):
        """Test recoupment fails when > 36 months."""
        from tools.recoupment_tools import calculate_va_recoupment
        
        result = calculate_va_recoupment(
            total_closing_costs=12000.00,
            taxes_amount=600.00,
            escrow_deposits=900.00,
            va_funding_fee=2800.00,
            old_monthly_pi=1896.20,
            new_monthly_pi=1810.50  # Only ~$86 savings
        )
        # Recoupable: 12000 - 600 - 900 - 2800 = 7700
        # Recoupment: 7700 / 86 = ~90 months
        
        data = json.loads(result)
        assert data["passed"] is False
        assert data["recoupment_months"] > 36
    
    def test_piti_trigger_not_triggered(self):
        """Test PITI trigger not triggered with small increase."""
        from tools.recoupment_tools import check_piti_increase_trigger
        
        result = check_piti_increase_trigger(
            old_monthly_piti=2400.00,
            new_monthly_piti=2250.00  # Decrease
        )
        
        data = json.loads(result)
        assert data["trigger"]["triggered"] is False
    
    def test_piti_trigger_triggered(self):
        """Test PITI trigger triggered with 20%+ increase."""
        from tools.recoupment_tools import check_piti_increase_trigger
        
        result = check_piti_increase_trigger(
            old_monthly_piti=2200.00,
            new_monthly_piti=2700.00  # 22.7% increase
        )
        
        data = json.loads(result)
        assert data["trigger"]["triggered"] is True


class TestRulesTools:
    """Tests for eligibility rules tools."""
    
    def test_fha_hard_stops_pass(self):
        """Test FHA hard stops all pass."""
        from tools.refi_rules import check_fha_hard_stops
        
        result = check_fha_hard_stops(
            existing_loan_type="FHA",
            fha_case_number="123-4567890",
            loan_is_current=True,
            cash_to_borrower=250.00
        )
        
        data = json.loads(result)
        assert data["eligible"] is True
        assert data["all_passed"] is True
    
    def test_fha_hard_stops_fail_cash_out(self):
        """Test FHA hard stops fail on cash-out."""
        from tools.refi_rules import check_fha_hard_stops
        
        result = check_fha_hard_stops(
            existing_loan_type="FHA",
            fha_case_number="123-4567890",
            loan_is_current=True,
            cash_to_borrower=600.00  # Exceeds $500 limit
        )
        
        data = json.loads(result)
        assert data["eligible"] is False
    
    def test_va_hard_stops_pass(self):
        """Test VA hard stops all pass."""
        from tools.refi_rules import check_va_hard_stops
        
        result = check_va_hard_stops(
            existing_loan_type="VA",
            va_loan_number="VA-2024-123456",
            same_property=True,
            cash_to_borrower=0.00,
            allowable_fees_only=True
        )
        
        data = json.loads(result)
        assert data["eligible"] is True
        assert data["all_passed"] is True
