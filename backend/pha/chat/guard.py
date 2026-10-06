"""Model-independent protection against degenerate generations (loops and word salad).

Small quantized models intermittently degenerate on long answers (add-generation-guards):
phi3-medquad-v2 looped in 5/36 and phi3-base produced word salad in 2/36 no-document samples.
The guard releases text one complete sentence at a time and stops before a bad one is shown.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")
PUNCTUATION = re.compile(r"[.,;:!?()\[\]\n•*\-–—]")
MIN_REPEAT_WORDS = 5  # shorter sentences ("Yes.") may legitimately repeat
OPENER_WORDS = 5
OPENER_LIMIT = 5  # the same 5-word opener this many times = a loop
SALAD_WORDS = 40  # this many words with no punctuation = word salad
# Malformed "words" seen in real degenerate output: NIversumedicate, IMPractice, OB1staying,
# ifppingoradviceasevervacuation. Legit medical terms don't match (HbA1c, pseudohypoparathyroidism).
MALFORMED = re.compile(r"^(?:[A-Z]{2,}[a-z]{3,}|[A-Za-z]+\d+[a-z]{3,}|[A-Za-z]{25,})$")
MALFORMED_LIMIT = 2

STOPPED_NOTE = "\n\n_(I stopped this answer early because it started repeating itself.)_"


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

    @staticmethod
    def _is_gibberish(text: str) -> bool:
        tokens = re.findall(r"[A-Za-z0-9]+", text)
        return sum(1 for t in tokens if MALFORMED.match(t)) >= MALFORMED_LIMIT

    @staticmethod
    def _is_salad(text: str) -> bool:
        return any(len(run.split()) >= SALAD_WORDS for run in PUNCTUATION.split(text))

    def _stop(self, reason: str) -> None:
        self.stopped = True
        self.reason = reason
        self._buffer = ""
