"""
Langfuse Observability Client
==============================
Wraps every agent run in a Langfuse trace for full observability.
Records Gate 1 results, each ReAct iteration, Gate 3 results, and
total latency / token usage.

Features:
    - Trace per request (with shareable URL)
    - Span per ReAct iteration
    - Event logging for gate pass/fail decisions
    - Graceful no-op when Langfuse is not configured
"""

import logging
import time
from typing import Any
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Try to import Langfuse — gracefully degrade if not available
try:
    from langfuse import Langfuse
    _langfuse_client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
    LANGFUSE_ENABLED = (
        "placeholder" not in settings.langfuse_public_key
        and "placeholder" not in settings.langfuse_secret_key
    )
    if LANGFUSE_ENABLED:
        logger.info("Langfuse observability: ENABLED")
    else:
        logger.info("Langfuse observability: DISABLED (placeholder keys detected)")
except Exception as e:
    _langfuse_client = None
    LANGFUSE_ENABLED = False
    logger.warning(f"Langfuse not available: {e}")


class AgentTrace:
    """
    Context manager for tracing a full agent request lifecycle.

    Usage:
        async with AgentTrace(session_id="abc", user_input="What's the weather?") as trace:
            trace.log_gate1(is_safe=True, scan_time_ms=2.3)
            trace.log_react_iteration(1, thought="...", action="get_weather", observation={...})
            trace.log_gate3(is_clean=True, violations=[])
            trace.finalize(response="It's sunny!", tokens_used=120)
    """

    def __init__(self, session_id: str, user_input: str):
        self.session_id = session_id
        self.user_input = user_input
        self.start_time = time.time()
        self._trace = None
        self._current_span = None
        self.trace_url: str | None = None
        self._iteration_spans: list = []

    def __enter__(self):
        if LANGFUSE_ENABLED and _langfuse_client:
            try:
                self._trace = _langfuse_client.trace(
                    name="sentinel-agent-request",
                    session_id=self.session_id,
                    input=self.user_input,
                    metadata={"session_id": self.session_id},
                )
                self.trace_url = (
                    f"{settings.langfuse_host}/trace/{self._trace.id}"
                    if self._trace else None
                )
            except Exception as e:
                logger.warning(f"Langfuse trace creation failed: {e}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._trace:
            try:
                self._trace.update(
                    status_message="error" if exc_type else "success",
                )
                _langfuse_client.flush()
            except Exception as e:
                logger.warning(f"Langfuse trace finalization failed: {e}")

    def log_gate1(self, is_safe: bool, threat_type: str | None = None, scan_time_ms: float = 0):
        """Record Gate 1 security check result."""
        if not self._trace:
            return
        try:
            self._trace.event(
                name="gate1_security_check",
                input={"user_input_length": len(self.user_input)},
                output={
                    "is_safe": is_safe,
                    "threat_type": threat_type,
                    "scan_time_ms": scan_time_ms,
                },
                level="DEFAULT" if is_safe else "WARNING",
            )
        except Exception as e:
            logger.debug(f"Langfuse gate1 log failed: {e}")

    def log_react_iteration(
        self,
        iteration: int,
        thought: str,
        action: str | None,
        action_input: dict | None,
        observation: Any,
    ):
        """Record a single ReAct loop iteration."""
        if not self._trace:
            return
        try:
            span = self._trace.span(
                name=f"react_iteration_{iteration}",
                input={"thought": thought, "action": action, "action_input": action_input},
                output={"observation": str(observation)[:1000]},  # Truncate large outputs
            )
            self._iteration_spans.append(span)
        except Exception as e:
            logger.debug(f"Langfuse react iteration log failed: {e}")

    def log_gate3(self, is_clean: bool, violations: list[str]):
        """Record Gate 3 output validation result."""
        if not self._trace:
            return
        try:
            self._trace.event(
                name="gate3_output_validation",
                output={"is_clean": is_clean, "violations": violations},
                level="DEFAULT" if is_clean else "WARNING",
            )
        except Exception as e:
            logger.debug(f"Langfuse gate3 log failed: {e}")

    def finalize(self, response: str, tools_used: list[str], total_iterations: int):
        """Record the final response and summary metadata."""
        if not self._trace:
            return
        total_time_ms = (time.time() - self.start_time) * 1000
        try:
            self._trace.update(
                output=response,
                metadata={
                    "tools_used": tools_used,
                    "total_iterations": total_iterations,
                    "total_time_ms": round(total_time_ms, 2),
                },
            )
        except Exception as e:
            logger.debug(f"Langfuse finalize failed: {e}")
