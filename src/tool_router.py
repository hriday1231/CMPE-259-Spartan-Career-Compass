import re
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.tools import query_events_tool, query_staff_tool, search_guides_tool

EVENT_KEYWORDS = (
    "event", "events", "workshop", "workshops", "fair", "fairs", "coming up",
    "happening", "calendar", "schedule", "career fair", "resume workshop",
    "interview prep", "headshot", "headshots", "closet", "career trek",
    "hackathon", "mixer", "networking event", "information session",
    "drop-in", "walk-in", "panel", "appointment", "services",
    "week", "month", "today", "tomorrow",
)
STAFF_KEYWORDS = (
    "counselor", "counselors", "staff", "who is", "contact", "liaison",
    "engineering", "business", "science", "college", "major", "advisor",
    "coach", "appointment",
)
GUIDE_KEYWORDS = (
    "resume", "resumes", "cover letter", "interview", "interviews", "tips",
    "guide", "guides", "resource", "resources", "internship", "internships",
    "job search", "job", "jobs", "linkedin", "graduate school", "grad school",
    "career", "prepare", "prep", "how to", "advice", "checklist", "roadmap",
    "mock interview", "behavioral", "STAR", "networking email",
    "skills", "assessment", "plan", "salary", "negotiate",
    "what should i bring", "services", "access",
)

EVENT_CATEGORY_MAP = [
    (r"\b(career\s*fairs?|job\s*fairs?|internship\s*fairs?|hiring\s*events?|career\s*expos?)\b", "Career Fairs"),
    (r"\bfairs?\b", "Career Fairs"),
    (r"\b(workshops?|salary|negotiate)\b", "Career Education Events"),
    (r"\b(information\s*sessions?|info\s*sessions?|employer)\b", "Employer Connection Events"),
    (r"\b(mixers?|alumni|networking\s*events?|panels?|engagement)\b", "Student Engagement Events"),
    (r"\bcommunity\b", "Community Event"),
]

EVENT_SEARCH_KEYWORDS = [
    (r"\bheadshots?\b", "headshot"),
    (r"\bresume\s*workshops?\b", "resume"),
    (r"\binterview\s*prep\b", "interview"),
    (r"\bresume\s*reviews?\b", "resume"),
    (r"\bcareer\s*treks?\b", "career trek"),
    (r"\bhackathons?\b", "hack"),
    (r"\bdrop[\s-]?in\b", "drop-in"),
    (r"\bSTEM\b", "STEM"),
    (r"\bnetworking\b", "networking"),
    (r"\bclosets?\b", "closet"),
    (r"\bAI\s*tools?\b", "AI"),
    (r"\bjob\s*search\b", "job search"),
    (r"\b(appointment|no\s*appointment|without\s*appointment)\b", "appointment"),
    (r"\bservices?\b", ""),  # empty keyword = no keyword filter, just use category/date
]

COLLEGE_ALIASES = [
    (r"\bengineering\b", "Engineering"),
    (r"\bbusiness\b", "Business"),
    (r"\bscience\b", "Science"),
    (r"\bsocial science(s)?\b", "Social Sciences"),
    (r"\bhumanities\b", "Humanities"),
    (r"\barts?\b", "Arts"),
    (r"\beducation\b", "Education"),
    (r"\bhealth\b", "Health"),
]

TIME_PATTERNS = [
    (r"\bthis\s*week\b", 7),
    (r"\bnext\s*(\d+)\s*days?\b", None),
    (r"\bnext\s*week\b", 14),
    (r"\bthis\s*month\b", 30),
    (r"\bnext\s*month\b", 60),
    (r"\btoday\b", 1),
    (r"\btomorrow\b", 2),
    (r"\bupcoming\b", 30),
    (r"\bnext\s*(\d+)\s*weeks?\b", None),
]

GUIDE_TITLE_MAP = [
    (r"\bresume|cover\s*letter\b", "Resume and Cover Letter Guide"),
    (r"\binterview|behavioral|mock\s*interview|STAR\b", "Interviewing Guide"),
    (r"\bjob\s*(search|hunting)|internship|career\s*fair|what.*bring\b", "Job and Internship Guide"),
    (r"\blinkedin|networking\s*email\b", "Utilizing LinkedIn Guide"),
    (r"\bgrad(uate)?\s*school\b", "Applying to Graduate School Guide"),
    (r"\binternational\s*student\b", "International Students Guide"),
    (r"\bexperience|build\s*experience\b", "Build Experience Guide"),
    (r"\bcareer\s*readiness|roadmap\b", "Career Readiness Roadmap"),
    (r"\bvalues?\s*assessment\b", "Career Values Assessment"),
    (r"\bskills?\s*inventory\b", "Skills Inventory"),
    (r"\bmajor|career\s*exploration\b", "Major and Career Exploration Guide"),
]


