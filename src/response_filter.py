"""strip boilerplate greetings and sign-offs from LLM output

belt-and-suspenders on top of the meta system prompt - some RLHF'd models
(notably Llama-2) re-add greetings even when explicitly told not to, so we
peel them off the accumulated response

patterns are precise (not greedy), each peels ONE leading sentence so
stacked openers like "Hi there! As a ..., I'm happy to ..." all come off
without eating substantive content - we also do NOT strip "Here is/are"
because that is usually the real answer ("Here are a few positions:")
"""

from __future__ import annotations

import re
from typing import Iterator

# each pattern peels one leading boilerplate sentence, anchored to start
_GREETING_PATTERNS: list[re.Pattern] = [
    # "Hi there!" / "Hello!" / "Hey!" / "Greetings!"
    re.compile(r"^\s*(?:hi\s+there|hello|hi|hey|greetings)[!,.]?\s+", re.IGNORECASE),
    # "Sure!" / "Of course!" / "Absolutely!" / "Certainly!" / "Great question!"
    re.compile(
        r"^\s*(?:sure|of\s+course|absolutely|certainly|definitely|great\s+question)[!,.]?\s+",
        re.IGNORECASE,
    ),
    # "As a/an/your <role>, " - comma is allowed as terminator
    re.compile(
        r"^\s*as\s+(?:a|an|your)\s+[^.!?\n,]{1,80}[.!?,]\s+",
        re.IGNORECASE,
    ),
    # "I'm happy to help ..." / "I'd be happy to help ..." / "I'm here to help ..."
    re.compile(
        r"^\s*i(?:'m|\s+am|'d|'ll|\s*would|\s*will)"
        r"(?:\s+(?:be|going\s+to\s+be))?"
        r"\s+(?:happy|glad|here|delighted|pleased)"
        r"[^.!?\n]{0,80}[.!?]\s+",
        re.IGNORECASE,
    ),
    # "Based on the retrieved context," / "Based on the current Career Center data,"
    re.compile(
        r"^\s*based\s+on\s+(?:the|our|my|your)\s+"
        r"(?:[a-z]+\s+){0,3}"
        r"(?:retrieved|provided|given|following|above|data|context|information|"
        r"career\s+center)[^.,\n]*[,.]\s+",
        re.IGNORECASE,
    ),
    # "According to the Career Center data," / "According to our records,"
    re.compile(
        r"^\s*according\s+to\s+(?:the|our|my|your)\s+"
        r"(?:[a-z]+\s+){0,3}"
        r"(?:career\s+center|retrieved|provided|data|records|information)"
        r"[^.,\n]*[,.]\s+",
        re.IGNORECASE,
    ),
]

_CLOSING_PATTERNS: list[re.Pattern] = [
    # "Hope this helps" / "I hope this helps for your search"
    re.compile(r"\s*(?:i\s+)?hope\s+this\s+helps[^.!?\n]*[!.]?\s*$", re.IGNORECASE),
    # "Let me know if you need more info"
    re.compile(r"\s*let\s+me\s+know\s+if[^.!?\n]*[!.]?\s*$", re.IGNORECASE),
    # "Feel free to ask if you need anything"
    re.compile(r"\s*feel\s+free\s+to\s+(?:ask|reach)[^.!?\n]*[!.]?\s*$", re.IGNORECASE),
    # "Please don't hesitate to ask / reach out"
    re.compile(
        r"\s*(?:please\s+)?(?:don'?t|do\s+not)\s+hesitate\s+to\s+[^.!?\n]+[!.]?\s*$",
        re.IGNORECASE,
    ),
    # "If you have any more questions, ..."
    re.compile(
        r"\s*if\s+you\s+have\s+any\s+(?:more\s+|other\s+|additional\s+)?questions"
        r"[^.!?\n]*[!.]?\s*$",
        re.IGNORECASE,
    ),
    # "Good luck (with your interview)!" / "Best of luck in your search"
    re.compile(
        r"\s*(?:good\s+luck|best\s+of\s+luck|wishing\s+you\s+(?:luck|the\s+best))"
        r"[^.!?\n]*[!.]?\s*$",
        re.IGNORECASE,
    ),
    # "Happy job hunting / interviewing / networking / searching"
    re.compile(
        r"\s*happy\s+(?:job\s+hunting|interviewing|networking|searching|applying)"
        r"[^.!?\n]*[!.]?\s*$",
        re.IGNORECASE,
    ),
    # "I hope this information is helpful" / "I hope these tips were useful"
    re.compile(
        r"\s*i\s+hope\s+(?:this|the|these)\s+(?:information|tips|response|answer)"
        r"\s+(?:is|are|was|were)\s+(?:helpful|useful)[^.!?\n]*[!.]?\s*$",
        re.IGNORECASE,
    ),
    # "Thank you for your question"
    re.compile(r"\s*thank\s+you\s+for\s+[^.!?\n]+[!.]?\s*$", re.IGNORECASE),
    # standalone "Cheers!" / "Best,"
    re.compile(r"\s*(?:cheers|best|regards|sincerely)[!,.]?\s*$", re.IGNORECASE),
]


def clean_response(text: str) -> str:
    """remove stacked greeting prefixes and closing pleasantries"""
    if not text:
        return text
    cleaned = text
    # peel up to 4 boilerplate sentences from the front
    for _ in range(4):
        matched = False
        for pat in _GREETING_PATTERNS:
            m = pat.match(cleaned)
            if m and m.end() > 0:
                cleaned = cleaned[m.end():]
                matched = True
                break
        if not matched:
            break
    # llama-2 can stack 4+ closing pleasantries, so loop the closers too
    for _ in range(6):
        matched = False
        for pat in _CLOSING_PATTERNS:
            new = pat.sub("", cleaned)
            if new != cleaned:
                cleaned = new
                matched = True
                break
        if not matched:
            break
    cleaned = cleaned.lstrip()
    # if peeling left the first word lowercase, capitalize it
    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned


# worst-case stacked opener is around 150 chars, buffer 220 to be safe
_STREAM_BUFFER_CHARS = 220


def filtered_stream(chunks: Iterator[str]) -> Iterator[str]:
    """strip greetings from a streaming iterator of text chunks

    buffers ~220 chars, cleans, yields cleaned text, then passes later chunks
    through unchanged - greeting-like content arriving after the first 220
    chars is left alone (rare in practice)
    """
    buffer = ""
    flushed = False
    try:
        for chunk in chunks:
            if flushed:
                yield chunk
                continue
            buffer += chunk
            if len(buffer) >= _STREAM_BUFFER_CHARS:
                cleaned = clean_response(buffer)
                if cleaned:
                    yield cleaned
                flushed = True
    finally:
        if not flushed and buffer:
            cleaned = clean_response(buffer)
            if cleaned:
                yield cleaned
