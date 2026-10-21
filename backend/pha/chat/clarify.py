"""Ask the user to clarify a short message that contains no word we know.

"ok cs" or "hash" score just above the retrieval floor against any document, so the fine-tuned
models receive unrelated excerpts and answer about one of them; for "ok cs" v3 claimed there
were no cholesterol results (2026-10-07). A message is unclear when it has at most 4 words and
none of its words is known from MedQuAD (words.txt), the retrieved excerpts or common
abbreviations. A long unknown word with no close spelling (a brand name such as "Ozempic") is
left to the model rather than questioned.
"""

import difflib
import re
from collections.abc import Iterable
from functools import cache
from pathlib import Path

from pha.rag.keyword import STOPWORDS

WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
MAX_WORDS = 4
SUGGEST_MIN_LETTERS = 5  # shorter words have too many near neighbours ("hash": wash, rash)
SUGGEST_MIN_COUNT = 20  # suggest only words that are common in MedQuAD
FILLER = STOPWORDS | {
    "ok", "okay", "so", "but", "hmm", "um", "uh", "pls", "please", "the", "a", "what", "about",
    "and", "also", "just", "now", "then", "well", "yes", "no", "yeah", "hey", "oh", "same", "as",
}  # fmt: skip
ABBREVIATIONS = {
    "bp", "bmi", "hr", "ekg", "ecg", "mri", "ct", "er", "icu", "rx", "otc", "covid", "covid19",
    "flu", "uti", "std", "sti", "hiv", "ibs", "gerd", "copd", "adhd", "ptsd", "ocd", "pcos",
    "hba1c", "inr", "psa", "crp", "esr", "ast", "alt", "alp", "ggt", "wbc", "rbc", "mcv", "rdw",
    "plt", "hgb", "hct", "ldl", "hdl", "tsh", "bun", "egfr", "a1c", "mg", "ml", "dl", "iu", "mcg",
    "pcp", "ob", "gyn", "ent", "pt", "ot", "doc", "dr", "meds", "med", "labs", "lab", "vit",
}  # fmt: skip


@cache
def vocabulary() -> tuple[frozenset[str], tuple[str, ...]]:
    """(all known words, common words used for spelling suggestions); empty if the file is gone."""
    path = Path(__file__).with_name("words.txt")
    if not path.is_file():
        return frozenset(), ()
    known, common = set(), []
    for line in path.read_text().splitlines():
        if line and not line.startswith("#"):
            word, count = line.split()
            known.add(word)
            if int(count) >= SUGGEST_MIN_COUNT and len(word) >= SUGGEST_MIN_LETTERS - 1:
                common.append(word)
    return frozenset(known), tuple(common)


def _known(word: str, document_words: set[str], known: frozenset[str]) -> bool:
    if word.isdigit() or word in ABBREVIATIONS or word in document_words:
        return True
    # plural "statins" → "statin", but not "cs" → "c" (vitamin C)
    return word in known or (len(word) > 3 and word.removesuffix("s") in known)


def clarification(message: str, excerpts: Iterable[str]) -> str | None:
    """A reply asking what the user means, or None when the message should be answered."""
    known, common = vocabulary()
    if not known:  # vocabulary missing: never guess
        return None
    words = WORD.findall(message.lower())
    content = [w for w in words if w not in FILLER]
    if not content or len(words) > MAX_WORDS:
        return None
    document_words = {w for text in excerpts for w in WORD.findall(text.lower())}
    if any(_known(w, document_words, known) for w in content):
        return None
    suggestions = {}
    for word in content:
        if len(word) >= SUGGEST_MIN_LETTERS:
            match = difflib.get_close_matches(word, common, n=1, cutoff=0.75)
            if not match:  # maybe a name we don't know (a new drug): let the model answer
                return None
            suggestions[word] = match[0]
    if suggestions:
        word, match = next(iter(suggestions.items()))
        return (
            f'I\'m not sure what you mean by "{word}". Did you mean "{match}"? You can ask a '
            f'full question, like "What do my documents say about {match}?"'
        )
    shown = " ".join(message.split())
    return (
        f'I\'m not sure what you mean by "{shown}". Could you ask a full question? For example: '
        '"Is my cholesterol high?" or "What does my visit summary say about my blood pressure?"'
    )
