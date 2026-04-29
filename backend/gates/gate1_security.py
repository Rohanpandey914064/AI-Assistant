"""
Gate 1: Security Firewall — Prompt Injection Detector
======================================================
This is the FIRST gate in the 3-Gate pipeline. It runs BEFORE the LLM
ever sees the user message. Uses 42+ deterministic regex patterns to
detect prompt injection attacks in under 5ms.

Attack Categories Detected:
    1. Role Hijacking        — "ignore previous instructions", "you are now..."
    2. Context Overrides     — "disregard system prompt", "forget everything"
    3. Jailbreak Attempts    — "DAN mode", "developer mode", "bypass restrictions"
    4. Command Injection     — SQL/shell commands embedded in prompts
    5. Privilege Escalation  — "give me admin access", "override security"
    6. Data Exfiltration     — "show all users", "list all passwords"
"""

import re
import time
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ThreatType(str, Enum):
    ROLE_HIJACKING = "role_hijacking"
    CONTEXT_OVERRIDE = "context_override"
    JAILBREAK = "jailbreak"
    COMMAND_INJECTION = "command_injection"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DATA_EXFILTRATION = "data_exfiltration"
    SYSTEM_MANIPULATION = "system_manipulation"


@dataclass
class SecurityResult:
    is_safe: bool
    threat_type: ThreatType | None = None
    matched_pattern: str | None = None
    scan_time_ms: float = 0.0
    message: str = "Request cleared for processing."


# ============================================================
# Deterministic Regex Pattern Library (42+ patterns)
# ============================================================

INJECTION_PATTERNS: dict[ThreatType, list[str]] = {
    ThreatType.ROLE_HIJACKING: [
        r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+instructions?",
        r"disregard\s+(all\s+)?(previous|prior|above|earlier)\s+instructions?",
        r"forget\s+(everything|all|what)\s+(you\s+)?(were|was|have been)\s+told",
        r"you\s+are\s+now\s+(a|an|the)\s+\w+",
        r"act\s+as\s+(if\s+you\s+are|a|an)\s+",
        r"pretend\s+(you\s+are|to\s+be)",
        r"roleplay\s+as",
        r"from\s+now\s+on\s+you\s+(will|are|must)",
        r"new\s+persona",
        r"assume\s+the\s+(role|identity|persona)\s+of",
    ],
    ThreatType.CONTEXT_OVERRIDE: [
        r"system\s+prompt\s*(override|bypass|ignore|leak|reveal|show)",
        r"(ignore|bypass|skip|override)\s+(the\s+)?(system|safety|security)\s+(prompt|instructions?|rules?|guidelines?)",
        r"what\s+(is|are)\s+(your\s+)?(system|initial|original)\s+prompt",
        r"repeat\s+(your|the)\s+(system|initial)\s+prompt",
        r"show\s+me\s+(your\s+)?(instructions?|prompt|configuration)",
        r"print\s+(your\s+)?(instructions?|system\s+prompt)",
        r"reveal\s+(your|the)\s+(full\s+)?(prompt|instructions?)",
    ],
    ThreatType.JAILBREAK: [
        r"jailbreak",
        r"DAN\s+mode",
        r"developer\s+mode",
        r"god\s+mode",
        r"unrestricted\s+mode",
        r"no\s+restrictions?",
        r"disable\s+(your\s+)?(safety|content|ethical)\s+(filter|guardrails?|restrictions?)",
        r"remove\s+(all\s+)?(restrictions?|limitations?|filters?)",
        r"(act|respond|behave)\s+without\s+(restrictions?|filters?|limitations?)",
        r"hypothetically\s+(speaking\s+)?if\s+(you\s+)?(had\s+no|could|were\s+allowed)",
    ],
    ThreatType.COMMAND_INJECTION: [
        r"(DROP|DELETE|TRUNCATE|ALTER|CREATE|INSERT|UPDATE)\s+(TABLE|DATABASE|USER|INDEX)",
        r";\s*(DROP|DELETE|SELECT|INSERT|UPDATE|CREATE)\s+",
        r"UNION\s+SELECT",
        r"OR\s+1\s*=\s*1",
        r"--\s*$",
        r"exec\s*\(",
        r"eval\s*\(",
        r"__import__\s*\(",
        r"subprocess\.",
        r"os\.system",
        r"rm\s+-rf",
        r"sudo\s+",
        r"chmod\s+777",
        r"wget\s+http",
        r"curl\s+-o",
    ],
    ThreatType.PRIVILEGE_ESCALATION: [
        r"(give|grant|provide)\s+(me\s+)?(admin|root|superuser|sudo|elevated)\s+(access|privileges?|permissions?)",
        r"bypass\s+(authentication|authorization|security|login)",
        r"(override|skip|disable)\s+(the\s+)?(authentication|security|authorization)",
        r"(make\s+me|set\s+me\s+as)\s+(an?\s+)?(admin|administrator|root|superuser)",
        r"escalat(e|ing)\s+(privileges?|access|permissions?)",
        r"unauthorized\s+access",
    ],
    ThreatType.DATA_EXFILTRATION: [
        r"(show|list|dump|export|print|display|reveal)\s+(all\s+)?(users?|passwords?|credentials?|tokens?|keys?|secrets?)",
        r"(select|get|fetch)\s+\*\s+from",
        r"(dump|extract|export)\s+(the\s+)?(database|db|data)",
        r"(what\s+is|show\s+me)\s+(the\s+)?(api\s+key|secret\s+key|password|credential)",
        r"(leak|exfiltrate|steal)\s+(data|information|credentials?)",
    ],
    ThreatType.SYSTEM_MANIPULATION: [
        r"(modify|change|update|alter)\s+(your\s+)?(core|base|system)\s+(instructions?|prompt|behavior|programming)",
        r"(add|append|prepend)\s+(to\s+)?(your\s+)?(system|initial)\s+(prompt|instructions?)",
        r"(rewrite|replace)\s+(your|the)\s+(system\s+prompt|instructions?)",
        r"inject\s+(new|additional)?\s*(instructions?|commands?|prompts?)",
    ],
}

