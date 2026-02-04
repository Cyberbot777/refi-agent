"""
Streamline Government Refinance Agent - Simple API

Endpoints:
- /process/{refi_id} - Process application, get JSON response
- /pdf/{refi_id} - Generate and download PDF report
"""

import sys
import os
import asyncio
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from agents.refi_agent import process_application
from tools.pdf_generator import markdown_to_pdf

# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Streamline Refi Agent",
    description="AI-powered FHA Streamline & VA IRRRL underwriting",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Models
# ============================================================================

class ProcessResponse(BaseModel):
    refi_id: str
    report: str
    success: bool
    error: Optional[str] = None


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Health check and API info."""
    return {
        "service": "Streamline Refi Agent",
        "version": "2.0.0",
        "endpoints": {
            "/process/{refi_id}": "Process application, get JSON with report",
            "/pdf/{refi_id}": "Generate and download PDF report",
            "/test-cases": "List available test cases"
        }
    }


@app.get("/test-cases")
async def get_test_cases():
    """Available test cases."""
    return {
        "test_cases": [
            {"id": "REFI-FHA-001", "program": "FHA", "expected": "APPROVED"},
            {"id": "REFI-FHA-002", "program": "FHA", "expected": "DENIED - Late payments"},
            {"id": "REFI-VA-001", "program": "VA", "expected": "APPROVED"},
            {"id": "REFI-VA-002", "program": "VA", "expected": "DENIED - Recoupment"}
        ]
    }


@app.get("/process/{refi_id}")
async def process(refi_id: str) -> ProcessResponse:
    """Process a refinance application and return the agent's report."""
    try:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            report = await loop.run_in_executor(executor, process_application, refi_id)
        
        return ProcessResponse(refi_id=refi_id, report=report, success=True)
    
    except Exception as e:
        return ProcessResponse(refi_id=refi_id, report="", success=False, error=str(e))


@app.get("/pdf/{refi_id}")
async def generate_pdf(refi_id: str):
    """Process application and return PDF report."""
    try:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            report = await loop.run_in_executor(executor, process_application, refi_id)
        
        pdf_bytes = markdown_to_pdf(report, refi_id)
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=report-{refi_id}.pdf"}
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Run
# ============================================================================

if __name__ == "__main__":
    print("[API] Streamline Refi Agent")
    print("[API] Endpoints: /process/{id}, /pdf/{id}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
