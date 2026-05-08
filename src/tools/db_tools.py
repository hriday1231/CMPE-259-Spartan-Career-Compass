"""sqlite-backed tools for events and staff lookups"""

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

from langchain_core.tools import tool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config import DB_PATH


def _get_conn():
    return sqlite3.connect(str(DB_PATH))


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


@tool
def query_events_tool(
    category: str = "",
    keyword: str = "",
    days_ahead: int = 30,
    limit: int = 20,
) -> str:
    """query upcoming Career Center events filtered by category, keyword, and a forward window in days"""
    conn = _get_conn()
    cur = conn.cursor()
    try:
        now_iso = _iso(datetime.now())
        cutoff_iso = _iso(datetime.now() + timedelta(days=days_ahead))
        conditions = ["start_datetime >= ?", "start_datetime <= ?"]
        params = [now_iso, cutoff_iso]

        if category:
            conditions.append("category LIKE ? COLLATE NOCASE")
            params.append(f"%{category}%")

        if keyword:
            conditions.append("(title LIKE ? COLLATE NOCASE OR COALESCE(description, '') LIKE ? COLLATE NOCASE)")
            params.append(f"%{keyword}%")
            params.append(f"%{keyword}%")

        params.append(limit)
        where = " AND ".join(conditions)

        cur.execute(
            f"""
            SELECT title, start_datetime, end_datetime, location, category, audience, description, source_url
            FROM events
            WHERE {where}
            ORDER BY start_datetime
            LIMIT ?
            """,
            params,
        )
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
    finally:
        cur.close()
        conn.close()

    if not rows:
        return "No upcoming events found for the given filters."

    lines = []
    for r in rows:
        d = dict(zip(cols, r))
        start_dt = d.get("start_datetime")
        if start_dt:
            try:
                dt_str = datetime.fromisoformat(start_dt).strftime("%A, %B %d, %Y at %I:%M %p")
            except (ValueError, TypeError):
                dt_str = start_dt
        else:
            dt_str = "TBD"
        loc_str = d.get("location") or "TBD"
        lines.append(
            f"- **{d['title']}** | Category: {d['category']} | Date: {dt_str} | Location: {loc_str} | source_url: {d.get('source_url', '')}"
        )
        if d.get("description"):
            lines.append(f"  Description: {d['description'][:150]}")
    return "\n".join(lines)


@tool
def query_staff_tool(college: str = "") -> str:
    """look up Career Center staff and counselors by college, empty college lists everyone"""
    conn = _get_conn()
    cur = conn.cursor()
    try:
        if college:
            cur.execute(
                """
                SELECT name, role, college, email, phone, office_location, office_hours, profile_url
                FROM staff WHERE college LIKE ? COLLATE NOCASE ORDER BY name
                """,
                (f"%{college}%",),
            )
        else:
            cur.execute(
                """
                SELECT name, role, college, email, phone, office_location, office_hours, profile_url
                FROM staff ORDER BY college, name
                """
            )
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
    finally:
        cur.close()
        conn.close()

    # no specific match for the requested college -> fall back to listing all
    # counselors and coaches, since they accept students from any college
    if not rows and college:
        conn2 = _get_conn()
        cur2 = conn2.cursor()
        try:
            cur2.execute(
                """
                SELECT name, role, college, email, phone, office_location, office_hours, profile_url
                FROM staff WHERE role LIKE '%counselor%' COLLATE NOCASE OR role LIKE '%coach%' COLLATE NOCASE
                ORDER BY name
                """
            )
            rows = cur2.fetchall()
            cols = [d[0] for d in cur2.description]
        finally:
            cur2.close()
            conn2.close()
        if rows:
            header = f"No counselor specifically assigned to '{college}' was found. Here are all Career Center counselors who can assist students from any college:\n"
            lines = [header]
            for r in rows:
                d = dict(zip(cols, r))
                parts = [f"- **{d['name']}**"]
                if d.get("role"):
                    parts.append(f"Role: {d['role']}")
                if d.get("college"):
                    parts.append(f"College: {d['college']}")
                if d.get("email"):
                    parts.append(f"Email: {d['email']}")
                if d.get("profile_url"):
                    parts.append(f"profile_url: {d['profile_url']}")
                lines.append(" | ".join(parts))
            return "\n".join(lines)
        return f"No staff found matching '{college}'."
    if not rows:
        return "No staff in database."

    lines = []
    for r in rows:
        d = dict(zip(cols, r))
        parts = [f"- **{d['name']}**"]
        if d.get("role"):
            parts.append(f"Role: {d['role']}")
        if d.get("college"):
            parts.append(f"College: {d['college']}")
        if d.get("email"):
            parts.append(f"Email: {d['email']}")
        if d.get("phone"):
            parts.append(f"Phone: {d['phone']}")
        if d.get("profile_url"):
            parts.append(f"profile_url: {d['profile_url']}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)
