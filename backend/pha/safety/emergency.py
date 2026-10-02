"""Emergency and crisis detection.

Deliberately simple, transparent rules tuned for recall: a false positive only shows an
urgent-care message, a false negative could delay care. Patterns describe the person's
*current situation* (symptoms happening now), so educational questions such as
"what are the signs of a stroke?" are still answered normally.
"""

import re
from dataclasses import dataclass

_I = re.IGNORECASE

PATTERNS: dict[str, list[str]] = {
    "self_harm": [
        r"\b(kill|hurt|harm|cut)(ing)?\s+my\s*self\b",
        r"\b(end|take)(ing)?\s+my\s+(own\s+)?life\b",
        r"\bsuicid",
        r"\bwant(s|ed)?\s+to\s+die\b",
        r"\bself[- ]?harm",
        r"\b(don'?t|do not)\s+want\s+to\s+(live|be\s+alive|exist)\b",
        r"\bbetter\s+off\s+dead\b",
        r"\bno\s+reason\s+to\s+live\b",
    ],
    "cardiac": [
        r"\bchest\s+(pain|pressure|tightness|squeezing|discomfort|hurts?)\b",
        r"\b(pain|pressure|tightness)\s+in\s+(my|his|her|the)\s+chest\b",
        r"\b(am|i'?m|is|are|be|been)\s+having\s+a\s+heart\s+attack\b",
    ],
    "breathing": [
        r"\b(can'?t|cannot|can\s+not|unable\s+to|hard\s+to|struggling\s+to)\s+breath",
        r"\b(trouble|difficulty)\s+breathing\b",
        r"\bshort(ness)?\s+of\s+breath\b",
        r"\bgasping\s+for\s+(air|breath)\b",
        r"\b(is|am|i'?m)\s+choking\b",
        r"\blips?\s+(are\s+|is\s+)?(turning\s+)?blue\b",
    ],
    "stroke": [
        r"\b(face|mouth|smile)\s+(is\s+)?droop",
        r"\bslurr(ed|ing)\s+(speech|words|my\s+words)\b",
        r"\b(am|i'?m|is|be)\s+having\s+a\s+stroke\b",
        r"\bsudden(ly)?\s+(numb|weak|can'?t\s+(see|speak|talk|move))",
        r"\bcan'?t\s+move\s+(my\s+)?(arm|leg|one\s+side)",
        r"\bworst\s+headache\s+of\s+my\s+life\b",
    ],
    "bleeding": [
        r"\b(heavy|severe|uncontrolled|profuse)\s+bleeding\b",
        r"\bbleeding\b.{0,30}\b(won'?t|will\s+not|doesn'?t|isn'?t)\s+stop",
        r"\b(coughing|vomiting|throwing)\s+(up\s+)?blood\b",
        r"\bblood\s+(is\s+)?(spurting|pouring|gushing)\b",
    ],
    "anaphylaxis": [
        r"\banaphyla",
        r"\b(throat|tongue|lips?|face)\s+(is\s+|are\s+)?(swelling|swollen|closing)",
    ],
    "overdose": [
        r"\boverdos",
        r"\b(took|swallowed|ate|drank|taken)\b.{0,40}\b(too\s+many|too\s+much|whole\s+bottle|entire\s+bottle|bottle\s+of)\b",
        r"\bpoisoned\b",
        r"\bpoisoning\b(?!\s+ivy)",
        r"\b(drank|swallowed)\s+(bleach|antifreeze|drain\s+cleaner)\b",
    ],
    "seizure": [
        r"\b(am|i'?m|is|are|was|be)\s+having\s+a\s+seizure\b",
        r"\b(is|are|keeps)\s+seizing\b",
        r"\bconvuls",
    ],
    "unconscious": [
        r"\b(passed|passing)\s+out\b",
        r"\b(is|was|went)\s+unconscious\b",
        r"\bunresponsive\b",
        r"\b(won'?t|will\s+not|isn'?t|is\s+not)\s+wak(e|ing)\s+up\b",
        r"\bcollapsed\b",
    ],
}

COMPILED = {cat: [re.compile(p, _I) for p in pats] for cat, pats in PATTERNS.items()}

# Category order matters only for which category is reported when several match.
PRIORITY = [
    "self_harm", "cardiac", "breathing", "stroke", "anaphylaxis", "bleeding",
    "overdose", "unconscious", "seizure",
]  # fmt: skip

NEGATIONS = {
    "no", "not", "never", "without", "denies", "denied", "deny", "don't", "dont", "didn't",
    "didnt", "doesn't", "doesnt", "haven't", "havent", "hasn't", "hasnt", "isn't", "wasn't",
    "free", "negative",
}  # fmt: skip
CLAUSE_BREAK = re.compile(r"[.,;:!?]|\b(but|and|however|though|although|yet)\b", _I)
NEGATION_WINDOW = 4  # words
NEGATABLE = set(PRIORITY) - {"self_harm"}  # never discount a possible crisis on negation


@dataclass(frozen=True)
class EmergencyMatch:
    category: str
    matched_text: str


def _negated(text: str, start: int) -> bool:
    before = text[:start]
    breaks = list(CLAUSE_BREAK.finditer(before))
    clause = before[breaks[-1].end() :] if breaks else before
    words = re.findall(r"[a-z']+", clause.lower())[-NEGATION_WINDOW:]
    return any(w in NEGATIONS for w in words)


def detect_emergency(message: str) -> EmergencyMatch | None:
    for category in PRIORITY:
        for pattern in COMPILED[category]:
            for m in pattern.finditer(message):
                if category in NEGATABLE and _negated(message, m.start()):
                    continue
                return EmergencyMatch(category, m.group(0))
    return None
