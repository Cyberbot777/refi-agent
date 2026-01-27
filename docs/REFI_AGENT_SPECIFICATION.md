# Streamline Government Refinance Agent - Project Specification

**Version:** 1.0  
**Date:** January 2026  
**Author:** Kind Lending AI Team  
**Status:** Planning / Ready for Implementation

---

## Executive Summary

Build a multi-agent AI system to automate underwriting for **FHA Streamline Refinance** and **VA IRRRL** (Interest Rate Reduction Refinance Loan) programs. This agent follows the same architecture as our successful Loan Intake Agent (agents-as-tools pattern using Strands SDK) but with specialized logic for government refinance programs.

**Reference Document:** `Streamline_Govt_Checklist_v1_0.pdf` - Internal underwriting checklist defining all validation rules and regulatory requirements.

---

## Background

### What We Built (Intake Agent)

We have a working multi-agent loan intake system for purchase loans:
- **Orchestrator** coordinates 4 specialist agents (Document Validator, Credit Checker, Income Verifier, Decision Agent)
- Uses Strands SDK with "agents as tools" pattern
- Claude Sonnet 4 for orchestration, Claude Haiku for specialists
- FastAPI + SSE streaming to React frontend
- PostgreSQL for mock data (production will use Hydra)

### What We Need (Refi Agent)

A new multi-agent system for streamline government refinances with:
- **Two program workflows:** FHA Streamline and VA IRRRL (different rules for each)
- **Focus on seasoning, payment history, and rate reduction** (not traditional credit underwriting)
- **Net Tangible Benefit calculations** (rate + MIP comparisons)
- **VA-specific recoupment test** (36-month statutory requirement)

---

## Regulatory Requirements

### FHA Streamline Refinance

**Source:** HUD Single Family Housing Policy Handbook 4000.1  
**URL:** https://www.hud.gov/hud-partners/single-family-handbook-4000-1

**Hard Stops (Must Pass):**
1. Existing loan is FHA-insured (verify FHA case number)
2. No cash-out (max $500 incidental cash back)
3. Loan is current (not delinquent at underwriting or closing)
4. Manual underwriting to FHA Streamline requirements

**Seasoning Requirements:**
1. At least 6 payments made on existing loan
2. At least 6 months since first payment due date
3. At least 210 days since closing date
4. 12-month payment history validation
5. Forbearance completion check (if applicable)

**Net Tangible Benefit (NTB):**
- Combined rate = Note rate + Annual MIP
- Must show reduction in combined rate (scenario-dependent thresholds)
- Scenarios: fixed-to-fixed, fixed-to-ARM, ARM-to-fixed, term reduction

**Borrower Changes:**
- Non-credit-qualifying: all borrowers must remain (exceptions for death/divorce)
- Credit-qualifying: required if adding/removing borrowers outside exceptions

### VA IRRRL

**Source:** VA Circular 26-19-22 and M26-7 Chapter 6  
**URLs:**
- https://www.benefits.va.gov/HOMELOANS/documents/circulars/26_19_22.pdf
- https://benefits.va.gov/WARMS/docs/admin26/m26-07/chapter6-refinancing-loans.pdf

**Hard Stops (Must Pass):**
1. Existing loan is VA-guaranteed
2. Same property as loan being refinanced
3. No improper cash-out (follow VA Form 26-8923 rounding)
4. Only allowable fees/costs included

**Seasoning Requirements:**
1. First payment due date at least 210 days prior to IRRRL closing
2. At least 6 consecutive monthly payments made

**Net Tangible Benefit (NTB):**
- Fixed-to-fixed: Rate must be at least 0.50% lower
- Fixed-to-ARM: Rate must be at least 2.00% lower
- P&I must decrease (with limited exceptions)

**Fee Recoupment (Statutory):**
- All closing costs must recoup within 36 months
- Recoupment = Total Fees / Monthly P&I Savings ≤ 36 months
- **Exclude from numerator:** Taxes, escrow deposits, VA funding fee
- If P&I doesn't decrease, special rules apply

**20% Payment Increase Trigger:**
- If PITI increases by 20% or more, must verify ability to pay

---

## Proposed Architecture

### Agent Structure (7 Specialists)

```
REFI ORCHESTRATOR (Claude Sonnet 4)
├── @tool package_validator(refi_id)      # Section A - Document completeness
├── @tool program_router(refi_id)         # Determine FHA vs VA
├── @tool eligibility_checker(refi_id)    # Hard stops (B1/C1)
├── @tool seasoning_validator(refi_id)    # Payment history (B2/C2)
├── @tool ntb_calculator(refi_id)         # Net Tangible Benefit (B5/C3)
├── @tool recoupment_analyzer(refi_id)    # VA only (C4)
└── @tool refi_decision_agent(refi_id)    # Final decision
```

