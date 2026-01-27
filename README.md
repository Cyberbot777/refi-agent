# Streamline Government Refinance Agent

Multi-agent AI system for **FHA Streamline Refinance** and **VA IRRRL** (Interest Rate Reduction Refinance Loan) underwriting using Strands SDK with the **"Agents as Tools"** pattern.

**Status:** POC / Ready for Testing  
**Owner:** Kind Lending AI Automation Team  
**Architecture Reference:** Based on Kind Lending's Loan Intake Agent standard

---

## What It Does

Automates underwriting validation for streamline government refinances. An orchestrator agent coordinates seven specialized agents following the [Streamline Government Refinance Checklist](docs/STREAMLINE_GOVT_CHECKLIST.md):

| Agent | Section | Purpose |
|-------|---------|---------|
| **Package Validator** | A | Document completeness and readability |
| **Program Router** | - | Determines FHA vs VA workflow |
| **Eligibility Checker** | B1/C1 | Hard stop verification |
| **Seasoning Validator** | B2/C2 | 210 days, 6 payments, payment history |
| **NTB Calculator** | B5/C3 | Net Tangible Benefit calculation |
| **Recoupment Analyzer** | C4/C5 | VA 36-month recoupment & 20% PITI trigger |
| **Refi Decision Agent** | - | Final pre-qualification decision |

Each specialist agent is wrapped as a `@tool` that the orchestrator invokes, creating a hierarchical multi-agent system.

---

## Demo Screenshots

### Home Screen
Clean, modern interface with Kind Lending branding and capability overview.

![Home Screen](docs/screenshots/01-home.png)

### Test Cases Dropdown
Pre-configured test scenarios for both FHA Streamline and VA IRRRL - showing expected outcomes (✅ Pass, ❌ Fail, ⚠️ Warning).

![Test Cases](docs/screenshots/02-test-cases.png)

### Agent Processing (FHA Approval)
Real-time streaming output showing the multi-agent pipeline: Package Validation → Program Routing → Eligibility Check → Seasoning Analysis → NTB Calculation.

![Agent Processing](docs/screenshots/04-agent-processing.png)

### Approval Decision
Final decision with confidence score, key metrics, and next steps for the underwriter.

![Approval Decision](docs/screenshots/06-final-decision.png)

### Denial Example (Seasoning Failure)
When a loan fails validation, the agent stops processing and provides clear denial reasons with remediation steps.

![Denial Example](docs/screenshots/07-fha-denied.png)

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| **Framework** | Strands Agents SDK |
| **Orchestrator Model** | Claude Sonnet 4 |
| **Specialist Models** | Claude Haiku |
| **API** | FastAPI + SSE streaming |
| **Frontend** | React + Vite + Tailwind |
| **Database (POC)** | PostgreSQL |
| **Database (Prod)** | Hydra |
| **Deployment** | AWS Bedrock AgentCore (us-east-1) |

---

## Quick Start

### Prerequisites

- Docker Desktop
- Python 3.12+
- Node.js 18+
- AWS credentials configured

### 1. Start Database

```bash
docker-compose up -d postgres
```

### 2. Setup Python

```bash
# Create virtual environment
uv venv .venv
source .venv/Scripts/activate  # Windows Git Bash
# or
source .venv/bin/activate       # Linux/Mac

# Install dependencies
uv pip install -r requirements.txt
```

### 3. Create `.env`

```env
ENV=local
DATABASE_URL=postgresql://refiuser:localdev@localhost:5432/streamline_refi
AWS_REGION=us-east-1
```

### 4. Run the Application

**Option A: Interactive CLI**
```bash
python main.py
```

**Option B: API Server (with streaming)**
```bash
python api.py
# API runs on http://localhost:8000
```

**Option C: Demo Script**
```bash
python demo.py
# Or test specific case:
python demo.py REFI-FHA-001
```

### 5. Start Frontend

```bash
cd frontend
npm install
npm run dev
# Frontend runs on http://localhost:5173
```

---

## Test Cases

### FHA Streamline

| ID | Scenario | Expected |
|----|----------|----------|
| REFI-FHA-001 | Good loan, 8+ months seasoned, rate drops 0.625% | ✅ APPROVED |
| REFI-FHA-002 | Only 4 months old - fails 210 day requirement | ❌ DENIED |
| REFI-FHA-003 | Same rate - lateral refi, no NTB | ❌ DENIED |
| REFI-FHA-004 | Cash back $450 (near $500 limit) | ⚠️ CONDITIONS |

### VA IRRRL

| ID | Scenario | Expected |
|----|----------|----------|
| REFI-VA-001 | Good loan, 0.75% rate drop, recoup in ~18 months | ✅ APPROVED |
| REFI-VA-002 | Rate drops only 0.40% (need 0.50%) | ❌ DENIED |
| REFI-VA-003 | Recoupment exceeds 36 months | ❌ DENIED |
| REFI-VA-004 | PITI increases 22.7% (triggers manual review) | ⚠️ MANUAL REVIEW |

---

## FHA MIP (Mortgage Insurance Premium)

> **Important:** Understanding MIP is critical for FHA Net Tangible Benefit calculations.

### What is MIP?

