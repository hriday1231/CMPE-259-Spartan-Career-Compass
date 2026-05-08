"""scrape upcoming events from careercenter.sjsu.edu/events/ and load them into sqlite"""

import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH

# windows console default codepage cannot encode emoji in event titles, so
# force utf-8 stdout when this script runs as __main__
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

EVENTS_LIST_URL = "https://careercenter.sjsu.edu/events/"
MAX_PAGES = 10
USER_AGENT = "SpartanCareerCompass/1.0 (SJSU CMPE 259 project; educational)"

# title-keyword rules used to map an event into one of the 5 site categories
# (Career Fairs, Career Education, Employer Connection, Student Engagement,
# Community), since the event detail pages do not always carry a category tag
CATEGORY_RULES = [
    (r"\bcommunity\s*event\b", "Community Event"),
    (r"\b(skillsbuild|skills\s*build|experiential\s*learning|immersion)\b", "Career Education Events"),
    (r"\bexploring\s*careers\b", "Career Education Events"),
    (r"\b(job\s*(&|and)\s*internship\s*fair|career\s*fair|career\s*expo|job\s*fair|hiring\s*event)\b", "Career Fairs"),
    (r"\b(information\s*session|info\s*session)\b", "Employer Connection Events"),
    (r"\b(career\s*trek|company\s*visit|site\s*visit|prologis|adobe.*experience)\b", "Employer Connection Events"),
    (r"\b(figma|linkedin\s*ambassadors?)\b", "Employer Connection Events"),
    (r"\b(alumnight|alumni|mixer|panel|connections?\s*catalyst|empower|leadership)\b", "Student Engagement Events"),
    (r"\b(hackathon|hack\s*\d|sparthill|adobe\s*club)\b", "Student Engagement Events"),
    (r"\b(networking\s*(event|mixer|for))\b", "Student Engagement Events"),
    (r"\b(student\s*to\s*alumni|community\s*for\s*all\s*careers)\b", "Student Engagement Events"),
    (r"\bieee\b", "Student Engagement Events"),
    (r"\b(workshop|negotiate|salary|confidence)\b", "Career Education Events"),
    (r"\b(resume|cover\s*letter|interview|job\s*search\s*tips|jumpstart)\b", "Career Education Events"),
    (r"\b(headshot|head\s*shot|closet|professional\s*clothing)\b", "Career Education Events"),
    (r"\b(drop[\s-]?in|walk[\s-]?in|no\s*appointment|career\s*help)\b", "Career Education Events"),
    (r"\b(elevate|ai\s*tools|skillsbuild|skills\s*build)\b", "Career Education Events"),
    (r"\b(hidden\s*job\s*market|labor\s*market|get\s*hired)\b", "Career Education Events"),
]


def _infer_category(title: str, description: str = "") -> str:
    combined = f"{title} {description}".strip()
    for pattern, category in CATEGORY_RULES:
        if re.search(pattern, combined, re.I):
            return category
    return "Career Education Events"


def _session():
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def _parse_event_date_location(link_text: str):
    start_dt = end_dt = None
    location = ""

    m = re.search(
        r"(\w+day),?\s+(\w+)\s+(\d{1,2}),?\s+(\d{4})\s+"
        r"(\d{1,2})(?::(\d{2}))?\s*([ap]m)\s*[-–]\s*"
        r"(\d{1,2})(?::(\d{2}))?\s*([ap]m)",
        link_text, re.I,
    )
    if m:
        _, month, day, year, h1, min1, ampm1, h2, min2, ampm2 = m.groups()
        month_num = MONTH_MAP.get(month.lower(), 1)
        h1, h2 = int(h1), int(h2)
        min1, min2 = int(min1 or 0), int(min2 or 0)
        if ampm1.lower() == "pm" and h1 != 12:
            h1 += 12
        if ampm1.lower() == "am" and h1 == 12:
            h1 = 0
        if ampm2.lower() == "pm" and h2 != 12:
            h2 += 12
        if ampm2.lower() == "am" and h2 == 12:
            h2 = 0
        try:
            start_dt = datetime(int(year), month_num, int(day), h1, min1)
            end_dt = datetime(int(year), month_num, int(day), h2, min2)
        except (ValueError, TypeError):
            pass

    loc_m = re.search(
        r"\d{1,2}(?::\d{2})?\s*[ap]m\s*[-–]\s*\d{1,2}(?::\d{2})?\s*[ap]m\s+(.+?)$",
        link_text, re.S | re.I,
    )
    if loc_m:
        location = loc_m.group(1).strip()
        location = re.sub(
            r"^\w{3},?\s+\w{3}\s+\d{1,2}\s+from\s+\d{1,2}(?::\d{2})?\s*[ap]m\s*[-–]\s*\d{1,2}(?::\d{2})?\s*[ap]m\s*",
            "", location, flags=re.I
        ).strip()
        location = re.sub(r"^[-–-]+\s*", "", location)
        location = re.sub(r"\s*https?://.*$", "", location)
        if len(location) > 300:
            location = location[:300]
    return start_dt, end_dt, location