def _extract_event_category(text: str) -> str:
    for pattern, category in EVENT_CATEGORY_MAP:
        if re.search(pattern, text, re.I):
            return category
    return ""


def _extract_event_keyword(text: str) -> str:
    for pattern, keyword in EVENT_SEARCH_KEYWORDS:
        if re.search(pattern, text, re.I):
            return keyword
    return ""


def _extract_college(text: str) -> str:
    for pattern, college in COLLEGE_ALIASES:
        if re.search(pattern, text, re.I):
            return college
    return ""


def _extract_days_ahead(text: str) -> int:
    t = text.lower()
    for pattern, days in TIME_PATTERNS:
        m = re.search(pattern, t, re.I)
        if m:
            if days is not None:
                return days
            try:
                n = int(m.group(1))
                if "week" in pattern:
                    return n * 7
                return n
            except (IndexError, ValueError):
                pass
    return 30  # default


def _extract_guide_title(text: str) -> str:
    for pattern, title in GUIDE_TITLE_MAP:
        if re.search(pattern, text, re.I):
            return title
    return ""


def _wants_events(text: str) -> bool:
    return any(k in text.lower() for k in EVENT_KEYWORDS)


def _wants_staff(text: str) -> bool:
    return any(k in text.lower() for k in STAFF_KEYWORDS)


def _wants_guides(text: str) -> bool:
    return any(k in text.lower() for k in GUIDE_KEYWORDS)


def _guide_search_query(user_message: str) -> str:
    stop = {
        "what", "the", "are", "is", "for", "from", "sjsu", "center",
        "best", "provide", "me", "my", "i", "can", "you", "give", "get",
        "some", "any", "about", "into", "next", "this", "week", "month",
        "days", "there", "find", "show", "list", "help", "tell", "please",
        "do", "does", "how", "create", "make", "write", "should", "would",
        "could", "with", "without", "have", "has", "been", "being", "was",
        "were", "will", "be", "to", "of", "in", "on", "at", "by", "up",
        "out", "an", "a", "and", "or", "not", "no", "if", "it", "its",
        "that", "than", "then", "them", "they", "guides", "guide",
    }
    words = re.findall(r"\b\w+\b", user_message.lower())
    kept = [w for w in words if w not in stop and len(w) > 2][:8]
    return " ".join(kept) if kept else user_message[:100]


def run_tools(user_message: str) -> str:
    parts = []
    q = user_message.strip()
    days = _extract_days_ahead(q)

    if _wants_events(q):
        category = _extract_event_category(q)
        keyword = _extract_event_keyword(q)
        out = query_events_tool.invoke({
            "category": category,
            "keyword": keyword,
            "days_ahead": days,
            "limit": 15,
        })
        if "No upcoming events found" in out and category and keyword:
            out_cat = query_events_tool.invoke({
                "category": category, "keyword": "", "days_ahead": days, "limit": 10,
            })
            out_kw = query_events_tool.invoke({
                "category": "", "keyword": keyword, "days_ahead": days, "limit": 10,
            })
            fallback_parts = []
            if "No upcoming events found" not in out_cat:
                fallback_parts.append(f"### Events matching category '{category}':\n{out_cat}")
            if "No upcoming events found" not in out_kw:
                fallback_parts.append(f"### Events matching '{keyword}':\n{out_kw}")
            if fallback_parts:
                out = "\n\n".join(fallback_parts)
            elif "No upcoming events found" in out_cat and "No upcoming events found" in out_kw:
                out_all = query_events_tool.invoke({
                    "category": "", "keyword": "", "days_ahead": days, "limit": 10,
                })
                out = f"No events matching '{keyword}' in '{category}' found. Here are all upcoming events:\n{out_all}"
        parts.append("## Upcoming Career Center events\n" + out)

    if _wants_staff(q):
        college = _extract_college(q)
        out = query_staff_tool.invoke({"college": college})
        parts.append("## Career Center staff / counselors\n" + out)

    if _wants_guides(q):
        search_q = _guide_search_query(q)
        guide_title = _extract_guide_title(q)
        out = search_guides_tool.invoke({
            "query": search_q,
            "guide_title": guide_title,
            "max_chunks": 6,
        })
        parts.append("## Relevant Career Center guide content\n" + out)

    if not parts:
        out_events = query_events_tool.invoke({"category": "", "keyword": "", "days_ahead": 30, "limit": 10})
        out_guides = search_guides_tool.invoke({
            "query": _guide_search_query(q) or "career resources",
            "guide_title": "",
            "max_chunks": 4,
        })
        parts.append("## Upcoming events\n" + out_events)
        parts.append("## Guide content\n" + out_guides)

    return "\n\n".join(parts)


if __name__ == "__main__":
    import sys as _sys
    msg = _sys.argv[1] if len(_sys.argv) > 1 else "What career events are coming up?"
    print(run_tools(msg))
