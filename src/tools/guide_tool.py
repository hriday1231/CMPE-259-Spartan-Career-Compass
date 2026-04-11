import psycopg2
from langchain_core.tools import tool

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config import DATABASE_URL


def _get_conn():
    return psycopg2.connect(DATABASE_URL)


@tool
def search_guides_tool(
    query: str,
    guide_title: str = "",
    max_chunks: int = 8,
) -> str:
    conn = _get_conn()
    cur = conn.cursor()
    try:
        words = [w.strip() for w in query.split() if len(w.strip()) > 1]
        if not words:
            return "Please provide a search query (e.g. resume, interview, career fair)."

        or_conds = " OR ".join(["text ILIKE %s" for _ in words])
        params = [f"%{w}%" for w in words]

        score_parts = " + ".join([f"CASE WHEN text ILIKE %s THEN 1 ELSE 0 END" for _ in words])
        score_params = [f"%{w}%" for w in words]

        title_score_parts = " + ".join([f"CASE WHEN title ILIKE %s THEN 2 ELSE 0 END" for _ in words])
        title_score_params = [f"%{w}%" for w in words]

        all_params = score_params + title_score_params + params

        title_filter = ""
        if guide_title:
            title_filter = "AND title ILIKE %s"
            all_params.append(f"%{guide_title}%")

        all_params.append(max_chunks)

        cur.execute(
            f"""
            SELECT title, section, text, page_start, page_end, source_pdf,
                   ({score_parts} + {title_score_parts}) AS relevance
            FROM guides
            WHERE ({or_conds}) {title_filter}
            ORDER BY relevance DESC, title, page_start
            LIMIT %s
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
        lines.append(d["text"][:1500] + ("..." if len(d["text"]) > 1500 else ""))
        lines.append("")
    return "\n".join(lines).strip()
