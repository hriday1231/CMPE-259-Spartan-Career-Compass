"""on-disk prompt cache keyed on (model_name, full_prompt_hash)

independent of Ollama's own kv-cache so we can benchmark "with caching"
vs "without caching" latency from the application's perspective
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import PROMPT_CACHE_PATH


def _ensure_db() -> sqlite3.Connection:
    PROMPT_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(PROMPT_CACHE_PATH))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS prompt_cache (
            key TEXT PRIMARY KEY,
            model TEXT NOT NULL,
            prompt_hash TEXT NOT NULL,
            response TEXT NOT NULL,
            latency_ms INTEGER,
            created_at REAL NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def _messages_to_key(model: str, messages: Iterable) -> tuple[str, str]:
    parts = []
    for m in messages:
        role = getattr(m, "type", getattr(m, "role", "msg"))
        content = getattr(m, "content", str(m))
        parts.append(f"{role}:{content}")
    blob = json.dumps({"model": model, "messages": parts}, ensure_ascii=False)
    h = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    return h, blob


def get(model: str, messages: Iterable) -> str | None:
    key, _ = _messages_to_key(model, messages)
    conn = _ensure_db()
    try:
        cur = conn.execute("SELECT response FROM prompt_cache WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def put(model: str, messages: Iterable, response: str, latency_ms: int | None = None) -> None:
    key, _ = _messages_to_key(model, messages)
    h = key
    conn = _ensure_db()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO prompt_cache
            (key, model, prompt_hash, response, latency_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (key, model, h, response, latency_ms, time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def clear() -> int:
    conn = _ensure_db()
    try:
        cur = conn.execute("DELETE FROM prompt_cache")
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def stats() -> dict:
    conn = _ensure_db()
    try:
        cur = conn.execute("SELECT COUNT(*), AVG(latency_ms) FROM prompt_cache")
        count, avg_latency = cur.fetchone()
        return {"entries": count or 0, "avg_stored_latency_ms": avg_latency}
    finally:
        conn.close()


def cached_invoke(llm, messages) -> str:
    """invoke a langchain chat model with transparent caching

    returns assistant text - on cache hit no network call is made
    """
    model_name = getattr(llm, "model", None) or getattr(llm, "model_name", "unknown")
    hit = get(model_name, messages)
    if hit is not None:
        return hit
    t0 = time.time()
    response = llm.invoke(messages)
    latency_ms = int((time.time() - t0) * 1000)
    text = response.content if hasattr(response, "content") else str(response)
    put(model_name, messages, text, latency_ms=latency_ms)
    return text
