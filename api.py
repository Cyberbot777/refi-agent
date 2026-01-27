"""
Streamline Government Refinance API
FastAPI backend with streaming multi-agent analysis for FHA Streamline and VA IRRRL.
"""

import json
import queue
import threading
from typing import AsyncGenerator
from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from strands import Agent
from strands.models import BedrockModel

from config.prompts import ORCHESTRATOR_PROMPT
from utils.config_loader import get_model_config

# Import the tool functions
from agents.package_validator import package_validator
from agents.program_router import program_router
from agents.eligibility_checker import eligibility_checker
from agents.seasoning_validator import seasoning_validator
from agents.ntb_calculator import ntb_calculator
from agents.recoupment_analyzer import recoupment_analyzer
from agents.refi_decision_agent import refi_decision_agent


def create_streaming_orchestrator(output_queue: queue.Queue) -> Agent:
    """Create orchestrator with streaming callback for underwriter UI."""
    model_config = get_model_config()
    model = BedrockModel(
        model_id=model_config["orchestrator_model"],
        temperature=model_config["temperature"],
    )
    
    def streaming_callback(**kwargs):
        """Callback handler that streams orchestrator output to queue."""
        # Stream text data chunks from orchestrator
        if "data" in kwargs:
            data = kwargs["data"]
            if data:
                output_queue.put({"type": "chunk", "content": data})
        
        # Notify about tool usage (sub-agent calls)
        elif "current_tool_use" in kwargs:
            tool_use = kwargs["current_tool_use"]
            if tool_use and tool_use.get("name"):
                if "input" in tool_use and isinstance(tool_use.get("input"), dict):
                    tool_name = tool_use["name"]
                    readable_names = {
                        "package_validator": "Validating Package",
                        "program_router": "Routing Program",
                        "eligibility_checker": "Checking Eligibility",
                        "seasoning_validator": "Validating Seasoning",
                        "ntb_calculator": "Calculating Net Tangible Benefit",
                        "recoupment_analyzer": "Analyzing Recoupment",
                        "refi_decision_agent": "Generating Decision",
                    }
                    display_name = readable_names.get(tool_name)
                    if display_name:
                        output_queue.put({"type": "tool", "content": display_name})
    
    return Agent(
        model=model,
        system_prompt=ORCHESTRATOR_PROMPT,
        tools=[
            package_validator,
            program_router,
            eligibility_checker,
            seasoning_validator,
            ntb_calculator,
            recoupment_analyzer,
            refi_decision_agent,
        ],
        callback_handler=streaming_callback
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[API] Streamline Government Refinance Agent")
    print("[API] Ready for FHA Streamline and VA IRRRL processing")
    yield
    print("[API] Shutting down...")


app = FastAPI(
    title="Streamline Government Refinance API",
    description="Multi-agent system for FHA Streamline and VA IRRRL refinance underwriting",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176",
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "streamline-refi-api"}


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Streaming chat for refinance processing with full multi-agent analysis."""
    
    async def generate() -> AsyncGenerator[str, None]:
        output_queue = queue.Queue()
        done_event = threading.Event()
        error_holder = [None]
        
        def run_agent():
            """Run orchestrator in thread - sub-agents run sequentially within."""
            try:
                orchestrator = create_streaming_orchestrator(output_queue)
                orchestrator(request.message)
            except Exception as e:
                error_holder[0] = str(e)
                output_queue.put({"type": "error", "content": str(e)})
            finally:
                output_queue.put({"type": "done", "content": ""})
                done_event.set()
        
        # Start orchestrator in background thread
        thread = threading.Thread(target=run_agent, daemon=True)
        thread.start()
        
        # Stream chunks as they arrive
        while not done_event.is_set() or not output_queue.empty():
            try:
                data = output_queue.get(timeout=0.05)
                yield f"data: {json.dumps(data)}\n\n"
                
                if data.get("type") in ("done", "error"):
                    break
            except queue.Empty:
                await asyncio.sleep(0.01)
                continue
        
        # Allow up to 3 minutes for full analysis
        thread.join(timeout=180.0)
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/applications")
async def list_applications():
    """List all refinance applications in the system."""
    from tools.refi_database_tools import get_cursor
    
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT 
                refi_id,
                borrower_name,
                existing_loan_type,
                current_note_rate,
                new_note_rate,
                (current_note_rate - new_note_rate) as rate_reduction,
                loan_status
            FROM refi_applications 
            ORDER BY refi_id
        """)
        results = cursor.fetchall()
        
        return {"applications": [
            {
                "refi_id": row["refi_id"],
                "borrower_name": row["borrower_name"],
                "program": row["existing_loan_type"],
                "current_rate": float(row["current_note_rate"]) if row["current_note_rate"] else 0,
                "new_rate": float(row["new_note_rate"]) if row["new_note_rate"] else 0,
                "rate_reduction": float(row["rate_reduction"]) if row["rate_reduction"] else 0,
                "status": row["loan_status"]
            }
            for row in results
        ]}


@app.get("/applications/{refi_id}")
async def get_application(refi_id: str):
    """Get details for a specific refinance application."""
    from tools.refi_database_tools import get_refi_application, get_payment_history, get_refi_documents
    
    app_data = get_refi_application(refi_id)
    payment_data = get_payment_history(refi_id)
    docs_data = get_refi_documents(refi_id)
    
    return {
        "application": json.loads(app_data),
        "payment_history": json.loads(payment_data),
        "documents": json.loads(docs_data)
    }


@app.get("/decisions")
async def list_decisions():
    """List all refinance decisions made."""
    from tools.refi_database_tools import get_cursor
    
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT 
                dl.id,
                dl.refi_id,
                ra.borrower_name,
                ra.existing_loan_type,
                dl.decision,
                dl.confidence_score,
                dl.reasoning,
                dl.created_at
            FROM refi_decision_log dl
            JOIN refi_applications ra ON dl.refi_id = ra.refi_id
            ORDER BY dl.created_at DESC
            LIMIT 20
        """)
        results = cursor.fetchall()
        
        return {"decisions": [
            {
                "id": row["id"],
                "refi_id": row["refi_id"],
                "borrower_name": row["borrower_name"],
                "program": row["existing_loan_type"],
                "decision": row["decision"],
                "confidence": float(row["confidence_score"]) if row["confidence_score"] else 0,
                "reasoning": row["reasoning"],
                "created_at": str(row["created_at"])
            }
            for row in results
        ]}


@app.get("/test-cases")
async def list_test_cases():
    """List all test cases with expected outcomes."""
    from tools.refi_database_tools import get_cursor
    
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT * FROM v_test_case_summary
        """)
        results = cursor.fetchall()
        
        return {"test_cases": [dict(row) for row in results]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
