"""regex-based intent and parameter extraction for every tool

I picked a router-first design over an LLM tool-caller because the use case
is narrow (5 tools), the queries are short, and a 10ms regex pass is way
cheaper than asking the model to pick a tool every turn - it also makes
tools_used deterministic, so the UI can show the dispatch caption before
any LLM tokens stream
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.tools import (
    query_events_tool,
    query_staff_tool,
    search_guides_tool,
    search_jobs_tool,
    web_search_tool,
)

EVENT_KEYWORDS = (
    "event", "events", "workshop", "workshops", "fair", "fairs", "coming up",
    "happening", "calendar", "schedule", "career fair", "resume workshop",
    "interview prep", "headshot", "headshots", "closet", "career trek",
    "hackathon", "mixer", "networking event", "information session",
    "drop-in", "walk-in", "panel", "appointment", "services",
    "week", "month", "today", "tomorrow",
)
STAFF_KEYWORDS = (
    "counselor", "counselors", "staff", "liaison",
    "advisor", "coach", "appointment",
)
# combined with a college name these phrases imply "staff for X college"
STAFF_COLLEGE_TRIGGERS = re.compile(
    r"\b(counselor|advisor|coach|staff|liaison|contact|who\s+is)\b",
    re.I,
)
GUIDE_KEYWORDS = (
    "resume", "resumes", "cover letter", "interview", "interviews", "tips",
    "guide", "guides", "resource", "resources",
    "linkedin", "graduate school", "grad school",
    "prepare", "prep", "how to", "advice", "checklist", "roadmap",
    "mock interview", "behavioral", "STAR", "networking email",
    "skills", "assessment", "plan", "negotiate",
    "what should i bring", "services", "access",
)

JOB_KEYWORDS = (
    "find jobs", "find a job", "find internship", "find internships",
    "job listing", "job listings", "job opening", "job openings",
    "entry-level", "entry level", "apply", "hiring", "hire",
    "remote job", "remote internship", "remote role", "remote roles",
    "salary", "pay", "stipend", "paying", "per hour", "/hr",
    "full time", "full-time", "part time", "part-time",
    "software role", "software engineer", "data scientist",
    "data science intern", "product manager", "recruiter",
    "who is hiring", "roles in", "positions in",
)

WEB_SEARCH_KEYWORDS = (
    "company", "companies", "employer", "employers", "recent news",
    "background on", "about the company", "company news", "about company",
    "profile of", "overview of", "tell me about",
    "latest news", "recent", "news about",
    "lucrative", "market trends", "industry",
)

# explicit "go to the web" intent - covers "search for X", "web search X",
# "google X", "look up X online", etc. these are unambiguous web triggers
# even when the rest of the query also matches guide / job keywords
EXPLICIT_WEB_TRIGGERS = (
    "search for", "search the web", "web search", "search online",
    "look up online", "look it up", "find online", "google for",
    "google about", "search up", "look online",
)

# any of these tokens in the query is a strong signal that the user wants
# information about an external company, not generic SJSU career advice -
# whole-word matched (case-insensitive) so e.g. "google" inside another
# word does not trip it
KNOWN_COMPANIES = (
    # tech giants
    "adobe", "google", "microsoft", "apple", "amazon", "meta", "facebook",
    "netflix", "tesla", "nvidia", "intel", "amd", "ibm", "salesforce",
    "oracle", "openai", "anthropic", "uber", "lyft", "airbnb", "twitter",
    "linkedin", "github", "spotify", "tiktok", "bytedance", "x corp",
    # SF / Bay Area / SV
    "stripe", "square", "block", "snap", "snapchat", "pinterest", "reddit",
    "yelp", "ebay", "paypal", "venmo", "zoom", "dropbox", "figma", "notion",
    "twilio", "shopify", "atlassian", "datadog", "doordash", "instacart",
    "robinhood", "coinbase", "palantir", "snowflake", "databricks",
    "huggingface", "deepmind", "perplexity", "scale ai", "mistral",
    # enterprise / hardware
    "cisco", "vmware", "qualcomm", "broadcom", "splunk", "slack", "discord",
    "verkada", "fortinet", "sandisk", "western digital", "applied materials",
    "lam research", "micron", "marvell", "arm", "synopsys", "cadence",
    # finance / consulting
    "goldman sachs", "morgan stanley", "jp morgan", "jpmorgan",
    "bank of america", "wells fargo", "citi", "blackrock", "bridgewater",
    "two sigma", "jane street", "citadel", "deloitte", "pwc", "kpmg",
    "ernst & young", "mckinsey", "bcg", "bain",
    # other large employers SJSU students target
    "boeing", "lockheed", "raytheon", "northrop", "general motors", "ford",
    "samsung", "sony", "panasonic", "siemens", "tesla motors",
)

# when the question is clearly about an external entity, suppress the guides
# DB - it only contains generic SJSU career advice and never has Adobe /
# OpenAI / etc. facts, so firing it tempts the LLM to misattribute web facts
# to unrelated guide pages (e.g. "Adobe is known for X. Source: Interviewing
# Guide p.6")
COMPANY_LOOKUP_PATTERNS = [
    re.compile(r"\btell\s+me\s+about\b", re.I),
    re.compile(r"\babout\s+(?:the\s+)?company\b", re.I),
    re.compile(r"\bcompany\s+(?:news|overview|profile|background)\b", re.I),
    re.compile(r"\b(?:news|info|information)\s+(?:about|on)\b", re.I),
    re.compile(r"\b(?:most\s+)?(?:lucrative|top|leading|biggest)\s+companies\b", re.I),
    re.compile(r"\bcompanies\s+in\s+the\b", re.I),
    re.compile(r"\bmarket\s+trends\b", re.I),
]


def _is_company_lookup(text: str) -> bool:
    return any(p.search(text) for p in COMPANY_LOOKUP_PATTERNS)


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
    (r"\bservices?\b", ""),  # empty keyword keeps category-only filter
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
    return 30


def _extract_guide_title(text: str) -> str:
    for pattern, title in GUIDE_TITLE_MAP:
        if re.search(pattern, text, re.I):
            return title
    return ""


def _wants_events(text: str) -> bool:
    return any(k in text.lower() for k in EVENT_KEYWORDS)


def _wants_staff(text: str) -> bool:
    t = text.lower()
    if any(k in t for k in STAFF_KEYWORDS):
        return True
    # "Who is the counselor for engineering students?" needs both a college
    # AND a staff-trigger word - bare "science" in a job query must NOT
    # fire staff lookup
    if _extract_college(text) and STAFF_COLLEGE_TRIGGERS.search(text):
        return True
    return False


def _wants_guides(text: str) -> bool:
    if _is_company_lookup(text):
        return False
    return any(k in text.lower() for k in GUIDE_KEYWORDS)


def _wants_jobs(text: str) -> bool:
    t = text.lower()
    if any(k in t for k in JOB_KEYWORDS):
        return True
    # bare "internship" / "job" still triggers jobs, but only when the query
    # is not clearly a guide summary or an event question
    job_single = any(w in t for w in ["internship", "internships", "jobs", "job"])
    guide_single = any(w in t for w in [
        "guide", "summarize", "checklist", "roadmap", "tips", "advice",
        "prepare", "prep", "what should i bring",
    ])
    event_single = any(w in t for w in ["event", "workshop", "fair", "calendar"])
    return job_single and not (guide_single or event_single)


_KNOWN_COMPANY_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(c) for c in KNOWN_COMPANIES) + r")\b",
    re.I,
)


def _wants_web(text: str) -> bool:
    t = text.lower()
    if any(k in t for k in WEB_SEARCH_KEYWORDS):
        return True
    if any(k in t for k in EXPLICIT_WEB_TRIGGERS):
        return True
    if _KNOWN_COMPANY_RE.search(text):
        return True
    return False


def _extract_location(text: str) -> str:
    t = text.lower()
    state_map = {
        r"\bcalifornia\b|\bca\b": "California",
        r"\bnew york\b|\bny\b": "New York",
        r"\btexas\b|\btx\b": "Texas",
        r"\bwashington\b|\bwa\b": "Washington",
        r"\bbay area\b|\bsan francisco\b|\bsf\b": "San Francisco, CA",
        r"\bsan jose\b|\bsjsu\b|\bsouth bay\b": "San Jose, CA",
        r"\bsilicon valley\b": "Santa Clara, CA",
        r"\bseattle\b": "Seattle, WA",
        r"\bremote\b": "",
    }
    for pattern, loc in state_map.items():
        if re.search(pattern, t, re.I):
            return loc
    m = re.search(r"\bin\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)", text)
    if m:
        return m.group(1)
    return ""


def _extract_is_remote(text: str) -> bool:
    return bool(re.search(r"\bremote\b|\bwork[-\s]from[-\s]home\b|\bwfh\b", text, re.I))


def _extract_min_pay(text: str) -> float:
    m = re.search(r"\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(k|/hr|/hour|per hour|an hour)?", text, re.I)
    if not m:
        m = re.search(r"(\d+)\s*(?:/hr|/hour|per hour|an hour|dollars? an hour)", text, re.I)
        if m:
            hourly = float(m.group(1))
            return hourly * 40 * 52
        return 0
    amount = float(m.group(1).replace(",", ""))
    unit = (m.group(2) or "").lower()
    if unit == "k":
        amount *= 1000
    elif unit in ("/hr", "/hour", "per hour", "an hour"):
        amount *= 40 * 52
    return amount


def _extract_job_keyword(text: str) -> str:
    t = text.lower()
    role_patterns = [
        (r"\bdata\s*scien(ce|tist)\s*(intern(ship)?)?\b", "data science"),
        (r"\bmachine\s*learning\b", "machine learning"),
        (r"\bsoftware\s*(engineer|engineering|developer|role|roles|position|positions)\b", "software engineer"),
        (r"\bproduct\s*manager(ment)?\b", "product manager"),
        (r"\bui\s*/\s*ux\b|\buser\s*experience\b", "ux design"),
        (r"\bcyber\s*security\b|\bsecurity\s*engineer\b", "cybersecurity"),
        (r"\brobotics?\b", "robotics"),
        (r"\bbiotech\b|\bbiomedical\b", "biotech"),
        (r"\bfinance\b|\baccounting\b", "finance"),
        (r"\bmarketing\b", "marketing"),
    ]
    for pattern, kw in role_patterns:
        if re.search(pattern, t):
            return kw
    if "internship" in t or "intern" in t:
        return "intern"
    return ""


def _extract_web_query(text: str) -> str:
    # strip Career-Center-scoped words so Brave is not forced to search for them
    cleaned = re.sub(
        r"\b(sjsu|career\s*center|spartan|counselor|counselors|workshop|workshops)\b",
        "", text, flags=re.I,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or text


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


def run_tools_with_meta(user_message: str) -> tuple[str, list[str]]:
    """run tool dispatch and return (combined_context, tools_used)

    tools_used is a human-readable list in dispatch order, used by the UI to
    show the "Tools used: ..." caption before any LLM tokens stream
    """
    parts = []
    tools_used: list[str] = []
    q = user_message.strip()
    days = _extract_days_ahead(q)

    if _wants_events(q):
        category = _extract_event_category(q)
        keyword = _extract_event_keyword(q)
        out = query_events_tool.invoke({
            "category": category,
            "keyword": keyword,
            "days_ahead": days,
            "limit": 10,
        })
        # if a category+keyword combination returns nothing, retry each filter
        # on its own so the LLM gets something to reason from instead of a
        # bald "no results" line
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
        tools_used.append("events DB")

    if _wants_staff(q):
        college = _extract_college(q)
        out = query_staff_tool.invoke({"college": college})
        parts.append("## Career Center staff / counselors\n" + out)
        tools_used.append("staff DB")

    if _wants_guides(q):
        search_q = _guide_search_query(q)
        guide_title = _extract_guide_title(q)
        out = search_guides_tool.invoke({
            "query": search_q,
            "guide_title": guide_title,
            "max_chunks": 4,
        })
        parts.append("## Relevant Career Center guide content\n" + out)
        tools_used.append("guides DB")

    if _wants_jobs(q):
        kw = _extract_job_keyword(q)
        loc = _extract_location(q)
        remote = _extract_is_remote(q)
        min_pay = _extract_min_pay(q)
        out = search_jobs_tool.invoke({
            "keyword": kw,
            "location": loc,
            "is_remote": remote,
            "min_pay": min_pay,
            "limit": 10,
        })
        parts.append("## Job listings (Adzuna)\n" + out)
        tools_used.append("Adzuna jobs")

    if _wants_web(q):
        web_q = _extract_web_query(q)
        out = web_search_tool.invoke({"query": web_q, "count": 5})
        if out.startswith("__WEB_SEARCH_UNAVAILABLE__"):
            parts.append("## Web search results\n" + out +
                         "\n(No live web data is available for this question.)")
            tools_used.append("Brave web search (unavailable)")
        else:
            parts.append("## Web search results\n" + out)
            tools_used.append("Brave web search")

    # nothing matched - fall back to events + guides so the LLM can still say
    # something useful (and the UI shows the fallback explicitly)
    if not parts:
        out_events = query_events_tool.invoke({"category": "", "keyword": "", "days_ahead": 30, "limit": 10})
        out_guides = search_guides_tool.invoke({
            "query": _guide_search_query(q) or "career resources",
            "guide_title": "",
            "max_chunks": 3,
        })
        parts.append("## Upcoming events\n" + out_events)
        parts.append("## Guide content\n" + out_guides)
        tools_used.extend(["events DB (fallback)", "guides DB (fallback)"])

    return "\n\n".join(parts), tools_used


def run_tools(user_message: str) -> str:
    """back-compat wrapper that returns just the combined context"""
    context, _ = run_tools_with_meta(user_message)
    return context


if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) > 1 else "What career events are coming up?"
    print(run_tools(msg))
