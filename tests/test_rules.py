"""Unit tests for scripts/lib/rules.py — every rule function with Decimal."""

import pytest
from datetime import date
from decimal import Decimal

from scripts.lib.rules import (
    days_since_closing,
    months_since_first_payment,
    combined_rate,
    rate_reduction,
    recoupable_costs,
    monthly_savings,
    recoupment_months,
    piti_delta_pct,
)

EVAL_DATE = date(2026, 2, 10)
D = Decimal  # shorthand


# --- days_since_closing ---

class TestDaysSinceClosing:
    def test_well_seasoned(self):
        # 2025-03-15 → 2026-02-10 = 332 days
        assert days_since_closing(date(2025, 3, 15), EVAL_DATE) == 332

    def test_under_210(self):
        # 2025-10-01 → 2026-02-10 = 132 days
        assert days_since_closing(date(2025, 10, 1), EVAL_DATE) == 132

    def test_exactly_210(self):
        # 210 days before 2026-02-10 is 2025-07-15
        assert days_since_closing(date(2025, 7, 15), EVAL_DATE) == 210

    def test_same_day(self):
        assert days_since_closing(EVAL_DATE, EVAL_DATE) == 0


# --- months_since_first_payment ---

class TestMonthsSinceFirstPayment:
    def test_well_seasoned(self):
        # 2025-05-01 → 2026-02-10 = 9 months
        assert months_since_first_payment(date(2025, 5, 1), EVAL_DATE) == 9

    def test_under_six(self):
        # 2025-11-01 → 2026-02-10 = 3 months
        assert months_since_first_payment(date(2025, 11, 1), EVAL_DATE) == 3

    def test_exactly_six(self):
        # 2025-08-10 → 2026-02-10 = 6 months
        assert months_since_first_payment(date(2025, 8, 10), EVAL_DATE) == 6


# --- combined_rate ---

class TestCombinedRate:
    def test_typical_fha(self):
        assert combined_rate("6.500", "0.550") == D("7.050")

    def test_low_mip(self):
        assert combined_rate("5.000", "0.500") == D("5.500")

    def test_zero_mip(self):
        assert combined_rate("6.000", "0.000") == D("6.000")

    def test_accepts_floats(self):
        assert combined_rate(6.5, 0.55) == D("7.050")


# --- rate_reduction ---

class TestRateReduction:
    def test_positive_reduction(self):
        assert rate_reduction("6.750", "6.000") == D("0.750")

    def test_zero_reduction(self):
        assert rate_reduction("5.750", "5.750") == D("0.000")

    def test_negative_reduction(self):
        assert rate_reduction("5.000", "5.500") == D("-0.500")

    def test_small_reduction(self):
        assert rate_reduction("6.500", "6.100") == D("0.400")


# --- recoupable_costs ---

class TestRecoupableCosts:
    def test_va001(self):
        # From REFI-VA-001: 6500 - 2500 - 500 - 800 = 2700
        assert recoupable_costs("6500", "2500", "500", "800") == D("2700.00")

    def test_va003(self):
        # From REFI-VA-003: 12000 - 2800 - 600 - 900 = 7700
        assert recoupable_costs("12000", "2800", "600", "900") == D("7700.00")

    def test_all_excluded(self):
        assert recoupable_costs("5000", "2000", "1500", "1500") == D("0.00")


# --- monthly_savings ---

class TestMonthlySavings:
    def test_positive_savings(self):
        assert monthly_savings("1947.50", "1798.65") == D("148.85")

    def test_no_savings(self):
        assert monthly_savings("1751.95", "1751.95") == D("0.00")

    def test_negative_savings(self):
        assert monthly_savings("1800.00", "1900.00") == D("-100.00")


# --- recoupment_months ---

class TestRecoupmentMonths:
    def test_va001(self):
        # 2700 / 148.85 = 18.1
        assert recoupment_months("2700", "148.85") == D("18.1")

    def test_va003_high(self):
        # 7700 / 85.70 = 89.8
        assert recoupment_months("7700", "85.70") == D("89.8")

    def test_zero_savings(self):
        assert recoupment_months("5000", "0") is None

    def test_negative_savings(self):
        assert recoupment_months("5000", "-50") is None

    def test_exact_36(self):
        assert recoupment_months("3600", "100") == D("36.0")


# --- piti_delta_pct ---

class TestPitiDeltaPct:
    def test_va004_increase(self):
        # (2700 - 2200) / 2200 * 100 = 22.7%
        assert piti_delta_pct("2200", "2700") == D("22.7")

    def test_decrease(self):
        # (2220 - 2350) / 2350 * 100 = -5.5%
        assert piti_delta_pct("2350", "2220") == D("-5.5")

    def test_no_change(self):
        assert piti_delta_pct("2000", "2000") == D("0.0")

    def test_large_increase(self):
        assert piti_delta_pct("2000", "3000") == D("50.0")

    def test_zero_old_piti(self):
        assert piti_delta_pct("0", "1000") == D("0.0")
