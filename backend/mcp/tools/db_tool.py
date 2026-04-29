"""
MCP Tool: Database (User Preferences & Session Data)
=====================================================
Provides safe CRUD operations on the SQLite database.
ALL queries use parameterized statements — SQL injection is impossible.

Tools exposed:
    - save_preference(key, value)
    - get_preference(key)
    - list_preferences()
    - delete_preference(key)
"""

import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_connection(db_path: str) -> sqlite3.Connection:
    """Create or connect to the SQLite database and ensure table exists."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent read performance

    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            key       TEXT NOT NULL UNIQUE,
            value     TEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


# ============================================================
# Tool Functions (called by MCP server)
# ============================================================

def save_preference(key: str, value: str, db_path: str = "./database/sentinel.db") -> dict:
    """
    Save or update a user preference in the database.

    Args:
        key:     Preference identifier (e.g., "city", "temperature_unit")
        value:   Value to store (e.g., "Delhi", "Celsius")
        db_path: Path to the SQLite database file.

    Returns:
        dict with success status and saved key/value.
    """
    if not key or not key.strip():
        return {"success": False, "error": "Key cannot be empty."}

    try:
        with _get_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO user_preferences (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key.strip().lower(), str(value).strip()),
            )
        logger.info(f"DB Tool: Saved preference [{key}] = [{value}]")
        return {"success": True, "key": key, "value": value}

    except sqlite3.Error as e:
        logger.error(f"DB Tool save_preference error: {e}")
        return {"success": False, "error": str(e)}


def get_preference(key: str, db_path: str = "./database/sentinel.db") -> dict:
    """
    Retrieve a specific user preference by key.

    Args:
        key:     The preference key to look up.
        db_path: Path to the SQLite database file.

    Returns:
        dict with found value or a not_found indicator.
    """
    try:
        with _get_connection(db_path) as conn:
            row = conn.execute(
                "SELECT key, value, updated_at FROM user_preferences WHERE key = ?",
                (key.strip().lower(),),
            ).fetchone()

        if row:
            result = {"found": True, "key": row["key"], "value": row["value"], "updated_at": row["updated_at"]}
        else:
            result = {"found": False, "key": key, "message": f"No preference found for key: '{key}'"}

        logger.info(f"DB Tool: Get [{key}] → {result}")
        return result

    except sqlite3.Error as e:
        logger.error(f"DB Tool get_preference error: {e}")
        return {"found": False, "error": str(e)}


def list_preferences(db_path: str = "./database/sentinel.db") -> dict:
    """
    List all stored user preferences.

    Returns:
        dict with a list of all key-value pairs.
    """
    try:
        with _get_connection(db_path) as conn:
            rows = conn.execute(
                "SELECT key, value, updated_at FROM user_preferences ORDER BY key"
            ).fetchall()

        preferences = [dict(row) for row in rows]
        logger.info(f"DB Tool: Listed {len(preferences)} preferences.")
        return {"success": True, "count": len(preferences), "preferences": preferences}

    except sqlite3.Error as e:
        logger.error(f"DB Tool list_preferences error: {e}")
        return {"success": False, "error": str(e)}


def delete_preference(key: str, db_path: str = "./database/sentinel.db") -> dict:
    """
    Delete a user preference by key.

    Returns:
        dict with success status.
    """
    try:
        with _get_connection(db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM user_preferences WHERE key = ?",
                (key.strip().lower(),),
            )

        if cursor.rowcount > 0:
            logger.info(f"DB Tool: Deleted preference [{key}]")
            return {"success": True, "message": f"Preference '{key}' deleted."}
        else:
            return {"success": False, "message": f"No preference found for key: '{key}'"}

    except sqlite3.Error as e:
        logger.error(f"DB Tool delete_preference error: {e}")
        return {"success": False, "error": str(e)}
