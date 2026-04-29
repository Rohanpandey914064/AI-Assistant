"""
Tests for MCP Tools: Calculator, DB, API
"""

import sys
import os
import asyncio
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.mcp.tools.calc_tool import calculate
from backend.mcp.tools.db_tool import save_preference, get_preference, list_preferences, delete_preference


class TestCalculator:
    """Test the safe math calculator."""

    def test_basic_addition(self):
        assert calculate("2 + 3")["result"] == 5

    def test_multiplication(self):
        assert calculate("25 * 48")["result"] == 1200

    def test_sqrt(self):
        assert calculate("sqrt(144)")["result"] == 12.0

    def test_power(self):
        assert calculate("2 ** 10")["result"] == 1024

    def test_pi_constant(self):
        r = calculate("pi")
        assert abs(r["result"] - 3.14159265) < 0.001

    def test_complex_expression(self):
        r = calculate("sqrt(1764) + 15 * 3")
        assert r["success"]
        assert r["result"] == 87.0

    def test_division_by_zero(self):
        r = calculate("10 / 0")
        assert not r["success"]
        assert "zero" in r["error"].lower()

    def test_blocks_eval(self):
        r = calculate("__import__('os').system('ls')")
        assert not r["success"]

    def test_blocks_exec(self):
        r = calculate("exec('print(1)')")
        assert not r["success"]

    def test_empty_expression(self):
        r = calculate("")
        assert not r["success"]

    def test_long_expression(self):
        r = calculate("1+" * 300 + "1")
        assert r["success"]  # Should still work if valid


class TestDBTool:
    """Test the database CRUD tool."""

    def _get_temp_db(self):
        return os.path.join(tempfile.mkdtemp(), "test.db")

    def test_save_and_get(self):
        db = self._get_temp_db()
        save_preference("city", "Delhi", db_path=db)
        result = get_preference("city", db_path=db)
        assert result["found"]
        assert result["value"] == "Delhi"

    def test_update_preference(self):
        db = self._get_temp_db()
        save_preference("city", "Delhi", db_path=db)
        save_preference("city", "Mumbai", db_path=db)
        result = get_preference("city", db_path=db)
        assert result["value"] == "Mumbai"

    def test_list_preferences(self):
        db = self._get_temp_db()
        save_preference("city", "Delhi", db_path=db)
        save_preference("unit", "Celsius", db_path=db)
        result = list_preferences(db_path=db)
        assert result["count"] == 2

    def test_delete_preference(self):
        db = self._get_temp_db()
        save_preference("city", "Delhi", db_path=db)
        delete_preference("city", db_path=db)
        result = get_preference("city", db_path=db)
        assert not result["found"]

    def test_get_nonexistent(self):
        db = self._get_temp_db()
        result = get_preference("nonexistent", db_path=db)
        assert not result["found"]

    def test_empty_key_rejected(self):
        db = self._get_temp_db()
        result = save_preference("", "value", db_path=db)
        assert not result["success"]
