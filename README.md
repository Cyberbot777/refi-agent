# Refi Agent

Minimal agentic underwriter for FHA Streamline and VA IRRRL refinance loans.

## Architecture

The agent does all the reasoning. We just provide:
- **Rules** → System prompt (from STREAMLINE_GOVT_CHECKLIST.md)
- **Data** → One database tool
- **Goal** → User prompt

```
┌─────────────────────────────────────────┐
│            refi_agent.py                │
│                                         │
│  SYSTEM PROMPT (FHA/VA Rules)           │
│           ↓                             │
│      CLAUDE SONNET                      │
│   - Fetches loan data                   │
│   - Checks eligibility rules            │
│   - Does calculations (NTB, etc.)       │
│   - Makes decision                      │
│   - Generates report                    │
│           ↓                             │
│      TOOLS                              │
│   - get_loan_data(refi_id)              │
│   - record_decision(...)                │
└─────────────────────────────────────────┘
```

## Quick Start

```bash
# 1. Start database
docker-compose up -d postgres

# 2. Activate environment
source venv/Scripts/activate  # Windows
source venv/bin/activate      # Mac/Linux

# 3. Run agent (CLI)
python -m agents.refi_agent REFI-FHA-001
```

## Test Cases

| ID | Program | Description | Expected |
|----|---------|-------------|----------|
| REFI-FHA-001 | FHA Streamline | Good loan, all checks pass | APPROVED |
| REFI-FHA-002 | FHA Streamline | Late payments in history | DENIED |
| REFI-VA-001 | VA IRRRL | Good loan, all checks pass | APPROVED |
| REFI-VA-002 | VA IRRRL | Recoupment > 36 months | DENIED |

## CLI Usage

```bash
# Process a single application
python -m agents.refi_agent REFI-FHA-001

# Process VA loan
python -m agents.refi_agent REFI-VA-001
```

## API Usage (Optional)

```bash
# Start API server
python api.py

# Process application (JSON response)
curl http://localhost:8000/process/REFI-FHA-001

# Download PDF report
curl -o report.pdf http://localhost:8000/pdf/REFI-FHA-001
```

## Files

```
refi-agent/
├── agents/
│   └── refi_agent.py          # The agent (rules in prompt)
├── tools/
│   ├── refi_database_tools.py # Data access
│   └── pdf_generator.py       # Markdown → PDF
├── config/
│   └── settings.py            # Database config
├── docs/
│   └── STREAMLINE_GOVT_CHECKLIST.md  # Source rules
├── mock_data/
│   └── refi_init.sql          # Test data
├── api.py                     # Optional HTTP API
├── docker-compose.yml         # PostgreSQL
└── requirements.txt
```

## Rules Reference

### FHA Streamline (Sections B1, B2, B5)
- **B1 Hard Stops**: FHA case number, cash ≤ $500, loan current
- **B2 Seasoning**: 210 days since closing, 6 payments made, max 1x30 late
- **B5 NTB**: New combined rate (note + MIP) < old combined rate

### VA IRRRL (Sections C1-C5)
- **C1 Hard Stops**: VA loan number, same property, no cash out
- **C2 Seasoning**: 210 days, 6 consecutive payments
- **C3 NTB**: Rate reduction ≥0.50% (fixed) or ≥2.00% (ARM)
- **C4 Recoupment**: Fees recovered in ≤36 months
- **C5 PITI Trigger**: >20% increase requires manual review

## Requirements

```
strands-agents>=0.1.0
psycopg2-binary>=2.9.0
reportlab>=4.0.0
fastapi>=0.100.0
uvicorn>=0.22.0
```
