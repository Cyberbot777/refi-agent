"""
Known-input / known-output tests for the decision engine.
Based on the 8 existing DB test cases plus edge-case scenarios.
"""

import pytest
from datetime import date
from decimal import Decimal

from scripts.lib.decision_engine import Scenario, evaluate

D = Decimal
EVAL = date(2026, 2, 10)


# FHA SCENARIOS 

class TestFHADecisions:
    def test_fha001_approved(self):
        """REFI-FHA-001: All checks pass → APPROVED."""
        s = Scenario(
            program="FHA",
            borrower_name="Michael Johnson",
            property_address="123 Oak Street, Irvine, CA 92618",
            fha_case_number="123-4567890",
            closing_date=date(2025, 3, 15),
            first_payment_date=date(2025, 5, 1),
            eval_date=EVAL,
            current_note_rate=D("6.500"),
            current_annual_mip=D("0.550"),
            new_note_rate=D("5.875"),
            new_annual_mip=D("0.550"),
            current_monthly_pi=D("1896.20"),
            current_monthly_piti=D("2350.00"),
            new_monthly_pi=D("1768.45"),
            new_monthly_piti=D("2220.00"),
            current_loan_balance=D("298500.00"),
            new_loan_amount=D("300000.00"),
            cash_to_borrower=D("250.00"),
            total_payments=8,
            late_30_day=0,
            late_60_plus=0,
            consecutive_on_time=8,
            loan_status="CURRENT",
        )
        result = evaluate(s)
        assert result.decision == "APPROVED"

    def test_fha002_denied_seasoning(self):
        """REFI-FHA-002: 4 months old + PENDING status → DENIED."""
        s = Scenario(
            program="FHA",
            borrower_name="Sarah Williams",
            property_address="456 Pine Avenue, Costa Mesa, CA 92627",
            fha_case_number="234-5678901",
            closing_date=date(2025, 10, 1),
            first_payment_date=date(2025, 11, 1),
            eval_date=EVAL,
            current_note_rate=D("7.000"),
            current_annual_mip=D("0.550"),
            new_note_rate=D("6.250"),
            new_annual_mip=D("0.550"),
            current_monthly_pi=D("1995.91"),
            current_monthly_piti=D("2450.00"),
            new_monthly_pi=D("1845.00"),
            new_monthly_piti=D("2300.00"),
            current_loan_balance=D("299000.00"),
            new_loan_amount=D("300000.00"),
            cash_to_borrower=D("0.00"),
            total_payments=4,
            late_30_day=0,
            late_60_plus=0,
            consecutive_on_time=4,
            loan_status="PENDING",
        )
        result = evaluate(s)
        assert result.decision == "DENIED"
        # Both B1 (status) and B2 (seasoning) should fail
        b1 = next(c for c in result.checks if c.name == "B1")
        b2 = next(c for c in result.checks if c.name == "B2")
        assert not b1.passed
        assert not b2.passed

    def test_fha003_denied_no_ntb(self):
        """REFI-FHA-003: Same rate, PENDING status → DENIED."""
        s = Scenario(
            program="FHA",
            borrower_name="Robert Chen",
            property_address="789 Maple Drive, Newport Beach, CA 92660",
            fha_case_number="345-6789012",
            closing_date=date(2025, 1, 15),
            first_payment_date=date(2025, 3, 1),
            eval_date=EVAL,
            current_note_rate=D("5.750"),
            current_annual_mip=D("0.550"),
            new_note_rate=D("5.750"),
            new_annual_mip=D("0.550"),
            current_monthly_pi=D("1751.95"),
            current_monthly_piti=D("2200.00"),
            new_monthly_pi=D("1751.95"),
            new_monthly_piti=D("2200.00"),
            current_loan_balance=D("300000.00"),
            new_loan_amount=D("302000.00"),
            cash_to_borrower=D("0.00"),
            total_payments=10,
            late_30_day=0,
            late_60_plus=0,
            consecutive_on_time=10,
            loan_status="PENDING",
        )
        result = evaluate(s)
        assert result.decision == "DENIED"
        b1 = next(c for c in result.checks if c.name == "B1")
        b5 = next(c for c in result.checks if c.name == "B5")
        assert not b1.passed  # PENDING status
        assert not b5.passed  # Same rate = 0% reduction

    def test_fha004_denied_pending_status(self):
        """REFI-FHA-004: loan_status PENDING → DENIED (B1 hard stop)."""
        s = Scenario(
            program="FHA",
            borrower_name="Jennifer Lopez",
            property_address="888 Sunrise Court, Laguna Beach, CA 92651",
            fha_case_number="456-7890123",
            closing_date=date(2025, 2, 1),
            first_payment_date=date(2025, 4, 1),
            eval_date=EVAL,
            current_note_rate=D("7.125"),
            current_annual_mip=D("0.550"),
            new_note_rate=D("6.375"),
            new_annual_mip=D("0.550"),
            current_monthly_pi=D("2024.81"),
            current_monthly_piti=D("2500.00"),
            new_monthly_pi=D("1876.50"),
            new_monthly_piti=D("2350.00"),
            current_loan_balance=D("300000.00"),
            new_loan_amount=D("302000.00"),
            cash_to_borrower=D("450.00"),
            total_payments=9,
            late_30_day=0,
            late_60_plus=0,
            consecutive_on_time=9,
            loan_status="PENDING",
        )
        result = evaluate(s)
        assert result.decision == "DENIED"

    def test_fha_approved_with_conditions_cash(self):
        """FHA with $450 cash (edge case) and all else passing → AWC."""
        s = Scenario(
            program="FHA",
            borrower_name="Test Borrower",
            property_address="100 Test St, Irvine, CA 92618",
            fha_case_number="111-2222222",
            closing_date=date(2025, 3, 1),
            first_payment_date=date(2025, 5, 1),
            eval_date=EVAL,
            current_note_rate=D("7.000"),
            current_annual_mip=D("0.550"),
            new_note_rate=D("6.000"),
            new_annual_mip=D("0.550"),
            current_monthly_pi=D("2000.00"),
            current_monthly_piti=D("2500.00"),
            new_monthly_pi=D("1800.00"),
            new_monthly_piti=D("2300.00"),
            current_loan_balance=D("300000.00"),
            new_loan_amount=D("302000.00"),
            cash_to_borrower=D("450.00"),
            total_payments=8,
            late_30_day=0,
            late_60_plus=0,
            consecutive_on_time=8,
            loan_status="CURRENT",
        )
        result = evaluate(s)
        assert result.decision == "APPROVED WITH CONDITIONS"
        assert any("$450" in f for f in result.edge_case_flags)

    def test_fha_approved_with_conditions_1x_late(self):
        """FHA with 1x 30-day late → AWC."""
        s = Scenario(
            program="FHA",
            borrower_name="Test Borrower",
            property_address="100 Test St, Irvine, CA 92618",
            fha_case_number="111-3333333",
            closing_date=date(2025, 3, 1),
            first_payment_date=date(2025, 5, 1),
            eval_date=EVAL,
            current_note_rate=D("7.000"),
            current_annual_mip=D("0.550"),
            new_note_rate=D("6.000"),
            new_annual_mip=D("0.550"),
            current_monthly_pi=D("2000.00"),
            current_monthly_piti=D("2500.00"),
            new_monthly_pi=D("1800.00"),
            new_monthly_piti=D("2300.00"),
            current_loan_balance=D("300000.00"),
            new_loan_amount=D("302000.00"),
            cash_to_borrower=D("0.00"),
            total_payments=8,
            late_30_day=1,
            late_60_plus=0,
            consecutive_on_time=7,
            loan_status="CURRENT",
        )
        result = evaluate(s)
        assert result.decision == "APPROVED WITH CONDITIONS"
        assert any("30-day late" in f for f in result.edge_case_flags)

    def test_fha_denied_no_case_number(self):
        """FHA with missing case number → DENIED."""
        s = Scenario(
            program="FHA",
            borrower_name="Test Borrower",
            property_address="100 Test St, Irvine, CA 92618",
            fha_case_number=None,
            closing_date=date(2025, 3, 1),
            first_payment_date=date(2025, 5, 1),
            eval_date=EVAL,
            current_note_rate=D("7.000"),
            current_annual_mip=D("0.550"),
            new_note_rate=D("6.000"),
            new_annual_mip=D("0.550"),
            current_monthly_pi=D("2000.00"),
            current_monthly_piti=D("2500.00"),
            new_monthly_pi=D("1800.00"),
            new_monthly_piti=D("2300.00"),
            current_loan_balance=D("300000.00"),
            new_loan_amount=D("302000.00"),
            cash_to_borrower=D("0.00"),
            total_payments=8,
            loan_status="CURRENT",
        )
        result = evaluate(s)
        assert result.decision == "DENIED"

    def test_fha_denied_excessive_cash(self):
        """FHA with $600 cash to borrower → DENIED."""
        s = Scenario(
            program="FHA",
            borrower_name="Test Borrower",
            property_address="100 Test St, Irvine, CA 92618",
            fha_case_number="111-4444444",
            closing_date=date(2025, 3, 1),
            first_payment_date=date(2025, 5, 1),
            eval_date=EVAL,
            current_note_rate=D("7.000"),
            current_annual_mip=D("0.550"),
            new_note_rate=D("6.000"),
            new_annual_mip=D("0.550"),
            current_monthly_pi=D("2000.00"),
            current_monthly_piti=D("2500.00"),
            new_monthly_pi=D("1800.00"),
            new_monthly_piti=D("2300.00"),
            current_loan_balance=D("300000.00"),
            new_loan_amount=D("302000.00"),
            cash_to_borrower=D("600.00"),
            total_payments=8,
            loan_status="CURRENT",
        )
        result = evaluate(s)
        assert result.decision == "DENIED"


