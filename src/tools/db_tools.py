import psycopg2
from langchain_core.tools import tool

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config import DATABASE_URL


def _get_conn():
    return psycopg2.connect(DATABASE_URL)


@tool
def query_events_tool(
    category: str = "",
    keyword: str = "",
    days_ahead: int = 30,
    limit: int = 20,
) -> str:
    """Query upcoming Career Center events. Use when the user asks about events, workshops, career fairs, or what's happening.
    category: optional filter e.g. 'Career Fairs', 'Career Education Events', 'Employer Connection Events'. Leave empty for all.
    keyword: optional keyword to search in event title and description (e.g. 'headshot', 'resume', 'STEM', 'interview').
    days_ahead: how many days from now to look (default 30).
    limit: max number of events to return (default 20).
    """
    conn = _get_conn()
    cur = conn.cursor()
    try:
        conditions = ["start_datetime >= NOW()", "start_datetime <= NOW() + INTERVAL '1 day' * %s"]
        params = [days_ahead]

        if category:
            conditions.append("category ILIKE %s")
            params.append(f"%{category}%")

        if keyword:
            conditions.append("(title ILIKE %s OR COALESCE(description, '') ILIKE %s)")
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
            LIMIT %s
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
        dt_str = d['start_datetime'].strftime('%A, %B %d, %Y at %I:%M %p') if d.get('start_datetime') else 'TBD'
        loc_str = d.get('location') or 'TBD'
        lines.append(
            f"- **{d['title']}** | Category: {d['category']} | Date: {dt_str} | Location: {loc_str} | source_url: {d.get('source_url', '')}"
        )
        if d.get("description"):
            lines.append(f"  Description: {d['description'][:300]}")
    return "\n".join(lines)


@tool
def query_staff_tool(college: str = "") -> str:
    conn = _get_conn()
    cur = conn.cursor()
    try:
        if college:
            cur.execute(
                """
                SELECT name, role, college, email, phone, office_location, office_hours, profile_url
                FROM staff WHERE college ILIKE %s ORDER BY name
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

    if not rows and college:
        cur2 = conn2 = None
        try:
            conn2 = _get_conn()
            cur2 = conn2.cursor()
            cur2.execute(
                """
                SELECT name, role, college, email, phone, office_location, office_hours, profile_url
                FROM staff WHERE role ILIKE '%counselor%' OR role ILIKE '%coach%'
                ORDER BY name
                """
            )
            rows = cur2.fetchall()
            cols = [d[0] for d in cur2.description]
        finally:
            if cur2:
                cur2.close()
            if conn2:
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
