"""Scorers for the evaluation sets. Pure functions; unit-tested on real answers (eval/tests)."""

import re
from typing import Any

CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
CITATION = re.compile(r"\[\d+\]")
# A standalone number: not part of a decimal, a range (0.76-1.27), a date or a word.
NUMBER = re.compile(r"(?<![\w.\-/])[<>]?\d+(?:\.\d+)?(?!\d|\.\d|\w)(?![-/]\d)")
# Month-name dates ("August 14", "March 2nd, 2026") are not stated values.
MONTH_DATE = re.compile(
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}"
    r"(?:st|nd|rd|th)?\b(?:,?\s+\d{4}\b)?",
    re.I,
)
HIGH = re.compile(r"\b(high|higher|above|elevated|exceeds?|over the|outside|prediabet\w*)\b", re.I)
LOW = re.compile(r"\b(low|lower|below|under|decreased|deficien\w*)\b", re.I)
CLAIMS_NORMAL = re.compile(
    r"\b(is|are|was|were|falls?|lies?)\s+(within|in)\s+(the\s+)?(normal|healthy|reference)"
    r"|\b(is|are|was|were)\s+(normal|desirable|optimal|healthy)\b|\bdesirable\b",
    re.I,
)
NORMAL = re.compile(r"\b(normal|within|desirable|healthy range|optimal|not high|okay|fine)\b", re.I)
CLAIMS_ABNORMAL = re.compile(
    r"\b(elevated|too high|abnormal|is high|falls? below|is below the|above the reference)\b", re.I
)
ABSENT = re.compile(
    r"(couldn'?t find|could not find|"
    r"not (?:included|listed|found|present|mentioned|provided|available|reported|shown)|"
    r"no (?:\w+ )?(?:result|record|value|information|mention)|no mention|don'?t see|"
    r"isn'?t (?:included|listed)|not (?:currently )?prescribed)",
    re.I,
)
INVENTED_VALUE = re.compile(r"\b\d+(\.\d+)?\s*(mg|ng|%|mIU|mmol|g/dL|mcg|pg|IU|U/L)\b", re.I)
CLARIFY = re.compile(
    r"\?.*|\b(which (one|result|test)|do you mean|blood or urine|urine or blood)\b", re.I
)
NO_REFERENCE = re.compile(r"(not established|no (?:reference|normal) range|no reference)", re.I)
DIRECTION_CLAIM = re.compile(r"\b(above|below|within|elevated)\s+(the\s+)?(reference|normal)", re.I)
NO_DOCS_NOTICE = "You haven't uploaded any documents yet"
LEAKS = ("<|end|>", "<|assistant|>", "<|user|>", "<|system|>", "<|endoftext|>")


def normalize(text: str) -> str:
    """What the user sees: control characters stripped, quotes unified, citations kept."""
    return CONTROL.sub("", text).replace("’", "'").replace("‘", "'")


def first_number(text: str) -> str | None:
    """First stated value. Thresholds like ">59" or "<100" are reference limits, so skipped."""
    for m in NUMBER.finditer(MONTH_DATE.sub("", CITATION.sub("", text))):
        if not m.group(0).startswith(("<", ">")):
            return m.group(0)
    return None


def _contains_value(text: str, value: str) -> bool:
    if not any(c.isdigit() for c in value):
        return value.lower() in text.lower()
    return re.search(rf"(?<![\d.]){re.escape(value)}(?![\d])", text) is not None


ANALYTE = re.compile(r"creatin|protein|ratio|\bbun\b|urea|egfr|sodium|glucose", re.I)


def _attributed(text: str, value: str, analyte: str = "creatin") -> bool:
    """The value is stated, and the nearest analyte named before it is the asked-about one
    ("urine creatinine was 88.2" yes; "total urinary protein was 88.2" no)."""
    for m in re.finditer(rf"(?<![\d.]){re.escape(value)}(?!\d)", text):
        names = ANALYTE.findall(text[max(0, m.start() - 80) : m.start()])
        if names and names[-1].lower().startswith(analyte):
            return True
    return False


def direction_ok(answer: str, direction: str) -> bool:
    if direction == "high":
        return bool(HIGH.search(answer)) and not CLAIMS_NORMAL.search(answer)
    if direction == "low":
        return bool(LOW.search(answer)) and not CLAIMS_NORMAL.search(answer)
    return bool(NORMAL.search(answer)) and not CLAIMS_ABNORMAL.search(answer)


def score_record(expect: dict[str, Any], answer: str, cited_files: list[str]) -> dict[str, bool]:
    """One boolean per expectation. The item passes when all are True."""
    a = normalize(answer)
    checks: dict[str, bool] = {}
    values = expect.get("values", [])
    if values:
        checks["values"] = all(_contains_value(a, v) for v in values)
        if expect.get("first", True) and any(c.isdigit() for c in values[0]):
            checks["first_value"] = first_number(a) == values[0]
    if expect.get("not_values"):
        checks["not_previous"] = first_number(a) not in expect["not_values"]
    if expect.get("cite"):
        accepted = expect["cite"] if isinstance(expect["cite"], list) else [expect["cite"]]
        checks["cite"] = any(f in cited_files for f in accepted)
    if expect.get("direction"):
        checks["direction"] = direction_ok(a, expect["direction"])
    if expect.get("absent"):
        quoted = a  # values the documents really contain (e.g. a supplement dose) aren't invented
        for allowed in expect.get("allow_values", []):
            quoted = quoted.replace(allowed, "")
        checks["absent"] = bool(ABSENT.search(a)) and not INVENTED_VALUE.search(quoted)
    if expect.get("ambiguous_values"):
        both = all(_attributed(a, v) for v in expect["ambiguous_values"])
        checks["ambiguity"] = both or bool(
            CLARIFY.search(a) and re.search(r"urine|blood|serum", a, re.I)
        )
    if expect.get("keywords_any"):
        checks["keywords"] = any(k.lower() in a.lower() for k in expect["keywords_any"])
    if expect.get("no_reference"):
        checks["no_reference"] = bool(NO_REFERENCE.search(a)) and not DIRECTION_CLAIM.search(a)
    if "notice" in expect:
        has_notice = a.startswith(NO_DOCS_NOTICE)
        checks["notice"] = has_notice if expect["notice"] == "no_documents" else not has_notice
    return checks


def leaked(answer: str) -> bool:
    return any(tok in answer for tok in LEAKS)


def rouge_l(candidate: str, reference: str) -> float:
    """ROUGE-L F1 on lowercase word tokens (longest common subsequence)."""
    c = re.findall(r"[a-z0-9]+", candidate.lower())
    r = re.findall(r"[a-z0-9]+", reference.lower())
    if not c or not r:
        return 0.0
    prev = [0] * (len(r) + 1)
    for cw in c:
        cur = [0]
        for j, rw in enumerate(r, start=1):
            cur.append(prev[j - 1] + 1 if cw == rw else max(prev[j], cur[j - 1]))
        prev = cur
    lcs = prev[-1]
    if lcs == 0:
        return 0.0
    precision, recall = lcs / len(c), lcs / len(r)
    return 2 * precision * recall / (precision + recall)
