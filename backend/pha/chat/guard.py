"""Model-independent protection against degenerate generations (loops and word salad).

Small quantized models intermittently degenerate on long answers (add-generation-guards):
phi3-medquad-v2 looped in 5/36 and phi3-base produced word salad in 2/36 no-document samples.
The guard releases text one complete sentence at a time and stops before a bad one is shown.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")
PUNCTUATION = re.compile(r"[.,;:!?()\[\]\n•*\-–—]")
MIN_REPEAT_WORDS = 5  # shorter sentences ("Yes.") may legitimately repeat
OPENER_WORDS = 5
OPENER_LIMIT = 5  # the same 5-word opener this many times = a loop
SALAD_WORDS = 40  # this many words with no punctuation = word salad
# Malformed "words" seen in real degenerate output: NIversumedicate, IMPractice, OB1staying,
# ifppingoradviceasevervacuation. Legit medical terms don't match (HbA1c, pseudohypoparathyroidism).
# Also a digit wedged into a word ("yoursand4a4"), a digit leading letters ("3oclaimi") and words
# joined by a full stop ("help7ithway.sniets"), from two real v3 answers (2026-10-07). Calibrated
# on 149,749 sentences (model answers, NIH answers, all MedQuAD training answers): 8 reach the
# limit, all typos in MedQuAD's own text ("600calories 200calories"), none in model answers.
# Enzymes ("GTPase", "ATPase") are exempt; "HbA1c", "B12" and "covid19" don't match.
MALFORMED = re.compile(r"^(?:[A-Z]{2,}[a-z]{3,}|[A-Za-z]+\d+[a-z]{3,}|[A-Za-z]{25,}|\d+[a-z]{5,})$")
WEDGED = re.compile(r"^[A-Za-z]*[a-z]{3,}\d+[a-z]+\d*$")
ENZYME = re.compile(r"ases?$")
JOINED = re.compile(r"\b[A-Za-z]*[a-z]{2}\.[a-z]{3,}\b")
FILE_OR_SITE = re.compile(r"\.(?:com|org|gov|edu|net|html?|pdf|txt|docx?|nih|uk|io|jsonl?)\b|www")
MALFORMED_LIMIT = 2

# Mashed words: "I'ureaseacherithesealth ... healthatheliefallithere" (a real v2 answer, 2026-10-06)
# are long tokens no medical text contains, too short for MALFORMED. A sentence with 2+ distinct
# long words that are neither in MedQuAD's vocabulary (long_words.txt) nor medically suffixed
# is garbled. Calibrated: 0/12,849 false alarms on NIH answers for held-out diseases, 3/5,322 on
# model answers (2 of them real garbage: invented URLs, "potassamountaining").
LONG_WORD_MIN = 14
MASHED_LIMIT = 2
WORD = re.compile(r"[A-Za-z]+")
CAMEL = re.compile(r"[a-z][A-Z]")  # brand or site names (SmokefreeWomen), not mashed output
INFLECTION = re.compile(r"(?:ies|es|s|ed|ing|ly)$")
MEDICAL_ENDING = re.compile(
    r"(?:omas?|itis|os[ie]s|ases?|emia|opathy|ectomy|olog(?:y|ist)|cytes?|genic|plasia|lar|ial"
    r"|ines?|ides?|ism|ia|ics?|al|ous|oid|ure)$"
)


def stem(word: str) -> str:
    return INFLECTION.sub("", word.lower())


def _load_long_words() -> frozenset[str]:
    path = Path(__file__).with_name("long_words.txt")
    if not path.is_file():
        return frozenset()
    return frozenset(
        line.strip() for line in path.read_text().splitlines() if line and not line.startswith("#")
    )


LONG_WORDS = _load_long_words()

STOPPED_NOTE = "\n\n_(I stopped this answer early because it started repeating itself.)_"
GARBLED_NOTE = "\n\n_(I stopped this answer early because the text became garbled.)_"


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


@dataclass
class DegenerationGuard:
    stopped: bool = False
    reason: str | None = None
    _buffer: str = ""
    _seen: set[tuple[str, ...]] = field(default_factory=set)
    _openers: Counter = field(default_factory=Counter)

    def feed(self, text: str) -> str:
        """Add model output; return the text that is safe to show now ('' if none yet)."""
        if self.stopped:
            return ""
        self._buffer += text
        released = []
        while True:
            match = SENTENCE_END.search(self._buffer)
            if not match:
                break
            sentence = self._buffer[: match.end()]
            if not self._accept(sentence):
                return "".join(released)
            released.append(sentence)
            self._buffer = self._buffer[match.end() :]
        if self._is_salad(self._buffer):
            self._stop("word_salad")
            return "".join(released)
        if self._is_gibberish(self._buffer):  # long unterminated garbage
            self._stop("gibberish")
            return "".join(released)
        return "".join(released)

    def flush(self) -> str:
        """End of generation: release the last (unterminated) sentence if it's acceptable."""
        if self.stopped or not self._buffer:
            return ""
        tail, self._buffer = self._buffer, ""
        return tail if self._accept(tail) else ""

    def _accept(self, sentence: str) -> bool:
        if self._is_salad(sentence):
            self._stop("word_salad")
            return False
        if self._is_gibberish(sentence):
            self._stop("gibberish")
            return False
        words = tuple(_words(sentence))
        if len(words) >= MIN_REPEAT_WORDS:
            if words in self._seen:
                self._stop("repeated_sentence")
                return False
            self._seen.add(words)
        if len(words) >= OPENER_WORDS:
            opener = words[:OPENER_WORDS]
            self._openers[opener] += 1
            if self._openers[opener] >= OPENER_LIMIT:
                self._stop("repeated_opener")
                return False
        return True

    @property
    def note(self) -> str:
        """What to tell the user after a stop."""
        return GARBLED_NOTE if self.reason in ("gibberish", "word_salad") else STOPPED_NOTE

    @staticmethod
    def _is_gibberish(text: str) -> bool:
        tokens = re.findall(r"[A-Za-z0-9]+", text)
        malformed = sum(
            1 for t in tokens if (MALFORMED.match(t) or WEDGED.match(t)) and not ENZYME.search(t)
        )
        malformed += sum(1 for j in JOINED.findall(text) if not FILE_OR_SITE.search(j))
        if malformed >= MALFORMED_LIMIT:
            return True
        return len(mashed_words(text)) >= MASHED_LIMIT

    @staticmethod
    def _is_salad(text: str) -> bool:
        return any(len(run.split()) >= SALAD_WORDS for run in PUNCTUATION.split(text))

    def _stop(self, reason: str) -> None:
        self.stopped = True
        self.reason = reason
        self._buffer = ""


def mashed_words(text: str) -> set[str]:
    """Distinct long words that no medical text uses and that don't look like medical terms."""
    if not LONG_WORDS:  # vocabulary missing: never guess
        return set()
    return {
        w.lower()
        for w in WORD.findall(text)
        if len(w) >= LONG_WORD_MIN
        and not CAMEL.search(w)
        and stem(w) not in LONG_WORDS
        and not MEDICAL_ENDING.search(w.lower())
    }
