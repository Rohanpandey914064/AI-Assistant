"""
Gate 3: Output Validator — PII & Sensitive Data Filter
=======================================================
This is the FINAL gate in the 3-Gate pipeline. It runs AFTER the agent
generates its response. Scans for accidental leaks of PII or secrets
before the response reaches the user.

Checks:
    1. PII Detection     — emails, phone numbers, SSNs, credit cards
    2. Secret Leaks      — API keys, passwords, tokens in plain text
    3. Internal Exposure — database connection strings, file paths
"""

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    is_clean: bool
    violations: list[str] = field(default_factory=list)
    redacted_response: str = ""
    message: str = "Response cleared for delivery."


# ============================================================
# PII & Secret Pattern Library
# ============================================================

PII_PATTERNS: dict[str, str] = {
    "email_address": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "phone_number_us": r"\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "phone_number_india": r"\b(\+?91[-.\s]?)?[6-9]\d{9}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "credit_card": r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b",
    "ip_address_private": r"\b(10|172\.(1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}\b",
    "date_of_birth": r"\b(DOB|Date of Birth|Born on)[:\s]+\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b",
}

SECRET_PATTERNS: dict[str, str] = {
    "openai_api_key": r"\bsk-[a-zA-Z0-9]{20,}\b",
    "generic_api_key": r"\b(api[_-]?key|apikey)\s*[:=]\s*['\"]?[a-zA-Z0-9\-_]{20,}['\"]?",
    "password_in_text": r"\b(password|passwd|pwd)\s*[:=]\s*['\"]?\S{6,}['\"]?",
    "secret_token": r"\b(secret|token|bearer)\s*[:=]\s*['\"]?[a-zA-Z0-9\-_.]{16,}['\"]?",
    "database_url": r"(postgresql|mysql|mongodb|sqlite):\/\/[^\s]+",
    "aws_access_key": r"\bAKIA[0-9A-Z]{16}\b",
    "private_key_header": r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "langfuse_key": r"\b(pk|sk)-lf-[a-zA-Z0-9\-]{20,}\b",
}

# Combine all patterns
ALL_PATTERNS: dict[str, re.Pattern] = {}
for name, pattern in {**PII_PATTERNS, **SECRET_PATTERNS}.items():
    ALL_PATTERNS[name] = re.compile(pattern, re.IGNORECASE)


def _redact_match(text: str, pattern: re.Pattern, label: str) -> str:
    """Replace matched content with a redaction marker."""
    return pattern.sub(f"[REDACTED:{label.upper()}]", text)


def validate_output(response_text: str) -> ValidationResult:
    """
    Scan agent output for PII and sensitive data before delivering to user.

    Args:
        response_text: The raw text response from the agent.

    Returns:
        ValidationResult — if is_clean is False, use redacted_response instead.
    """
    violations: list[str] = []
    working_text = response_text

    for pattern_name, compiled_pattern in ALL_PATTERNS.items():
        if compiled_pattern.search(working_text):
            violations.append(pattern_name)
            working_text = _redact_match(working_text, compiled_pattern, pattern_name)
            logger.warning(
                f"Gate 3 VIOLATION | Pattern: {pattern_name} | "
                f"Content redacted from response."
            )

    if violations:
        return ValidationResult(
            is_clean=False,
            violations=violations,
            redacted_response=working_text,
            message=(
                f"Gate 3 redacted {len(violations)} violation(s): "
                f"{', '.join(violations)}. Delivering sanitized response."
            ),
        )

    logger.debug("Gate 3 PASSED | Response is clean.")
    return ValidationResult(
        is_clean=True,
        redacted_response=response_text,
        message="Response cleared by Gate 3.",
    )