def get_all_event_urls(session: requests.Session) -> list[tuple[str, str]]:
    all_events = []
    seen_urls = set()

    for page_num in range(1, MAX_PAGES + 1):
        if page_num == 1:
            url = EVENTS_LIST_URL
        else:
            url = f"{EVENTS_LIST_URL}page/{page_num}/"

        try:
            r = session.get(url, timeout=15)
            if r.status_code == 404:
                break
            r.raise_for_status()
        except requests.RequestException:
            break

        soup = BeautifulSoup(r.text, "html.parser")
        found_on_page = 0
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if re.match(r".*/events/\d{4}/\d{2}/\d{2}/[^/]+/?$", href):
                full_url = urljoin(EVENTS_LIST_URL, href)
                if full_url not in seen_urls:
                    seen_urls.add(full_url)
                    link_text = a.get_text(separator=" ", strip=True)
                    all_events.append((full_url, link_text))
                    found_on_page += 1

        print(f"  Page {page_num}: found {found_on_page} events")
        if found_on_page == 0:
            break

    return all_events


def scrape_single_event(session: requests.Session, url: str, list_link_text: str = "") -> dict | None:
    try:
        r = session.get(url, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  Failed to fetch {url}: {e}")
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    title_el = soup.find("h1") or soup.find("title")
    title = (title_el.get_text(strip=True) if title_el else "").strip()
    for suffix in [" – Career Center San José State University",
                   " - Career Center San José State University",
                   " – Career Center", " - Career Center"]:
        title = title.replace(suffix, "").strip()
    if not title:
        title = url.rstrip("/").split("/")[-1].replace("-", " ").title()

    start_dt, end_dt, location = (None, None, "")
    if list_link_text:
        start_dt, end_dt, location = _parse_event_date_location(list_link_text)

    if not location:
        for cls_pattern in [r"location", r"venue", r"place", r"address"]:
            loc_el = soup.find(class_=re.compile(cls_pattern, re.I))
            if loc_el:
                location = loc_el.get_text(strip=True)[:300]
                break
        if not location:
            loc_el = soup.find("p", string=re.compile(
                r"Student Union|Clark Hall|Virtual|Engineering|San Jose|Room", re.I
            ))
            if loc_el:
                location = loc_el.get_text(strip=True)[:300]

    description = ""
    desc_el = (
        soup.find(class_=re.compile(r"entry-content|event-body|event-description", re.I))
        or soup.find("article")
        or soup.find("main")
    )
    if desc_el:
        for noise in desc_el.find_all(class_=re.compile(r"share|social|nav|menu|footer|header|sidebar|breadcrumb", re.I)):
            noise.decompose()
        raw = desc_el.get_text(separator="\n", strip=True)
        lines = []
        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                continue
            if any(skip in line.lower() for skip in [
                "share this", "share on", "tweet this", "facebook", "linkedin",
                "skip to content", "meet our team", "toggle navigation",
                "join us", "click here to attend", "spread the word",
                "add to calendar", "google calendar", "outlook/ical",
                "outlook", "ical", "click here", "register here",
                "rsvp", "sign up here",
            ]):
                continue
            lines.append(line)
        description = "\n".join(lines)[:2000]

    category = _infer_category(title, f"{list_link_text} {description}")

    return {
        "title": title or "Event",
        "start_datetime": start_dt,
        "end_datetime": end_dt,
        "location": location[:300] if location else None,
        "category": category,
        "audience": "SJSU students",
        "description": description or None,
        "source_url": url,
    }


def load_events_into_db(events: list[dict]) -> int:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("DELETE FROM events")
    for e in events:
        start_iso = e["start_datetime"].isoformat() if e.get("start_datetime") else None
        end_iso = e["end_datetime"].isoformat() if e.get("end_datetime") else None
        cur.execute(
            """
            INSERT INTO events (title, start_datetime, end_datetime, location, category, audience, description, source_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                e["title"],
                start_iso,
                end_iso,
                e["location"],
                e["category"],
                e.get("audience"),
                e["description"],
                e["source_url"],
            ),
        )
    conn.commit()
    cur.close()
    conn.close()
    return len(events)


def main():
    session = _session()
    print("Fetching event listings (all pages)...")
    urls_and_text = get_all_event_urls(session)
    print(f"Found {len(urls_and_text)} total event pages across all pages.")
    events = []
    for url, link_text in urls_and_text:
        try:
            ev = scrape_single_event(session, url, link_text)
            if ev:
                events.append(ev)
                # encode the print payload defensively to survive any console
                # codepage that cannot represent emoji in event titles
                line = f"  [{ev['category']}] {ev['title'][:60]}"
                print(line.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8", errors="replace"))
        except Exception as ex:
            print("  Skip", url[:60], ex)
    if not events:
        print("No events scraped.")
        sys.exit(1)
    n = load_events_into_db(events)
    print(f"Loaded {n} events into database.")


if __name__ == "__main__":
    main()
