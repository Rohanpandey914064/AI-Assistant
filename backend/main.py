"""
Sentinel-Agent: FastAPI Main Server
=====================================
The central orchestrator that wires together all 3 gates,
the ReAct agent, and the MCP tool server.

Endpoints:
    POST /chat          — Main agent endpoint (full 3-gate pipeline)
    GET  /health        — Health check for Docker/CI
    GET  /memory/{id}   — View session memories
    DELETE /memory/{id} — Clear session memories
"""

import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from backend.config import get_settings
from backend.gates.gate1_security import scan_input
from backend.gates.gate3_validator import validate_output
from backend.agent.llm_client import LLMClient
from backend.agent.memory import VectorMemory
from backend.agent.react_loop import run_react_loop
from backend.observability.langfuse_client import AgentTrace
from backend.models.schemas import (
    ChatRequest, ChatResponse, GateResult,
    MemoryResponse, MemoryEntry, HealthResponse
)

# ============================================================
# Logging Configuration
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# ============================================================
# Singleton Resources (initialized once at startup)
# ============================================================

_llm_client: LLMClient | None = None
_memory: VectorMemory | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources at startup, clean up at shutdown."""
    global _llm_client, _memory

    logger.info("🚀 Sentinel-Agent starting up...")
    _llm_client = LLMClient()
    _memory = VectorMemory()
    logger.info("✅ LLM client and memory initialized.")

    yield  # Server is running

    logger.info("🛑 Sentinel-Agent shutting down...")


# ============================================================
# FastAPI Application
# ============================================================

app = FastAPI(
    title="Sentinel-Agent",
    description=(
        "A production-ready autonomous AI agent with a 3-Gate security pipeline, "
        "MCP tool integration, and persistent vector memory."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# API Endpoints
# ============================================================

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Health check endpoint for Docker and CI/CD pipelines."""
    return HealthResponse(
        status="ok",
        version="1.0.0",
        environment=settings.app_env,
    )


@app.post("/chat", response_model=ChatResponse, tags=["Agent"])
async def chat(request: ChatRequest):
    """
    Main agent endpoint — executes the full 3-Gate pipeline.

    Flow:
        1. Gate 1: Security scan (blocks prompt injection)
        2. Gate 2: ReAct reasoning loop (think → act → observe)
        3. Gate 3: Output validation (redacts PII/secrets)
    """
    logger.info(f"📨 New request | session={request.session_id} | len={len(request.message)}")

    # ─── GATE 1: Security Firewall ────────────────────────────────
    security_result = scan_input(request.message)

    if not security_result.is_safe:
        logger.warning(
            f"🚨 Gate 1 BLOCKED | session={request.session_id} | "
            f"threat={security_result.threat_type}"
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Request blocked by security gate.",
                "threat_type": security_result.threat_type,
                "message": security_result.message,
            },
        )

    # ─── GATE 2: ReAct Agent Loop ─────────────────────────────────
    with AgentTrace(session_id=request.session_id, user_input=request.message) as trace:
        # Log Gate 1 pass
        trace.log_gate1(
            is_safe=True,
            scan_time_ms=security_result.scan_time_ms,
        )

        # Run the reasoning engine
        agent_result = await run_react_loop(
            user_input=request.message,
            session_id=request.session_id,
            llm_client=_llm_client,
            memory=_memory,
            trace=trace,
        )

        raw_response = agent_result.answer

        # ─── GATE 3: Output Validation ────────────────────────────────
        validation_result = validate_output(raw_response)

        # Use redacted response if violations found
        final_response = validation_result.redacted_response

        trace.log_gate3(
            is_clean=validation_result.is_clean,
            violations=validation_result.violations,
        )
        trace.finalize(
            response=final_response,
            tools_used=agent_result.tools_used,
            total_iterations=agent_result.total_iterations,
        )

        logger.info(
            f"✅ Request complete | session={request.session_id} | "
            f"iterations={agent_result.total_iterations} | "
            f"tools={agent_result.tools_used} | "
            f"gate3_clean={validation_result.is_clean}"
        )

        return ChatResponse(
            session_id=request.session_id,
            response=final_response,
            tools_used=agent_result.tools_used,
            iterations=agent_result.total_iterations,
            security=GateResult(
                gate1_passed=True,
                gate1_threat=None,
                gate1_scan_ms=security_result.scan_time_ms,
                gate3_clean=validation_result.is_clean,
                gate3_violations=validation_result.violations,
            ),
            trace_url=trace.trace_url,
        )


@app.get("/memory/{session_id}", response_model=MemoryResponse, tags=["Memory"])
async def get_memory(session_id: str):
    """Retrieve all stored memories for a session."""
    if not _memory:
        raise HTTPException(status_code=503, detail="Memory service not initialized.")

    memories = _memory.get_all_session_memories(session_id)
    return MemoryResponse(
        session_id=session_id,
        count=len(memories),
        memories=[MemoryEntry(**m) for m in memories],
    )


@app.delete("/memory/{session_id}", tags=["Memory"])
async def clear_memory(session_id: str):
    """Clear all memories for a session."""
    if not _memory:
        raise HTTPException(status_code=503, detail="Memory service not initialized.")

    success = _memory.clear_session_memory(session_id)
    if success:
        return {"success": True, "message": f"Memory cleared for session: {session_id}"}
    raise HTTPException(status_code=500, detail="Failed to clear memory.")


# ============================================================
# Serve Frontend (production mode)
# ============================================================

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "development",
        log_level="info",
    )
