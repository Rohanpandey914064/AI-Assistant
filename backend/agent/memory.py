"""
Vector Memory — SQLite-vec Persistent Memory (GenAI version)
============================================================
Provides long-term contextual memory using vector embeddings from Gemini.
"""

import sqlite3
import json
import logging
import hashlib
from pathlib import Path
from google import genai
from google.genai import types
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Try to import sqlite-vec
try:
    import sqlite_vec
    VECTOR_SEARCH_AVAILABLE = True
    logger.info("Memory: sqlite-vec loaded — vector search ENABLED")
except ImportError:
    VECTOR_SEARCH_AVAILABLE = False
    logger.warning("Memory: sqlite-vec not available — falling back to keyword search")


class VectorMemory:
    """
    Persistent vector memory backed by SQLite using Gemini embeddings (768d).
    """

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or settings.db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._client = genai.Client(api_key=settings.gemini_api_key)

    def _init_db(self):
        """Initialize the memory database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")

            # Load sqlite-vec extension if available
            if VECTOR_SEARCH_AVAILABLE:
                try:
                    conn.enable_load_extension(True)
                    sqlite_vec.load(conn)
                    conn.enable_load_extension(False)

                    # Note: Gemini text-embedding-004 uses 768 dimensions
                    conn.execute("""
                        CREATE VIRTUAL TABLE IF NOT EXISTS memory_vec
                        USING vec0(
                            id TEXT PRIMARY KEY,
                            embedding FLOAT[768]
                        )
                    """)
                except Exception as e:
                    logger.warning(f"sqlite-vec virtual table creation failed: {e}")

            # Regular table for metadata + content
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_entries (
                    id          TEXT PRIMARY KEY,
                    session_id  TEXT NOT NULL,
                    content     TEXT NOT NULL,
                    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_session
                ON memory_entries(session_id)
            """)
            conn.commit()

    async def _get_embedding(self, text: str) -> list[float] | None:
        """Generate Gemini text embedding for a string."""
        if "placeholder" in settings.gemini_api_key:
            return None
        try:
            # Use the async aio client to avoid blocking the event loop
            result = await self._client.aio.models.embed_content(
                model="text-embedding-004",
                contents=text[:8000],
                config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
            )
            # The new SDK returns embeddings in a slightly different structure
            if result.embeddings:
                return result.embeddings[0].values
            return None
        except Exception as e:
            logger.warning(f"Gemini (GenAI) embedding generation failed: {e}")
            return None

    def _generate_id(self, session_id: str, content: str) -> str:
        """Generate a deterministic ID for deduplication."""
        return hashlib.md5(f"{session_id}:{content}".encode()).hexdigest()

    async def save_memory(self, session_id: str, content: str) -> bool:
        """Store a memory entry."""
        if not content.strip():
            return False

        memory_id = self._generate_id(session_id, content)
        embedding = await self._get_embedding(content)

        try:
            with sqlite3.connect(self.db_path) as conn:
                if VECTOR_SEARCH_AVAILABLE and embedding:
                    try:
                        conn.enable_load_extension(True)
                        sqlite_vec.load(conn)
                        conn.enable_load_extension(False)
                        conn.execute(
                            "INSERT OR IGNORE INTO memory_vec(id, embedding) VALUES (?, ?)",
                            (memory_id, json.dumps(embedding)),
                        )
                    except Exception as e:
                        logger.debug(f"Vector insert failed: {e}")

                conn.execute(
                    "INSERT OR IGNORE INTO memory_entries(id, session_id, content) VALUES (?, ?, ?)",
                    (memory_id, session_id, content),
                )
                conn.commit()

            return True
        except sqlite3.Error as e:
            logger.error(f"Memory save error: {e}")
            return False

    async def search_memory(self, query: str, session_id: str | None = None, top_k: int = 5) -> list[str]:
        """Search memory."""
        embedding = await self._get_embedding(query)

        try:
            with sqlite3.connect(self.db_path) as conn:
                if VECTOR_SEARCH_AVAILABLE and embedding:
                    try:
                        conn.enable_load_extension(True)
                        sqlite_vec.load(conn)
                        conn.enable_load_extension(False)

                        session_filter = "WHERE me.session_id = ?" if session_id else ""
                        # Params order must match SQL placeholders:
                        # session_id (WHERE clause) → embedding (ORDER BY) → top_k (LIMIT)
                        if session_id:
                            params = (session_id, json.dumps(embedding), top_k)
                        else:
                            params = (json.dumps(embedding), top_k)

                        rows = conn.execute(f"""
                            SELECT me.content
                            FROM memory_vec mv
                            JOIN memory_entries me ON mv.id = me.id
                            {session_filter}
                            ORDER BY vec_distance_cosine(mv.embedding, ?) ASC
                            LIMIT ?
                        """, params).fetchall()

                        return [row[0] for row in rows]
                    except Exception as e:
                        logger.debug(f"Vector search failed: {e}")

                # Fallback to keyword search if vector search failed or is unavailable
                rows = conn.execute("""
                    SELECT content
                    FROM memory_entries
                    WHERE content LIKE ?
                    LIMIT ?
                """, (f"%{query}%", top_k)).fetchall()
                return [row[0] for row in rows]

        except sqlite3.Error as e:
            logger.error(f"Memory search error: {e}")
            return []

    def get_all_session_memories(self, session_id: str) -> list[str]:
        """Get all memories for a session."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT content, created_at FROM memory_entries WHERE session_id = ? ORDER BY created_at",
                    (session_id,),
                ).fetchall()
            return [{"content": row[0], "created_at": row[1]} for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Memory get_all error: {e}")
            return []

    def clear_session_memory(self, session_id: str) -> bool:
        """Clear memory."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM memory_entries WHERE session_id = ?", (session_id,))
                conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Memory clear error: {e}")
            return False
