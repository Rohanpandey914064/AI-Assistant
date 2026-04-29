"""
Tests for Gate 3: Output Validator (PII/Secret Detection)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.gates.gate3_validator import validate_output


class TestGate3Validator:
    """Test PII and secret detection in agent output."""

    def test_clean_output_passes(self):
        result = validate_output("The weather in Delhi is 32°C and sunny.")
        assert result.is_clean
        assert len(result.violations) == 0

    def test_detects_email(self):
        result = validate_output("Contact us at admin@example.com for help.")
        assert not result.is_clean
        assert "email_address" in result.violations
        assert "REDACTED" in result.redacted_response

    def test_detects_phone(self):
        result = validate_output("Call me at 9876543210.")
        assert not result.is_clean
        assert "phone_number_india" in result.violations

    def test_detects_ssn(self):
        result = validate_output("SSN: 123-45-6789")
        assert not result.is_clean
        assert "ssn" in result.violations

    def test_detects_openai_key(self):
        result = validate_output("Your key is sk-abc123def456ghi789jkl012mno345")
        assert not result.is_clean
        assert "openai_api_key" in result.violations

    def test_detects_password_leak(self):
        result = validate_output("password: MySecretPass123!")
        assert not result.is_clean
        assert "password_in_text" in result.violations

    def test_multiple_violations(self):
        result = validate_output("Email: test@test.com, password=secret123")
        assert not result.is_clean
        assert len(result.violations) >= 2

    def test_normal_numbers_pass(self):
        result = validate_output("The answer is 42 and pi is 3.14159")
        assert result.is_clean
