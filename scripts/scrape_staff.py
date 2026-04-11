import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2
import requests
from bs4 import BeautifulSoup

from config import DATABASE_URL

STAFF_URLS = [
    "https://careercenter.sjsu.edu/staff/",
    "https://careercenter.sjsu.edu/about-us/our-team/",
]
USER_AGENT = "SpartanCareerCompass/1.0 (SJSU CMPE 259 project; educational)"

COLLEGE_KEYWORDS = {
    "Engineering": ["engineering", "engr", "coe"],
    "Business": ["business", "lucas", "cob"],
    "Science": ["science", "cos"],
    "Social Sciences": ["social science", "coss"],
    "Education": ["education", "connie l. lurie", "lurie"],
    "Humanities and the Arts": ["humanities", "arts", "h&a", "ha"],
    "Health and Human Sciences": ["health", "human sciences"],
    "Professional and Global Education": ["professional", "global education"],
    "Graduate Studies": ["graduate"],
}


def _session():
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


def _extract_email(el) -> str:
    for a in el.find_all("a", href=True):
        if a["href"].startswith("mailto:"):
            return a["href"].replace("mailto:", "").strip()
    text = el.get_text()
    m = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
    if m:
        return m.group(0)
    return ""


def _extract_colleges(text: str) -> str:
    colleges = []
    text_lower = text.lower()
    for college, keywords in COLLEGE_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                colleges.append(college)
                break
    return "; ".join(colleges) if colleges else ""


def _parse_heading_structure(soup: BeautifulSoup) -> list[dict]:
    people = []
    current_section = ""

    for el in soup.find_all(["h2", "h3", "h4"]):
        if el.name == "h2":
            current_section = el.get_text(strip=True)
            continue

        name_tag = el
        name = name_tag.get_text(strip=True)
        if not _is_valid_name(name):
            continue

        role = ""
        email = ""
        college = ""
        phone = ""
        detail_text_parts = []

        sibling = name_tag.find_next_sibling()
        while sibling and sibling.name not in ("h2", "h3", "h4"):
            text = sibling.get_text(strip=True)

            if not email:
                found_email = _extract_email(sibling)
                if found_email:
                    email = found_email

            phone_m = re.search(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", text)
            if phone_m and not phone:
                phone = phone_m.group(0)

            if text and "@" not in text and not phone_m:
                detail_text_parts.append(text)

            sibling = sibling.find_next_sibling()

        detail_text = " ".join(detail_text_parts)

        if detail_text:
            role_parts = []
            college_parts = []
            for part in detail_text_parts:
                col = _extract_colleges(part)
                if col:
                    college_parts.append(col)
                elif not role_parts or len(" ".join(role_parts)) < 100:
                    role_parts.append(part)
            role = " ".join(role_parts)[:200] if role_parts else current_section
            college = "; ".join(college_parts) if college_parts else _extract_colleges(detail_text) or current_section

        if not role:
            role = current_section

        if name and (email or role):
            people.append({
                "name": name,
                "role": role or None,
                "college": college or None,
                "email": email or None,
                "phone": phone or None,
                "office_location": "Career Center",
                "office_hours": "See Career Center website",
                "profile_url": "https://careercenter.sjsu.edu/staff/",
            })

    return people


SKIP_NAMES = {
    "menu", "search", "navigation", "footer", "header",
    "contact", "hours", "location", "career center",
    "meet our team", "skip to", "toggle", "executive director",
    "career counselor", "career coach", "student affairs",
    "main content", "primary", "secondary", "mobile",
    "career counselors", "career coaches", "student assistants",
    "administration", "our team", "staff",
}


def _is_valid_name(name: str) -> bool:
    if not name or len(name) > 80 or len(name) < 3:
        return False
    if any(skip in name.lower() for skip in SKIP_NAMES):
        return False
    words = name.split()
    if len(words) < 2:
        return False
    return True


def _parse_block_structure(soup: BeautifulSoup) -> list[dict]:
    people = []
    for card in soup.find_all(class_=re.compile(r"staff|team|member|person|profile|card", re.I)):
        name = ""
        role = ""
        email = ""
        college = ""

        heading = card.find(["h2", "h3", "h4", "h5", "strong"])
        if heading:
            name = heading.get_text(strip=True)

        if not _is_valid_name(name):
            continue

        email = _extract_email(card)
        full_text = card.get_text(separator="\n", strip=True)
        college = _extract_colleges(full_text)

        lines = [l.strip() for l in full_text.split("\n") if l.strip()]
        role_lines = [l for l in lines if l != name and "@" not in l and not re.match(r"^\(?\d{3}", l)]
        role = " | ".join(role_lines[:2])[:200] if role_lines else ""

        if email or role:
            people.append({
                "name": name,
                "role": role or None,
                "college": college or None,
                "email": email or None,
                "phone": None,
                "office_location": "Career Center",
                "office_hours": "See Career Center website",
                "profile_url": "https://careercenter.sjsu.edu/staff/",
            })

    return people


def scrape_staff(session: requests.Session) -> list[dict]:
    all_people = []

    for url in STAFF_URLS:
        try:
            r = session.get(url, timeout=15)
            if r.status_code == 404:
                continue
            r.raise_for_status()
        except requests.RequestException:
            continue

        soup = BeautifulSoup(r.text, "html.parser")

        people = _parse_heading_structure(soup)
        if people:
            print(f"  Found {len(people)} staff via heading structure from {url}")
            all_people.extend(people)

        block_people = _parse_block_structure(soup)
        if block_people:
            print(f"  Found {len(block_people)} staff via block structure from {url}")
            all_people.extend(block_people)

    seen = set()
    unique = []
    for p in all_people:
        key = p["name"].lower().strip()
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)

    return unique


def load_staff_into_db(staff: list[dict]) -> int:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("DELETE FROM staff")
    for s in staff:
        cur.execute(
            """
            INSERT INTO staff (name, role, college, email, phone, office_location, office_hours, profile_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                s.get("name"),
                s.get("role"),
                s.get("college"),
                s.get("email"),
                s.get("phone"),
                s.get("office_location"),
                s.get("office_hours"),
                s.get("profile_url"),
            ),
        )
    conn.commit()
    n = len(staff)
    cur.close()
    conn.close()
    return n


def main():
    session = _session()
    print("Fetching staff pages...")
    staff = scrape_staff(session)
    print(f"Found {len(staff)} unique staff members.")
    for s in staff[:10]:
        print(f"  {s['name']} | {(s.get('role') or '')[:40]} | {s.get('college') or ''} | {s.get('email') or ''}")
    if not staff:
        print("WARNING: No staff scraped. The page may be JavaScript-rendered.")
        print("You may need to manually add staff data or use a browser-based scraper.")
        return
    n = load_staff_into_db(staff)
    print(f"Loaded {n} staff into database.")


if __name__ == "__main__":
    main()
