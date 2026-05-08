"""brave web search wrapper with client-side rate-limit throttle and 429 retry"""

import re
import sys
import time
from pathlib import Path

import requests
from langchain_core.tools import tool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config import BRAVE_API_KEY

BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

# Brave free tier caps at 1 query per second, hitting it harder returns 429
_last_call_ts: float = 0.0
_MIN_INTERVAL_S = 1.05

# sentinel the agent prompts look for to detect "no live web data" - keep
# short and distinctive so it survives any incidental copy-paste
UNAVAILABLE_PREFIX = "__WEB_SEARCH_UNAVAILABLE__:"


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "")


@tool
def web_search_tool(query: str, count: int = 5) -> str:
    """live web search via Brave for employer summaries, recent news, and company background"""
    global _last_call_ts

    if not BRAVE_API_KEY:
        return f"{UNAVAILABLE_PREFIX} BRAVE_API_KEY is not configured."

    count = max(1, min(count, 10))
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": BRAVE_API_KEY,
    }
    params = {
        "q": query,
        "count": count,
        "safesearch": "moderate",
    }

    elapsed = time.time() - _last_call_ts
    if elapsed < _MIN_INTERVAL_S:
        time.sleep(_MIN_INTERVAL_S - elapsed)

    last_error = None
    for attempt in range(3):
        try:
            r = requests.get(BRAVE_ENDPOINT, headers=headers, params=params, timeout=15)
            _last_call_ts = time.time()
            if r.status_code == 429:
                time.sleep(1.5 * (attempt + 1))
                last_error = "rate_limited (HTTP 429)"
                continue
            r.raise_for_status()
            break
        except requests.RequestException as e:
            last_error = str(e)
            time.sleep(0.5 * (attempt + 1))
    else:
        return f"{UNAVAILABLE_PREFIX} Brave returned errors after retries ({last_error})."

    try:
        data = r.json()
    except ValueError:
        return f"{UNAVAILABLE_PREFIX} Brave returned non-JSON response."

    results = (data.get("web") or {}).get("results") or []
    if not results:
        return f"{UNAVAILABLE_PREFIX} No Brave results for '{query}'."

    lines = [f"(Brave web search, {len(results)} result(s) for '{query}')"]
    for res in results[:count]:
        title = _strip_html(res.get("title") or "").strip()
        url = (res.get("url") or "").strip()
        snippet = _strip_html(res.get("description") or "").strip()
        snippet = snippet.replace("\n", " ")[:300]
        lines.append(f"- **{title}** - {url}")
        if snippet:
            lines.append(f"  {snippet}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(web_search_tool.invoke({"query": "Adobe company overview 2026", "count": 3}))
