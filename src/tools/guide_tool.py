"""keyword search across the 11 Career Center PDF guides loaded as chunks"""

import sqlite3
import sys
from pathlib import Path

from langchain_core.tools import tool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config import DB_PATH


def _get_conn():
    return sqlite3.connect(str(DB_PATH))


@tool
def search_guides_tool(
    query: str,
    guide_title: str = "",
    max_chunks: int = 4,
) -> str:
    """search Career Center PDF guides by keyword, returns top chunks with title and page numbers"""
    conn = _get_conn()
    cur = conn.cursor()
    try:
        words = [w.strip() for w in query.split() if len(w.strip()) > 1]
        if not words:
            return "Please provide a search query (e.g. resume, interview, career fair)."

        or_conds = " OR ".join(["text LIKE ? COLLATE NOCASE" for _ in words])
        params = [f"%{w}%" for w in words]

        # body match counts +1 per matching word, title match counts +2 per
        # matching word - title hits dominate so resume questions surface
        # the resume guide first
        score_parts = " + ".join(["CASE WHEN text LIKE ? COLLATE NOCASE THEN 1 ELSE 0 END" for _ in words])
        score_params = [f"%{w}%" for w in words]

        title_score_parts = " + ".join(["CASE WHEN title LIKE ? COLLATE NOCASE THEN 2 ELSE 0 END" for _ in words])
        title_score_params = [f"%{w}%" for w in words]

        all_params = score_params + title_score_params + params

        title_filter = ""
        if guide_title:
            title_filter = "AND title LIKE ? COLLATE NOCASE"
            all_params.append(f"%{guide_title}%")

        all_params.append(max_chunks)

        cur.execute(
            f"""
            SELECT title, section, text, page_start, page_end, source_pdf,
                   ({score_parts} + {title_score_parts}) AS relevance
            FROM guides
            WHERE ({or_conds}) {title_filter}
            ORDER BY relevance DESC, title, page_start
            LIMIT ?
            """,
            all_params,
        )
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
    finally:
        cur.close()
        conn.close()

    if not rows:
        return "No guide content found for that query."

    lines = []
    for r in rows:
        d = dict(zip(cols, r))
        lines.append(f"[{d['title']} (p.{d.get('page_start', '?')})]")
        lines.append(d["text"][:700] + ("..." if len(d["text"]) > 700 else ""))
        lines.append("")
    return "\n".join(lines).strip()
