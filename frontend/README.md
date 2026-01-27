# Streamline Refi Agent - Frontend

React + Vite frontend for the Streamline Government Refinance Agent.

## Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend runs on http://localhost:5173

## Features

- Real-time streaming responses from multi-agent system
- Test case quick-select for FHA Streamline and VA IRRRL scenarios
- Markdown rendering for agent responses
- Dark theme with Kind Lending branding

## Test Cases

| ID | Program | Expected Outcome |
|----|---------|------------------|
| REFI-FHA-001 | FHA | ✅ APPROVED |
| REFI-FHA-002 | FHA | ❌ DENIED - Seasoning |
| REFI-FHA-003 | FHA | ❌ DENIED - No NTB |
| REFI-FHA-004 | FHA | ⚠️ CONDITIONS |
| REFI-VA-001 | VA | ✅ APPROVED |
| REFI-VA-002 | VA | ❌ DENIED - Rate |
| REFI-VA-003 | VA | ❌ DENIED - Recoupment |
| REFI-VA-004 | VA | ⚠️ MANUAL REVIEW |

## Requirements

- Node.js 18+
- Backend API running on http://localhost:8000