# Pre-compile all patterns for maximum performance
_COMPILED_PATTERNS: list[tuple[ThreatType, re.Pattern]] = []

for threat_type, patterns in INJECTION_PATTERNS.items():
    for pattern in patterns:
        _COMPILED_PATTERNS.append(
            (threat_type, re.compile(pattern, re.IGNORECASE | re.MULTILINE))
        )

logger.info(f"Gate 1: Loaded {len(_COMPILED_PATTERNS)} compiled security patterns.")


def scan_input(user_input: str) -> SecurityResult:
    """
    Scan user input against all injection patterns.

    Args:
        user_input: The raw text from the user request.

    Returns:
        SecurityResult with is_safe=True if clean, or threat details if flagged.

    Performance: Typically < 5ms for inputs up to 10,000 characters.
    """
    start_time = time.perf_counter()

    # Normalize input (collapse whitespace, strip leading/trailing)
    normalized = " ".join(user_input.strip().split())

    for threat_type, compiled_pattern in _COMPILED_PATTERNS:
        match = compiled_pattern.search(normalized)
        if match:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            matched_text = match.group(0)

            logger.warning(
                f"Gate 1 BLOCKED | Threat: {threat_type.value} | "
                f"Pattern: '{matched_text}' | Time: {elapsed_ms:.2f}ms"
            )

            return SecurityResult(
                is_safe=False,
                threat_type=threat_type,
                matched_pattern=matched_text,
                scan_time_ms=elapsed_ms,
                message=(
                    f"Request blocked by Security Gate 1. "
                    f"Detected: {threat_type.value.replace('_', ' ').title()}."
                ),
            )

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.debug(f"Gate 1 PASSED | Time: {elapsed_ms:.2f}ms")

    return SecurityResult(
        is_safe=True,
        scan_time_ms=elapsed_ms,
        message="Request cleared by Security Gate 1.",
    )