### Workflow

```
1. Package Validator
   └── Validates all required documents present
   
2. Program Router
   └── Routes to FHA or VA workflow based on existing loan type
   
3. Eligibility Checker
   ├── [FHA] Check B1 hard stops
   └── [VA] Check C1 hard stops
   
4. Seasoning Validator
   ├── [FHA] 210 days + 6 payments + 12-month history (B2)
   └── [VA] 210 days + 6 consecutive payments (C2)
   
5. NTB Calculator
   ├── [FHA] Combined rate reduction test (B5)
   └── [VA] Rate reduction test + P&I decrease (C3)
   
6. Recoupment Analyzer
   ├── [FHA] Skip
   └── [VA] 36-month recoupment test (C4)
   
7. Refi Decision Agent
   └── Final approval/denial with conditions
```

---

## Key Calculations

### Seasoning Check
```
days_since_closing = (today - original_closing_date).days
months_since_first_payment = months_between(first_payment_date, today)
payments_made = count of payments in payment_history

FHA Pass: days_since_closing >= 210 AND months_since_first_payment >= 6 AND payments_made >= 6
VA Pass:  days_since_closing >= 210 AND payments_made >= 6 (consecutive)
```

### FHA Net Tangible Benefit
```
old_combined_rate = old_note_rate + old_annual_mip
new_combined_rate = new_note_rate + new_annual_mip

# Fixed-to-Fixed scenario
passes = new_combined_rate < old_combined_rate
```

### VA Net Tangible Benefit
```
rate_reduction = old_note_rate - new_note_rate

# Fixed-to-Fixed
passes = rate_reduction >= 0.50

# Fixed-to-ARM  
passes = rate_reduction >= 2.00

# P&I Check
pi_decreases = new_pi < old_pi
```

### VA Recoupment
```
# Exclude prohibited items from fees
recoupment_fees = total_closing_costs - taxes - escrow_deposits - va_funding_fee

# Calculate months to recoup
monthly_savings = old_pi - new_pi
recoupment_months = recoupment_fees / monthly_savings

passes = recoupment_months <= 36
```

---

## Database Schema (New Tables)

### refi_applications
| Column | Type | Description |
|--------|------|-------------|
| refi_id | VARCHAR(50) | Primary key (e.g., "REFI-001") |
| borrower_name | VARCHAR(255) | Borrower name |
| property_address | TEXT | Property address |
| existing_loan_type | VARCHAR(50) | 'FHA' or 'VA' |
| existing_loan_number | VARCHAR(100) | Servicer loan number |
| fha_case_number | VARCHAR(50) | FHA case number (if FHA) |
| original_closing_date | DATE | When existing loan closed |
| first_payment_due_date | DATE | First payment date of existing loan |
| current_note_rate | DECIMAL(5,3) | Current interest rate |
| current_monthly_pi | DECIMAL(10,2) | Current P&I payment |
| current_monthly_piti | DECIMAL(10,2) | Current total payment |
| current_loan_balance | DECIMAL(12,2) | Payoff amount |
| new_note_rate | DECIMAL(5,3) | Proposed new rate |
| new_monthly_pi | DECIMAL(10,2) | New P&I payment |
| new_loan_amount | DECIMAL(12,2) | New loan amount |
| total_closing_costs | DECIMAL(10,2) | All closing costs |
| cash_to_borrower | DECIMAL(10,2) | Cash back at closing |

### payment_history
| Column | Type | Description |
|--------|------|-------------|
| refi_id | VARCHAR(50) | FK to refi_applications |
| payment_date | DATE | Date of payment |
| payment_amount | DECIMAL(10,2) | Amount paid |
| days_late | INT | Days past due (0 = on time) |
| status | VARCHAR(20) | 'CURRENT', 'LATE_30', 'LATE_60', 'LATE_90' |

### refi_documents
| Column | Type | Description |
|--------|------|-------------|
| refi_id | VARCHAR(50) | FK to refi_applications |
| document_type | VARCHAR(100) | 'PAYOFF_STATEMENT', 'PAYMENT_HISTORY', etc. |
| file_name | VARCHAR(255) | Filename |
| verified | BOOLEAN | Document verified |

---

## Test Scenarios

### FHA Streamline Test Cases

| ID | Scenario | Expected Result |
|----|----------|-----------------|
| REFI-FHA-001 | Good FHA, 8 months seasoned, rate drops 0.5% | ✅ APPROVED |
| REFI-FHA-002 | FHA loan only 4 months old | ❌ DENIED - Seasoning |
| REFI-FHA-003 | FHA with 2 late payments in last 12 months | ⚠️ REVIEW - Payment history |
| REFI-FHA-004 | FHA, no rate reduction (lateral refi) | ❌ DENIED - No NTB |
| REFI-FHA-005 | FHA, $600 cash back | ❌ DENIED - Cash-out exceeds $500 |

