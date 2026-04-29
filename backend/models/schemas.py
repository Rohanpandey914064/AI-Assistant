"""
Pydantic v2 Request/Response Schemas
======================================
All API contracts are defined here with strict validation.
"""

from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    session_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Unique session identifier for memory continuity.",
        examples=["user-123-session-abc"],
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="The user's input message.",
        examples=["What's the weather in Delhi?"],
    )


class GateResult(BaseModel):
    gate1_passed: bool = Field(..., description="Did the request pass Gate 1 security check?")
    gate1_threat: Optional[str] = Field(None, description="Threat type detected (if any).")
    gate1_scan_ms: float = Field(0.0, description="Gate 1 scan duration in milliseconds.")
    gate3_clean: bool = Field(..., description="Was the output clean (no PII/secrets)?")
    gate3_violations: list[str] = Field(default_factory=list, description="List of PII/secret violations found.")


class ChatResponse(BaseModel):
    session_id: str
    response: str = Field(..., description="The agent's final response to the user.")
    tools_used: list[str] = Field(default_factory=list, description="List of tools invoked during reasoning.")
    iterations: int = Field(..., description="Number of ReAct loop iterations.")
    security: GateResult
    trace_url: Optional[str] = Field(None, description="Langfuse trace URL for this request.")


class MemoryEntry(BaseModel):
    content: str
    created_at: str


class MemoryResponse(BaseModel):
    session_id: str
    count: int
    memories: list[MemoryEntry]


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    environment: str
