"""adzuna jobs API wrapper with sqlite-backed 6-hour cache"""

import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests
from langchain_core.tools import tool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config import ADZUNA_APP_ID, ADZUNA_APP_KEY, ADZUNA_COUNTRY, DB_PATH

ADZUNA_BASE = "https://api.adzuna.com/v1/api/jobs"
CACHE_TTL_HOURS = 6


def _get_conn():
    return sqlite3.connect(str(DB_PATH))


def _cache_key(keyword: str, location: str, is_remote: bool, min_pay: float, max_pay: float, job_type: str) -> str:
    return f"adzuna:{keyword}|{location}|{is_remote}|{min_pay}|{max_pay}|{job_type}".lower()


def _read_cache(key: str) -> list[dict] | None:
    conn = _get_conn()
    cur = conn.cursor()
    try:
        cutoff_iso = (datetime.utcnow() - timedelta(hours=CACHE_TTL_HOURS)).isoformat(timespec="seconds")
        cur.execute(
            """
            SELECT api_raw FROM jobs_cache
            WHERE job_id = ? AND created_at >= ?
            """,
            (key, cutoff_iso),
        )
        row = cur.fetchone()
        if row and row[0]:
            return json.loads(row[0])
        return None
    finally:
        cur.close()
        conn.close()


def _write_cache(key: str, results: list[dict]) -> None:
    conn = _get_conn()
    cur = conn.cursor()
    try:
        now_iso = datetime.utcnow().isoformat(timespec="seconds")
        cur.execute("DELETE FROM jobs_cache WHERE job_id = ?", (key,))
        cur.execute(
            """
            INSERT INTO jobs_cache (job_id, title, company, location, is_remote,
                                    min_pay, max_pay, currency, job_type,
                                    description, source_api, api_raw, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key,
                "cached_query",
                None,
                None,
                None,
                None,
                None,
                "USD",
                None,
                None,
                "adzuna",
                json.dumps(results),
                now_iso,
            ),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def _call_adzuna(keyword: str, location: str, is_remote: bool,
                 min_pay: float, max_pay: float, limit: int) -> list[dict]:
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        return []
    url = f"{ADZUNA_BASE}/{ADZUNA_COUNTRY}/search/1"
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "results_per_page": max(1, min(limit, 20)),
        "what": keyword or "intern",
        "content-type": "application/json",
    }
    if location:
        params["where"] = location
    if min_pay and min_pay > 0:
        params["salary_min"] = int(min_pay)
    if max_pay and max_pay > 0:
        params["salary_max"] = int(max_pay)

    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        return [{"_error": f"Adzuna request failed: {e}"}]

    data = r.json()
    results = []
    for item in data.get("results", []):
        title = (item.get("title") or "").strip()
        desc = (item.get("description") or "").strip()
        loc = (item.get("location") or {}).get("display_name", "")
        company = (item.get("company") or {}).get("display_name", "")
        # adzuna does not expose a remote flag, fall back to substring sniffing
        remote_flag = bool(
            "remote" in title.lower()
            or "remote" in desc.lower()
            or "remote" in loc.lower()
        )
        if is_remote and not remote_flag:
            continue
        results.append({
            "title": title,
            "company": company,
            "location": loc,
            "is_remote": remote_flag,
            "min_pay": item.get("salary_min"),
            "max_pay": item.get("salary_max"),
            "currency": "USD",
            "contract_type": item.get("contract_type"),
            "contract_time": item.get("contract_time"),
            "description": desc[:600],
            "url": item.get("redirect_url"),
        })
    return results


@tool
def search_jobs_tool(
    keyword: str = "",
    location: str = "",
    is_remote: bool = False,
    min_pay: float = 0,
    max_pay: float = 0,
    job_type: str = "",
    limit: int = 10,
) -> str:
    """search jobs and internships via Adzuna with location, remote, and pay filters"""
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        return "Job search is unavailable: Adzuna credentials are not configured."

    key = _cache_key(keyword, location, is_remote, min_pay, max_pay, job_type)
    cached = _read_cache(key)
    source = "cache"
    if cached is None:
        cached = _call_adzuna(keyword, location, is_remote, min_pay, max_pay, limit)
        if cached and not (len(cached) == 1 and cached[0].get("_error")):
            _write_cache(key, cached)
        source = "live"

    if not cached:
        return f"No jobs found for keyword '{keyword or 'any'}' in '{location or 'any location'}'."
    if len(cached) == 1 and cached[0].get("_error"):
        return cached[0]["_error"]

    lines = [f"(source: {source}, {len(cached)} result(s))"]
    for j in cached[:limit]:
        pay = ""
        if j.get("min_pay") and j.get("max_pay"):
            pay = f" | Pay: ${int(j['min_pay']):,}-${int(j['max_pay']):,} {j.get('currency', 'USD')}"
        elif j.get("min_pay"):
            pay = f" | Pay: from ${int(j['min_pay']):,} {j.get('currency', 'USD')}"
        remote = " | Remote" if j.get("is_remote") else ""
        lines.append(
            f"- **{j['title']}** at {j['company'] or 'Unknown'} | Location: {j['location'] or 'N/A'}"
            f"{remote}{pay} | url: {j.get('url', '')}"
        )
        if j.get("description"):
            lines.append(f"  Description: {j['description'][:280]}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(search_jobs_tool.invoke({
        "keyword": "data science intern",
        "location": "California",
        "is_remote": False,
        "limit": 5,
    }))