### VA IRRRL Test Cases

| ID | Scenario | Expected Result |
|----|----------|-----------------|
| REFI-VA-001 | Good VA, rate drops 0.75%, recoup in 24 months | ✅ APPROVED |
| REFI-VA-002 | VA only 5 payments made | ❌ DENIED - Seasoning |
| REFI-VA-003 | VA, rate drops 0.40% | ❌ DENIED - NTB (need 0.50%) |
| REFI-VA-004 | VA, recoupment = 42 months | ❌ DENIED - Recoupment |
| REFI-VA-005 | VA, PITI increases 25% | ⚠️ MANUAL REVIEW - 20% trigger |

---

## File Structure (Proposed)

```
refi-agent/
├── agents/
│   ├── refi_orchestrator.py       # Main coordinator
│   ├── package_validator.py       # Document completeness
│   ├── program_router.py          # FHA vs VA routing
│   ├── eligibility_checker.py     # Hard stops
│   ├── seasoning_validator.py     # Payment history checks
│   ├── ntb_calculator.py          # Net Tangible Benefit
│   ├── recoupment_analyzer.py     # VA recoupment (C4)
│   └── refi_decision_agent.py     # Final decision
├── tools/
│   ├── refi_database_tools.py     # Database queries
│   ├── refi_rules.py              # Hard stop logic
│   ├── seasoning_tools.py         # Seasoning calculations
│   ├── ntb_tools.py               # NTB calculations
│   └── recoupment_tools.py        # VA recoupment
├── config/
│   ├── refi_prompts.py            # Agent system prompts
│   └── settings.py                # Environment config
├── mock_data/
│   └── refi_init.sql              # Test data
├── tests/
│   ├── test_refi_agents.py
│   └── test_refi_tools.py
├── api.py                         # FastAPI server
├── demo.py                        # Demo script
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

## Tech Stack

| Component | Technology | Notes |
|-----------|------------|-------|
| Framework | Strands Agents SDK | Same as intake agent |
| Orchestrator Model | Claude Sonnet 4 | Reasoning & coordination |
| Specialist Models | Claude Haiku | Fast execution |
| API | FastAPI + SSE | Streaming responses |
| Database (POC) | PostgreSQL | Mock data |
| Database (Prod) | Hydra | Production data platform |
| Deployment | AWS Bedrock AgentCore | us-east-1 |

---

## Implementation Priority

### Phase 1: Core Rules Engine
1. `tools/refi_rules.py` - Hard stop eligibility checks
2. `tools/seasoning_tools.py` - Seasoning calculations
3. `tools/ntb_tools.py` - Net Tangible Benefit
4. `tools/recoupment_tools.py` - VA recoupment

### Phase 2: Database & Queries
5. `mock_data/refi_init.sql` - Schema + test data
6. `tools/refi_database_tools.py` - Query functions

### Phase 3: Agents
7. All 7 specialist agents
8. `config/refi_prompts.py` - System prompts
9. `agents/refi_orchestrator.py` - Main coordinator

### Phase 4: API & Demo
10. `api.py` - FastAPI endpoint
11. `demo.py` - Interactive demo
12. Tests

---

## References

- **HUD Handbook 4000.1:** https://www.hud.gov/hud-partners/single-family-handbook-4000-1
- **FDIC FHA Streamline:** https://www.fdic.gov/system/files/2024-07/streamline-refinance.pdf
- **VA Circular 26-19-22:** https://www.benefits.va.gov/HOMELOANS/documents/circulars/26_19_22.pdf
- **VA M26-7 Chapter 6:** https://benefits.va.gov/WARMS/docs/admin26/m26-07/chapter6-refinancing-loans.pdf
- **VA Form 26-8923:** https://www.vba.va.gov/pubs/forms/vba-26-8923-are.pdf
- **Strands SDK Docs:** https://strandsagents.com/latest/documentation/docs/

---

## Success Criteria

1. ✅ Process FHA Streamline applications with correct NTB calculation
2. ✅ Process VA IRRRL applications with recoupment validation
3. ✅ Enforce all hard stop rules from regulatory requirements
4. ✅ Calculate seasoning correctly (210 days, 6 payments)
5. ✅ Stream results to frontend with clear section breaks
6. ✅ Provide actionable recommendations when denying
7. ✅ Support both programs with single orchestrator
8. ✅ Ready for AgentCore deployment to us-east-1
