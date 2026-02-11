# Refi Agent

AI-powered underwriter for **FHA Streamline** and **VA IRRRL** refinance loans.

Built with [Strands Agents SDK](https://strandsagents.com) + Claude Sonnet on AWS Bedrock.

## How It Works

The agent receives a loan application ID, fetches the data, applies government underwriting rules, and produces a structured decision — all driven by the LLM with a rules-based system prompt.

```
User: "Analyze REFI-FHA-001"
        │
        ▼
┌──────────────────────────────────┐
│         Claude Sonnet            │
│                                  │
│  System Prompt                   │
│  ├─ FHA Rules (B1, B2, B5)       │
│  └─ VA Rules (C1-C5)             │
│                                  │
│  Tools                           │
│  ├─ get_loan_data(refi_id)       │
│  └─ record_decision(refi_id,     │
│       decision, reasoning)       │
└──────────────────────────────────┘
        │
        ▼
  Underwriting Report
  ├─ Loan Summary
  ├─ Eligibility Checks (PASS/FAIL)
  ├─ Calculations (NTB, recoupment)
  ├─ Decision (APPROVED / DENIED / NEEDS_REVIEW)
  └─ Next Steps
```

## Evaluation Results

**8/8 test cases correct (100% accuracy)** across FHA and VA programs:

| Case | Program | Scenario | Expected | Result |
|------|---------|----------|----------|--------|
| REFI-FHA-001 | FHA Streamline | All checks pass | APPROVED | APPROVED |
| REFI-FHA-002 | FHA Streamline | Insufficient seasoning + status PENDING | DENIED | DENIED |
| REFI-FHA-003 | FHA Streamline | Status PENDING + no NTB (identical rates) | DENIED | DENIED |
| REFI-FHA-004 | FHA Streamline | Status PENDING (all else passes) | DENIED | DENIED |
| REFI-VA-001 | VA IRRRL | All checks pass | APPROVED | APPROVED |
| REFI-VA-002 | VA IRRRL | NTB fail (0.40% < 0.50%) + status PENDING | DENIED | DENIED |
| REFI-VA-003 | VA IRRRL | Recoupment fail (89.8mo > 36mo) | DENIED | DENIED |
| REFI-VA-004 | VA IRRRL | PITI increase 22.7% > 20% trigger | NEEDS_REVIEW | NEEDS_REVIEW |

Average response time: **29 seconds** per application.

## Quick Start

### Prerequisites
- Python 3.12+
- Docker (for PostgreSQL)
- AWS credentials with Bedrock access (us-east-1)

### Setup

```bash
# 1. Start the database
docker compose up -d postgres

# 2. Create and activate virtual environment
python -m venv venv
source venv/Scripts/activate    # Windows (Git Bash)
source venv/bin/activate        # Mac/Linux

# 3. Install dependencies
uv pip install -r requirements.txt

# 4. Run the agent on a test case
PYTHONIOENCODING=utf-8 python -m agents.refi_agent REFI-FHA-001
```

### Run the Evaluation Suite

```bash
PYTHONIOENCODING=utf-8 python -m agents.eval_agent
```

## Project Structure

```
refi-agent/
├── agents/
│   ├── refi_agent.py              # Agent + system prompt (all underwriting rules)
│   └── eval_agent.py              # Automated evaluation harness
├── tools/
│   └── refi_database_tools.py     # Data access layer (PostgreSQL)
├── config/
│   └── settings.py                # Environment-aware configuration
├── utils/
│   └── config_loader.py           # Config helper
├── mock_data/
│   └── refi_init.sql              # Test data (8 loan scenarios)
├── docs/
│   └── STREAMLINE_GOVT_CHECKLIST.md   # Source underwriting rules
├── docker-compose.yml             # PostgreSQL
├── Dockerfile                     # Production container (AgentCore-ready)
└── requirements.txt               # Python dependencies
```

## Underwriting Rules

### FHA Streamline (Sections B1, B2, B5)

| Check | Rule | Fail Action |
|-------|------|-------------|
| B1 - Hard Stops | Valid FHA case number, cash to borrower <= $500, loan status CURRENT | DENY |
| B2 - Seasoning | >= 210 days since closing, >= 6 payments made, max 1x30 late / zero 60+ | DENY |
| B5 - NTB | New combined rate (note + MIP) < old combined rate | DENY |

### VA IRRRL (Sections C1-C5)

| Check | Rule | Fail Action |
|-------|------|-------------|
| C1 - Hard Stops | Valid VA loan number, same property, no cash out, loan status CURRENT | DENY |
| C2 - Seasoning | >= 210 days since closing, >= 6 consecutive on-time payments | DENY |
| C3 - NTB | >= 0.50% rate reduction (fixed-to-fixed), >= 2.00% (ARM-to-fixed) | DENY |
| C4 - Recoupment | (Recoupable costs) / monthly P&I savings <= 36 months | DENY |
| C5 - PITI Trigger | New PITI > 20% higher than current PITI | NEEDS_REVIEW |

## Technology Stack

- **Agent Framework**: [Strands Agents SDK](https://strandsagents.com)
- **LLM**: Claude 3.5 Sonnet v2 (via AWS Bedrock)
- **Database**: PostgreSQL 15
- **Deployment**: Docker, AWS Bedrock AgentCore ready
- **Region**: us-east-1

## Next Steps

- [ ] Connect to production Hydra/Snowflake data source
- [ ] Expand test cases with production loan scenarios
- [ ] Add Bedrock Guardrails for production
- [ ] Deploy to AWS Bedrock AgentCore
- [ ] Add more loan programs (conventional, USDA)