# VA SCENARIOS

class TestVADecisions:
    def test_va001_approved(self):
        """REFI-VA-001: All checks pass → APPROVED."""
        s = Scenario(
            program="VA",
            borrower_name="James Thompson",
            property_address="321 Veterans Way, San Diego, CA 92101",
            va_loan_number="VA-2024-123456",
            closing_date=date(2025, 2, 1),
            first_payment_date=date(2025, 4, 1),
            eval_date=EVAL,
            current_note_rate=D("6.750"),
            new_note_rate=D("6.000"),
            current_monthly_pi=D("1947.50"),
            current_monthly_piti=D("2400.00"),
            new_monthly_pi=D("1798.65"),
            new_monthly_piti=D("2250.00"),
            current_loan_balance=D("298000.00"),
            new_loan_amount=D("300000.00"),
            total_closing_costs=D("6500.00"),
            va_funding_fee=D("2500.00"),
            taxes_amount=D("500.00"),
            escrow_deposits=D("800.00"),
            cash_to_borrower=D("0.00"),
            total_payments=9,
            consecutive_on_time=9,
            loan_status="CURRENT",
        )
        result = evaluate(s)
        assert result.decision == "APPROVED"

    def test_va002_denied_ntb(self):
        """REFI-VA-002: 0.40% rate reduction < 0.50% → DENIED."""
        s = Scenario(
            program="VA",
            borrower_name="Patricia Davis",
            property_address="555 Liberty Lane, Oceanside, CA 92054",
            va_loan_number="VA-2024-234567",
            closing_date=date(2025, 3, 1),
            first_payment_date=date(2025, 5, 1),
            eval_date=EVAL,
            current_note_rate=D("6.250"),
            new_note_rate=D("5.850"),
            current_monthly_pi=D("1845.00"),
            current_monthly_piti=D("2300.00"),
            new_monthly_pi=D("1775.00"),
            new_monthly_piti=D("2230.00"),
            current_loan_balance=D("299000.00"),
            new_loan_amount=D("300000.00"),
            total_closing_costs=D("5500.00"),
            va_funding_fee=D("2200.00"),
            taxes_amount=D("450.00"),
            escrow_deposits=D("700.00"),
            cash_to_borrower=D("0.00"),
            total_payments=8,
            consecutive_on_time=8,
            loan_status="PENDING",
        )
        result = evaluate(s)
        assert result.decision == "DENIED"
        c3 = next(c for c in result.checks if c.name == "C3")
        assert not c3.passed

    def test_va003_denied_recoupment(self):
        """REFI-VA-003: Recoupment 89.8 months > 36 → DENIED."""
        s = Scenario(
            program="VA",
            borrower_name="William Martinez",
            property_address="777 Freedom Blvd, Carlsbad, CA 92008",
            va_loan_number="VA-2024-345678",
            closing_date=date(2025, 1, 15),
            first_payment_date=date(2025, 3, 1),
            eval_date=EVAL,
            current_note_rate=D("6.500"),
            new_note_rate=D("5.875"),
            current_monthly_pi=D("1896.20"),
            current_monthly_piti=D("2350.00"),
            new_monthly_pi=D("1810.50"),
            new_monthly_piti=D("2260.00"),
            current_loan_balance=D("299500.00"),
            new_loan_amount=D("302000.00"),
            total_closing_costs=D("12000.00"),
            va_funding_fee=D("2800.00"),
            taxes_amount=D("600.00"),
            escrow_deposits=D("900.00"),
            cash_to_borrower=D("0.00"),
            total_payments=10,
            consecutive_on_time=10,
            loan_status="PENDING",
        )
        result = evaluate(s)
        assert result.decision == "DENIED"

    def test_va004_needs_review(self):
        """REFI-VA-004: PITI +22.7% → NEEDS REVIEW."""
        s = Scenario(
            program="VA",
            borrower_name="David Wilson",
            property_address="999 Honor Drive, El Cajon, CA 92020",
            va_loan_number="VA-2024-456789",
            closing_date=date(2025, 1, 1),
            first_payment_date=date(2025, 3, 1),
            eval_date=EVAL,
            current_note_rate=D("7.000"),
            new_note_rate=D("6.250"),
            current_monthly_pi=D("1995.91"),
            current_monthly_piti=D("2200.00"),
            new_monthly_pi=D("1845.00"),
            new_monthly_piti=D("2700.00"),
            current_loan_balance=D("299000.00"),
            new_loan_amount=D("301000.00"),
            total_closing_costs=D("5800.00"),
            va_funding_fee=D("2300.00"),
            taxes_amount=D("480.00"),
            escrow_deposits=D("750.00"),
            cash_to_borrower=D("0.00"),
            total_payments=10,
            consecutive_on_time=10,
            loan_status="CURRENT",
        )
        result = evaluate(s)
        assert result.decision == "NEEDS REVIEW"
        c5 = next(c for c in result.checks if c.name == "C5")
        assert c5.details["triggered"] is True
        assert D(c5.details["piti_delta_pct"]) == D("22.7")

    def test_va_approved_with_conditions_recoupment(self):
        """VA with recoupment at 32 months (28-36 range) → AWC."""
        s = Scenario(
            program="VA",
            borrower_name="Test Veteran",
            property_address="100 Test St, San Diego, CA 92101",
            va_loan_number="VA-2025-111111",
            closing_date=date(2025, 3, 1),
            first_payment_date=date(2025, 5, 1),
            eval_date=EVAL,
            current_note_rate=D("7.000"),
            new_note_rate=D("6.000"),
            current_monthly_pi=D("1900.00"),
            current_monthly_piti=D("2300.00"),
            new_monthly_pi=D("1800.00"),
            new_monthly_piti=D("2200.00"),
            current_loan_balance=D("300000.00"),
            new_loan_amount=D("302000.00"),
            # Recoupable: 5400 - 2000 - 300 - 300 = 2800
            # Savings: 1900-1800 = 100/mo → 2800/100 = 28.0 months
            total_closing_costs=D("5400.00"),
            va_funding_fee=D("2000.00"),
            taxes_amount=D("300.00"),
            escrow_deposits=D("300.00"),
            cash_to_borrower=D("0.00"),
            total_payments=8,
            consecutive_on_time=8,
            loan_status="CURRENT",
        )
        result = evaluate(s)
        assert result.decision == "APPROVED WITH CONDITIONS"
        assert any("Recoupment" in f for f in result.edge_case_flags)

    def test_va_denied_no_va_loan_number(self):
        """VA with missing loan number → DENIED."""
        s = Scenario(
            program="VA",
            borrower_name="Test Veteran",
            property_address="100 Test St, San Diego, CA 92101",
            va_loan_number=None,
            closing_date=date(2025, 3, 1),
            first_payment_date=date(2025, 5, 1),
            eval_date=EVAL,
            current_note_rate=D("7.000"),
            new_note_rate=D("6.000"),
            current_monthly_pi=D("1900.00"),
            current_monthly_piti=D("2300.00"),
            new_monthly_pi=D("1800.00"),
            new_monthly_piti=D("2200.00"),
            current_loan_balance=D("300000.00"),
            new_loan_amount=D("302000.00"),
            total_closing_costs=D("5000.00"),
            va_funding_fee=D("2000.00"),
            taxes_amount=D("300.00"),
            escrow_deposits=D("300.00"),
            cash_to_borrower=D("0.00"),
            total_payments=8,
            consecutive_on_time=8,
            loan_status="CURRENT",
        )
        result = evaluate(s)
        assert result.decision == "DENIED"

    def test_va_denied_cash_out(self):
        """VA with $100 cash to borrower → DENIED (improper cash out)."""
        s = Scenario(
            program="VA",
            borrower_name="Test Veteran",
            property_address="100 Test St, San Diego, CA 92101",
            va_loan_number="VA-2025-222222",
            closing_date=date(2025, 3, 1),
            first_payment_date=date(2025, 5, 1),
            eval_date=EVAL,
            current_note_rate=D("7.000"),
            new_note_rate=D("6.000"),
            current_monthly_pi=D("1900.00"),
            current_monthly_piti=D("2300.00"),
            new_monthly_pi=D("1800.00"),
            new_monthly_piti=D("2200.00"),
            current_loan_balance=D("300000.00"),
            new_loan_amount=D("302000.00"),
            total_closing_costs=D("5000.00"),
            va_funding_fee=D("2000.00"),
            taxes_amount=D("300.00"),
            escrow_deposits=D("300.00"),
            cash_to_borrower=D("100.00"),
            total_payments=8,
            consecutive_on_time=8,
            loan_status="CURRENT",
        )
        result = evaluate(s)
        assert result.decision == "DENIED"

    def test_va_arm_to_fixed_auto_pass(self):
        """VA ARM-to-Fixed: NTB auto-pass regardless of rate reduction."""
        s = Scenario(
            program="VA",
            borrower_name="ARM Veteran",
            property_address="200 ARM St, San Diego, CA 92101",
            va_loan_number="VA-2025-333333",
            closing_date=date(2025, 3, 1),
            first_payment_date=date(2025, 5, 1),
            eval_date=EVAL,
            current_note_rate=D("6.500"),
            new_note_rate=D("6.400"),  # Only 0.10% reduction
            rate_type_current="ARM",
            rate_type_new="FIXED",
            current_monthly_pi=D("1900.00"),
            current_monthly_piti=D("2300.00"),
            new_monthly_pi=D("1750.00"),
            new_monthly_piti=D("2150.00"),
            current_loan_balance=D("300000.00"),
            new_loan_amount=D("302000.00"),
            total_closing_costs=D("4000.00"),
            va_funding_fee=D("2000.00"),
            taxes_amount=D("300.00"),
            escrow_deposits=D("300.00"),
            cash_to_borrower=D("0.00"),
            total_payments=8,
            consecutive_on_time=8,
            loan_status="CURRENT",
        )
        result = evaluate(s)
        # Should pass NTB (auto-pass for ARM-to-Fixed)
        c3 = next(c for c in result.checks if c.name == "C3")
        assert c3.passed
        assert result.decision in ("APPROVED", "APPROVED WITH CONDITIONS")

    def test_va_fixed_to_arm_needs_2pct(self):
        """VA Fixed-to-ARM: needs >= 2.00% reduction."""
        s = Scenario(
            program="VA",
            borrower_name="ARM Veteran 2",
            property_address="300 Fixed St, San Diego, CA 92101",
            va_loan_number="VA-2025-444444",
            closing_date=date(2025, 3, 1),
            first_payment_date=date(2025, 5, 1),
            eval_date=EVAL,
            current_note_rate=D("7.000"),
            new_note_rate=D("5.500"),  # 1.50% — not enough
            rate_type_current="FIXED",
            rate_type_new="ARM",
            current_monthly_pi=D("1900.00"),
            current_monthly_piti=D("2300.00"),
            new_monthly_pi=D("1700.00"),
            new_monthly_piti=D("2100.00"),
            current_loan_balance=D("300000.00"),
            new_loan_amount=D("302000.00"),
            total_closing_costs=D("4000.00"),
            va_funding_fee=D("2000.00"),
            taxes_amount=D("300.00"),
            escrow_deposits=D("300.00"),
            cash_to_borrower=D("0.00"),
            total_payments=8,
            consecutive_on_time=8,
            loan_status="CURRENT",
        )
        result = evaluate(s)
        assert result.decision == "DENIED"
        c3 = next(c for c in result.checks if c.name == "C3")
        assert not c3.passed

    def test_va_fixed_to_arm_passes_at_2pct(self):
        """VA Fixed-to-ARM: exactly 2.00% reduction → passes."""
        s = Scenario(
            program="VA",
            borrower_name="ARM Veteran 3",
            property_address="400 Fixed St, San Diego, CA 92101",
            va_loan_number="VA-2025-555555",
            closing_date=date(2025, 3, 1),
            first_payment_date=date(2025, 5, 1),
            eval_date=EVAL,
            current_note_rate=D("7.000"),
            new_note_rate=D("5.000"),  # 2.00% exactly
            rate_type_current="FIXED",
            rate_type_new="ARM",
            current_monthly_pi=D("1900.00"),
            current_monthly_piti=D("2300.00"),
            new_monthly_pi=D("1600.00"),
            new_monthly_piti=D("2000.00"),
            current_loan_balance=D("300000.00"),
            new_loan_amount=D("302000.00"),
            total_closing_costs=D("3500.00"),
            va_funding_fee=D("2000.00"),
            taxes_amount=D("300.00"),
            escrow_deposits=D("300.00"),
            cash_to_borrower=D("0.00"),
            total_payments=8,
            consecutive_on_time=8,
            loan_status="CURRENT",
        )
        result = evaluate(s)
        c3 = next(c for c in result.checks if c.name == "C3")
        assert c3.passed