FHA loans require mortgage insurance with two components:

1. **Upfront MIP (UFMIP):** ~1.75% of loan amount, paid at closing
2. **Annual MIP:** ~0.55% of loan balance, paid monthly

### Why It Matters for NTB

FHA Streamline requires the **combined rate** to decrease:

```
Combined Rate = Note Rate + Annual MIP Rate

Example:
Old Loan: 6.50% note + 0.55% MIP = 7.05% combined
New Loan: 5.875% note + 0.55% MIP = 6.425% combined
✅ PASSES - Combined rate decreased by 0.625%
```

### POC vs Production

| Environment | MIP Source |
|-------------|------------|
| **POC** | Hardcoded in `config/mip_rates.py` (current HUD rates) |
| **Production** | Should come from LOS/pricing engine as loan data fields |

**Current POC Rates (January 2026):**
- Annual MIP: 0.55% (loans >15 years, LTV >90%)
- UFMIP: 1.75% (or 0.01% for streamline within 3 years)

See `config/mip_rates.py` for full rate table and `get_mip_rate()` function.

---

## Project Structure

```
streamline-refi-multiagent/
├── agents/                      # Multi-agent system
│   ├── refi_orchestrator.py     # Main coordinator
│   ├── package_validator.py     # Section A
│   ├── program_router.py        # FHA vs VA routing
│   ├── eligibility_checker.py   # B1/C1 hard stops
│   ├── seasoning_validator.py   # B2/C2 seasoning
│   ├── ntb_calculator.py        # B5/C3 NTB
│   ├── recoupment_analyzer.py   # C4/C5 VA recoupment
│   └── refi_decision_agent.py   # Final decision
├── tools/                       # Tools used by agents
│   ├── refi_database_tools.py   # Database queries
│   ├── refi_rules.py            # Hard stop logic
│   ├── seasoning_tools.py       # Seasoning calculations
│   ├── ntb_tools.py             # NTB calculations
│   └── recoupment_tools.py      # VA recoupment
├── config/                      # Configuration
│   ├── settings.py              # Environment config
│   ├── prompts.py               # Agent system prompts
│   └── mip_rates.py             # FHA MIP rates
├── docs/                        # Documentation
│   ├── screenshots/             # POC demo screenshots
│   └── STREAMLINE_GOVT_CHECKLIST.md
├── mock_data/                   # Test data
│   └── refi_init.sql            # Schema + test cases
├── frontend/                    # React UI
├── tests/                       # Test suite
├── api.py                       # FastAPI server
├── main.py                      # Interactive CLI
├── demo.py                      # Demo script
├── docker-compose.yml           # Local services
├── Dockerfile                   # Container build
└── requirements.txt             # Python dependencies
```

---

## Regulatory References

| Source | Description |
|--------|-------------|
| [HUD Handbook 4000.1](https://www.hud.gov/hud-partners/single-family-handbook-4000-1) | FHA policy handbook |
| [FDIC FHA Streamline](https://www.fdic.gov/system/files/2024-07/streamline-refinance.pdf) | FHA Streamline fact sheet |
| [VA Circular 26-19-22](https://www.benefits.va.gov/HOMELOANS/documents/circulars/26_19_22.pdf) | IRRRL requirements |
| [VA M26-7 Chapter 6](https://benefits.va.gov/WARMS/docs/admin26/m26-07/chapter6-refinancing-loans.pdf) | Refinancing loans |
| [VA Form 26-8923](https://www.vba.va.gov/pubs/forms/vba-26-8923-are.pdf) | IRRRL worksheet |

---

## Key Calculations

### Seasoning (FHA)
```python
days_since_closing >= 210
months_since_first_payment >= 6
payments_made >= 6
```

### Seasoning (VA)
```python
days_from_first_payment_to_irrrl_closing >= 210
consecutive_payments_made >= 6
```

### FHA Net Tangible Benefit
```python
old_combined = old_note_rate + old_annual_mip
new_combined = new_note_rate + new_annual_mip
passes = new_combined < old_combined
```

### VA Net Tangible Benefit
```python
# Fixed-to-Fixed
passes = (old_rate - new_rate) >= 0.50

# Fixed-to-ARM
passes = (old_rate - new_rate) >= 2.00
```

### VA Recoupment
```python
recoupable_fees = total_costs - taxes - escrow - va_funding_fee
monthly_savings = old_pi - new_pi
recoupment_months = recoupable_fees / monthly_savings
passes = recoupment_months <= 36
```

---

## Production Deployment

This agent is designed for AWS Bedrock AgentCore deployment:

```yaml
# .bedrock_agentcore.yaml
agent:
  name: streamline-refi-agent
  region: us-east-1

runtime:
  type: container
  repository: kind-lending/streamline-refi-agent

observability:
  enabled: true
```

See `Dockerfile` for container configuration following AgentCore standards.

---

## Commands Reference

```bash
# Start database
docker-compose up -d postgres

# Run CLI
python main.py

# Run API server
python api.py

# Run demo
python demo.py
python demo.py REFI-FHA-001

# Run tests
ENV=local pytest tests/ -v

# Frontend
cd frontend && npm run dev
```

---

## License

Internal - Kind Lending
