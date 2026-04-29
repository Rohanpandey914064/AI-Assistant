"""
ReAct Loop — The Agent's Reasoning Engine (Gate 2)
====================================================
Implements the ReAct (Reasoning + Acting) pattern:
    THINK → What does the user want? What tool do I need?
    ACT   → Call the appropriate tool with the right parameters
    OBSERVE → Read the tool result
    REPEAT → Until FINAL_ANSWER or max_iterations reached

Key Features:
    - Max iteration cap to prevent infinite loops
    - Error Feedback Loop: tool errors are fed back to the LLM for self-correction
    - Tool result injection into conversation history
    - Full trace logging via Langfuse
"""

import json
import logging
import asyncio
from typing import Any
from dataclasses import dataclass, field

from backend.agent.llm_client import LLMClient
from backend.agent.memory import VectorMemory
from backend.mcp.tools import db_tool, api_tool, calc_tool
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ============================================================
# Tool Executor — Dispatches to the correct tool function
# ============================================================

async def _execute_tool(tool_name: str, action_input: dict) -> Any:
    """
    Execute a named tool with given parameters.
    Returns the tool result or an error dict if the tool fails/doesn't exist.
    """
    try:
        if tool_name == "save_preference":
            return db_tool.save_preference(**action_input)

        elif tool_name == "get_preference":
            return db_tool.get_preference(**action_input)

        elif tool_name == "list_preferences":
            return db_tool.list_preferences()

        elif tool_name == "delete_preference":
            return db_tool.delete_preference(**action_input)

        elif tool_name == "get_weather":
            return await api_tool.get_weather(**action_input)

        elif tool_name == "get_news":
            return await api_tool.get_news(**action_input)

        elif tool_name == "calculate":
            return calc_tool.calculate(**action_input)

        else:
            return {"error": f"Unknown tool: '{tool_name}'. Check tool name spelling."}

    except TypeError as e:
        # Wrong arguments passed to tool — feed error back to LLM for self-correction
        return {"error": f"Invalid arguments for tool '{tool_name}': {str(e)}"}

    except Exception as e:
        logger.error(f"Tool execution error [{tool_name}]: {e}")
        return {"error": f"Tool '{tool_name}' failed: {str(e)}"}


# ============================================================
# Result Dataclass
# ============================================================

@dataclass
class AgentResult:
    answer: str
    tools_used: list[str] = field(default_factory=list)
    total_iterations: int = 0
    total_tokens: int = 0
    error: str | None = None


# ============================================================
# ReAct Loop
# ============================================================

async def run_react_loop(
    user_input: str,
    session_id: str,
    llm_client: LLMClient,
    memory: VectorMemory,
    trace=None,  # AgentTrace (optional, for Langfuse)
) -> AgentResult:
    """
    Execute the ReAct reasoning loop for a user request.

    Flow:
        1. Retrieve relevant memory context
        2. THINK: Ask LLM what to do next
        3. ACT:   Execute the chosen tool
        4. OBSERVE: Feed result back to LLM
        5. Repeat until FINAL_ANSWER or max iterations
        6. Save key facts to memory for future sessions

    Args:
        user_input:  The user's sanitized (Gate 1 passed) message.
        session_id:  The conversation session identifier.
        llm_client:  Initialized LLMClient instance.
        memory:      Initialized VectorMemory instance.
        trace:       Optional Langfuse AgentTrace for observability.

    Returns:
        AgentResult with the final answer and metadata.
    """
    max_iterations = settings.max_react_iterations
    messages: list[dict] = [{"role": "user", "content": user_input}]
    tools_used: list[str] = []
    total_tokens: int = 0
    iteration: int = 0

    # Step 1: Retrieve relevant memory context
    memory_context = None
    try:
        relevant_memories = await memory.search_memory(user_input, session_id=session_id, top_k=5)
        if relevant_memories:
            memory_context = "Relevant facts from past conversations:\n" + "\n".join(
                f"- {m}" for m in relevant_memories
            )
            logger.debug(f"Memory context: {len(relevant_memories)} relevant facts loaded.")
    except Exception as e:
        logger.warning(f"Memory retrieval failed (non-fatal): {e}")

    # Step 2: ReAct Loop
    while iteration < max_iterations:
        iteration += 1
        logger.info(f"ReAct Iteration {iteration}/{max_iterations}")

        try:
            # THINK: Ask LLM what to do
            llm_response = await llm_client.get_next_action(
                messages=messages,
                context=memory_context,
            )
        except Exception as e:
            logger.error(f"LLM call failed at iteration {iteration}: {e}")
            return AgentResult(
                answer="I encountered an error while processing your request. Please try again.",
                tools_used=tools_used,
                total_iterations=iteration,
                total_tokens=total_tokens,
                error=str(e),
            )

        thought = llm_response.get("thought", "")
        action = llm_response.get("action", "FINAL_ANSWER")
        action_input = llm_response.get("action_input", {})
        total_tokens += llm_response.get("_tokens", 0)

        logger.info(f"  THOUGHT: {thought}")
        logger.info(f"  ACTION:  {action}")
        logger.info(f"  INPUT:   {json.dumps(action_input, ensure_ascii=False)[:200]}")

        # Check for FINAL ANSWER
        if action == "FINAL_ANSWER":
            final_answer = action_input.get("answer", "")

            # Log final iteration to trace
            if trace:
                trace.log_react_iteration(iteration, thought, "FINAL_ANSWER", action_input, final_answer)

            logger.info(f"ReAct complete: {iteration} iterations, {total_tokens} tokens.")

            # Step 3: Save this exchange to memory for future sessions
            try:
                await memory.save_memory(
                    session_id=session_id,
                    content=f"User asked: {user_input[:500]}. Agent answered: {final_answer[:300]}",
                )
            except Exception as e:
                logger.warning(f"Memory save failed (non-fatal): {e}")

            return AgentResult(
                answer=final_answer,
                tools_used=tools_used,
                total_iterations=iteration,
                total_tokens=total_tokens,
            )

        # ACT: Execute the chosen tool
        logger.info(f"  Executing tool: {action}")
        observation = await _execute_tool(action, action_input)

        # Track tools used (avoid duplicates)
        if action not in tools_used:
            tools_used.append(action)

        logger.info(f"  OBSERVATION: {str(observation)[:300]}")

        # Log iteration to Langfuse
        if trace:
            trace.log_react_iteration(iteration, thought, action, action_input, observation)

        # OBSERVE: Feed tool result back into conversation
        tool_result_message = (
            f"Tool '{action}' result:\n{json.dumps(observation, ensure_ascii=False, indent=2)}"
        )

        # Add tool call + result to message history
        messages.append({"role": "assistant", "content": json.dumps(llm_response)})
        messages.append({"role": "user", "content": tool_result_message})

    # Max iterations reached without FINAL_ANSWER
    logger.warning(f"ReAct loop hit max iterations ({max_iterations}) without FINAL_ANSWER.")
    return AgentResult(
        answer=(
            "I wasn't able to complete your request within the allowed number of steps. "
            "Could you rephrase or simplify your request?"
        ),
        tools_used=tools_used,
        total_iterations=iteration,
        total_tokens=total_tokens,
        error="max_iterations_exceeded",
    )
