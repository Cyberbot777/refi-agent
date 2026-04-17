# Refi Agent

AI-powered underwriter for **FHA Streamline** and **VA IRRRL** refinance loans. Compares two approaches to the same underwriting task:

1. **Claude Sonnet** — large model + detailed rules-based prompt + tool-calling agent loop (100% accuracy, ~29s)
2. **Nova Lite (Fine-Tuned)** — small model + short prompt + single inference call (87% accuracy, ~5s)

Built with [Strands Agents SDK](https://strandsagents.com) and [AWS Bedrock](https://aws.amazon.com/bedrock/) fine-tuning.

## Why Two Agents?

This project explores the tradeoff between **prompted large models** and **fine-tuned small models** for structured decision-making:

|                   | Claude Sonnet (Prompted)            | Nova Lite (Fine-Tuned)                 |
| ----------------- | ----------------------------------- | -------------------------------------- |
| **Accuracy**      | 100% (8/8 mock, 70/70 synthetic)    | 87.1% (8/8 mock, 61/70 synthetic)      |
| **Latency**       | ~29s                                | ~5s                                    |
| **System Prompt** | ~6,000 chars                        | ~900 chars                             |
| **Architecture**  | Multi-turn agent loop with tools    | Single inference call                  |
| **Cost/Request**  | Higher (Sonnet pricing, 2K+ tokens) | Lower (Nova Lite pricing, ~500 tokens) |
| **Setup**         | AWS credentials only                | Requires fine-tuning + deployment      |

The Claude agent uses a 6K-char system prompt that spells out every rule, threshold, and edge case. The LLM reasons through each rule step-by-step via tool calls. It's accurate but slow.

The Nova Lite agent was fine-tuned on 3,000 synthetic underwriting examples. The rules are baked into the model weights, so it only needs a 900-char prompt for decision priority. No tool-calling loop — the application formats DB data as text and makes a single API call.

## How It Works

Both agents receive a loan application ID, analyze the data, and produce a structured underwriting report with PASS/FAIL checks and a final decision.

**Claude Sonnet Agent** — multi-step agent loop:

```
refi_id → Agent → get_loan_data() → Reason through 6K prompt → record_decision() → Report
            └─── 2-3 LLM round-trips (~29s) ───┘
```

**Nova Lite Agent** — single inference:

```
refi_id → Fetch DB → Format text → Nova Lite inference → Parse & record → Report
            └─── 1 LLM call (~5s) ───┘
```

### Decision Classes

| Decision                     | Meaning                                                   |
| ---------------------------- | --------------------------------------------------------- |
| **APPROVED**                 | All checks pass, no edge-case flags                       |
| **APPROVED WITH CONDITIONS** | All checks pass, but borderline values flagged for review |
| **DENIED**                   | One or more required checks fail                          |
| **NEEDS REVIEW**             | VA only — PITI increase ≥20% triggers manual review       |

## Quick Start

### Prerequisites

- Python 3.12+
- Docker (for PostgreSQL)
- AWS credentials with Bedrock access (`us-east-1`)
- For Nova Lite: a deployed fine-tuned model endpoint (see Fine-Tuning section)

### Setup

```bash
# 1. Start the database
docker compose up -d postgres

# 2. Create and activate virtual environment
python -m venv venv
source venv/Scripts/activate    # Windows (Git Bash)
source venv/bin/activate        # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the Claude agent
PYTHONIOENCODING=utf-8 python -m agents.claude_refi_agent REFI-FHA-001

# 5. Run the Nova Lite agent
PYTHONIOENCODING=utf-8 python -m agents.novalite_refi_agent REFI-FHA-001
```

### Run the Evaluation Suite

```bash
# Claude agent evaluation (8 mock data cases)
PYTHONIOENCODING=utf-8 python -m tests.db_eval_agent
```

### Test Cases

Both agents produce identical correct results on the 8 mock data scenarios:

| Case         | Program | Scenario                        | Decision     |
| ------------ | ------- | ------------------------------- | ------------ |
| REFI-FHA-001 | FHA     | All checks pass                 | APPROVED     |
| REFI-FHA-002 | FHA     | Loan status PENDING             | DENIED       |
| REFI-FHA-003 | FHA     | PENDING + no NTB                | DENIED       |
| REFI-FHA-004 | FHA     | PENDING (all else passes)       | DENIED       |
| REFI-VA-001  | VA      | All checks pass                 | APPROVED     |
| REFI-VA-002  | VA      | NTB fail (0.40% < 0.50%)        | DENIED       |
| REFI-VA-003  | VA      | Recoupment fail (89.8mo > 36mo) | DENIED       |
| REFI-VA-004  | VA      | PITI increase 22.7% > 20%       | NEEDS REVIEW |

## Project Structure

```
refi-agent/
├── agents/
│   ├── claude_refi_agent.py        # Claude Sonnet agent (prompted, tool-calling)
│   └── novalite_refi_agent.py     # Nova Lite agent (fine-tuned, single call)
├── tools/
│   └── refi_database_tools.py     # Shared data access layer (PostgreSQL)
├── scripts/
│   ├── generate_training_data.py  # Synthetic training data generator
│   ├── launch_fine_tuning.py      # Bedrock fine-tuning job management
│   └── lib/
│       ├── decision_engine.py     # Deterministic rule engine (ground truth)
│       ├── rules.py               # FHA/VA underwriting rules
│       ├── scenarios.py           # Synthetic loan scenario generator
│       ├── templates.py           # Training data output templates
│       └── validators.py          # Data validation
├── data/nova/                     # Training/validation JSONL files
├── config/
│   └── settings.py                # Environment-aware configuration
├── mock_data/
│   └── refi_init.sql              # 8 test loan scenarios
├── tests/
│   ├── accuracy_test_harness.py   # Accuracy testing against training data
│   ├── db_eval_agent.py           # DB integration eval (8 mock cases)
│   ├── heldout_eval_cases.json    # 20 held-out cases (never in training data)
│   ├── heldout_test_agent.py      # Runs held-out cases against Nova Lite
│   ├── test_decisions.py          # Decision engine unit tests
│   └── test_rules.py              # Rule validation unit tests
├── docker-compose.yml             # PostgreSQL
├── Dockerfile                     # Production container (AgentCore-ready)
└── requirements.txt
```

## Underwriting Rules

### FHA Streamline (B1, B2, B5)

| Check           | Rule                                                | Fail → |
| --------------- | --------------------------------------------------- | ------ |
| B1 - Hard Stops | Valid FHA case number, cash ≤ $500, status CURRENT  | DENY   |
| B2 - Seasoning  | ≥ 210 days since closing, ≥ 6 payments, ≤ 1x30 late | DENY   |
| B5 - NTB        | Combined rate reduction ≥ 0.250%                    | DENY   |

### VA IRRRL (C1-C5)

| Check             | Rule                                                             | Fail →       |
| ----------------- | ---------------------------------------------------------------- | ------------ |
| C1 - Hard Stops   | Valid VA loan number, same property, $0 cash out, status CURRENT | DENY         |
| C2 - Seasoning    | ≥ 210 days since closing, ≥ 6 consecutive on-time payments       | DENY         |
| C3 - NTB          | ≥ 0.50% reduction (fixed-to-fixed), ≥ 2.00% (fixed-to-ARM)       | DENY         |
| C4 - Recoupment   | Recoupable costs / monthly savings ≤ 36 months                   | DENY         |
| C5 - PITI Trigger | New PITI ≥ 20% higher than current                               | NEEDS REVIEW |

## Fine-Tuning

The Nova Lite agent was fine-tuned using Amazon Bedrock's model customization API. The training pipeline:

1. **`scripts/lib/decision_engine.py`** — deterministic rule engine that produces ground-truth decisions
2. **`scripts/lib/scenarios.py`** — generates synthetic FHA/VA loan scenarios with controlled class distribution
3. **`scripts/generate_training_data.py`** — combines scenarios + engine into `bedrock-conversation-2024` JSONL format
4. **`scripts/launch_fine_tuning.py`** — submits fine-tuning jobs to Bedrock, checks status, runs smoke tests

Training data: 3,000 records (2,700 train / 300 validation), class balance 25% APPROVED / 20% AWC / 35% DENIED / 20% NEEDS_REVIEW. Base model: `amazon.nova-lite-v1:0:300k`.

## Technology Stack

- **Agent Framework**: [Strands Agents SDK](https://strandsagents.com)
- **Models**: Claude Sonnet (prompted) + Amazon Nova Lite (fine-tuned)
- **Cloud**: AWS Bedrock (inference + fine-tuning)
- **Database**: PostgreSQL 15
- **Deployment**: Docker, AWS Bedrock AgentCore ready
- **Region**: us-east-1
