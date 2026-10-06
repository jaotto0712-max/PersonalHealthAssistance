"""Column-aware extraction of lab result tables from PDFs (add-lab-table-extraction).

Lab reports print results as borderless tables. Plain text extraction turns
    Creatinine 01 1.06 1.94 08/12/2025 mg/dL 0.76-1.27
into a run of numbers with no labels: lab code, current, previous. Here each word is placed in
its column by x-position under the table's header row, and every result row becomes one
self-describing line, and previous results are grouped into a separate, explicitly labelled
line after the table:
    Creatinine: 1.06 mg/dL (reference 0.76-1.27).
    Older results from 08/12/2025 (not current): Creatinine 1.94 mg/dL; BUN 37 mg/dL.
Measured on a real report: with the previous value on the same line ("… Previous: 1.94 …") the
models reported it as the current value in 3-4 of 7 questions; with this layout, 0 of 7.
"""

import re
from dataclasses import dataclass, field

LINE_TOLERANCE = 3.0  # pt: words whose tops differ by less are on one line
SUPERSCRIPT_RATIO = 0.8  # smaller than this × the line's largest font = footnote marker
NAME_GAP = 20.0  # words left of (current column − this) belong to the test name
COLUMN_SLACK = 25.0  # values may start a little left of their header word

ROLE_WORDS = {
    "current": {"current", "result", "results", "value", "your"},
    "previous": {"previous", "prior", "last"},
    "units": {"units", "unit"},
    "reference": {"reference", "range", "interval", "normal"},
}
FLAG_WORDS = {"low", "high", "abnormal", "critical", "alert", "pending"}
SHORT_FLAGS = {"h", "l", "a", "hh", "ll"}  # only meaningful next to a numeric value
VALUE = re.compile(
    r"^[<>≤≥]?=?[-+]?\d[\d,]*(\.\d+)?%?$|^(positive|negative|non-?reactive|reactive|detected|not)$",
    re.I,
)
DATE = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$")

BOILERPLATE = re.compile(
    r"©|\(c\)\s*\d{4}|all rights reserved|page \d+ of \d+|date created and stored|"
    r"received this document in error|private and confidential|protected by (state|federal)|"
    r"enterprise report version|^icon legend$|out of reference range\s+critical",
    re.I,
)


@dataclass
class Word:
    text: str
    x0: float
    top: float
    size: float


@dataclass
class Row:
    test: list[str] = field(default_factory=list)
    columns: dict[str, list[str]] = field(default_factory=dict)

    def add(self, role: str, text: str) -> None:
        self.columns.setdefault(role, []).append(text)


def is_boilerplate(line: str) -> bool:
    return bool(BOILERPLATE.search(line.strip()))


def _lines(words: list[Word]) -> list[list[Word]]:
    lines: list[list[Word]] = []
    for w in sorted(words, key=lambda w: w.top):
        if lines and abs(lines[-1][0].top - w.top) <= LINE_TOLERANCE:
            lines[-1].append(w)
        else:
            lines.append([w])
    out = []
    for line in lines:
        biggest = max(w.size for w in line)
        kept = [w for w in line if w.size >= SUPERSCRIPT_RATIO * biggest]  # drop footnote markers
        out.append(sorted(kept, key=lambda w: w.x0))
    return out


HEADER_MAX_WORDS = 16
HEADER_MIN_GAP = 40.0  # pt between role columns: headers are spread out, prose is not


def _header_columns(line: list[Word]) -> list[tuple[float, str]] | None:
    # A header row is short, has no sentence punctuation, and its role words sit in columns.
    if len(line) > HEADER_MAX_WORDS or line[-1].text.endswith("."):
        return None
    found: dict[str, float] = {}
    for w in line:
        word = w.text.lower().strip(":,")
        for role, vocab in ROLE_WORDS.items():
            if word in vocab and role not in found:
                # "Previous Result": "Result" belongs to previous, not a second current column
                if role == "current" and "previous" in found:
                    continue
                found[role] = w.x0
    if len(found) < 2 or "current" not in found:
        return None
    columns = sorted((x, role) for role, x in found.items())
    if any(b[0] - a[0] < HEADER_MIN_GAP for a, b in zip(columns, columns[1:], strict=False)):
        return None
    return columns


def _assign(line: list[Word], columns: list[tuple[float, str]]) -> Row:
    current_x = next(x for x, role in columns if role == "current")
    row = Row()
    for w in line:
        if w.x0 < current_x - NAME_GAP:
            row.test.append(w.text)
            continue
        role = columns[0][1]
        for x, r in columns:
            if w.x0 >= x - COLUMN_SLACK:
                role = r
        row.add(role, w.text)
    return row


@dataclass
class Result:
    test: str
    values: list[str]
    units: str
    reference: str | None  # None: the lab says no range is established
    flags: list[str]
    specimen: str | None  # "blood" / "urine" when the name or the panel heading says so
    previous: list[str]
    previous_date: str
    label: str = ""  # set when another result on the page has the same name (see _label_twins)

    @property
    def name(self) -> str:
        return f"{self.test} ({self.label})" if self.label else self.test

    def line(self) -> str:
        value = " ".join(self.values) if self.values else "no numeric value"
        units = f" {self.units}" if self.units and self.values else ""
        flags = f", flagged {' '.join(self.flags)}" if self.flags else ""
        if self.reference is None:
            # A separate sentence, not "(reference …)": models put that slot into "within the
            # reference range (…)" whatever it says (measured in add-lab-specimen-…-clarity).
            return f"{self.name}: {value}{units}{flags}. {NO_RANGE}"
        return f"{self.name}: {value}{units} ({self.reference}){flags}."

    def older(self) -> str:
        return f"{self.name} {' '.join(self.previous)}{' ' + self.units if self.units else ''}"


# Same-name tests on different specimens (blood vs urine creatinine) are easy to mix up: label them
# and list them together. Unlabelled chemistry results are blood tests on lab reports.
URINE = re.compile(r"\b(urine|urinary|urinalysis)\b", re.I)
BLOOD = re.compile(r"\b(serum|plasma|blood)\b", re.I)
SPECIMEN_WORDS = re.compile(r"\b(urine|urinary|serum|plasma|blood|whole|random|spot)\b", re.I)
NO_RANGE = "The lab gives no reference range for this test."
TWIN_NOTE = re.compile(
    r"This report has \d+ different (?P<base>[^\n]+?) results: (?P<listed>[^\n]+?)\.$", re.M
)


def specimen_of(text: str) -> str | None:
    if URINE.search(text):
        return "urine"
    if BLOOD.search(text):
        return "blood"
    return None


def _base_name(test: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9/ ]", " ", SPECIMEN_WORDS.sub(" ", test.lower())).split())


def _format(row: Row, section_specimen: str | None) -> Result | None:
    current = row.columns.get("current", [])
    values = [t for t in current if VALUE.match(t)]
    flags = [t for t in current if t.lower() in FLAG_WORDS or (values and t.lower() in SHORT_FLAGS)]
    if not row.test or not (values or flags):
        return None
    test = " ".join(row.test).rstrip(":")
    ref = " ".join(row.columns.get("reference", []))
    if ref.lower().startswith("not estab"):
        reference = None
    else:
        reference = f"reference {ref}" if ref else "no reference given"
    previous = row.columns.get("previous", [])
    return Result(
        test=test,
        values=values,
        units=" ".join(row.columns.get("units", [])),
        reference=reference,
        flags=flags,
        specimen=specimen_of(test) or section_specimen,
        previous=[t for t in previous if VALUE.match(t)],
        previous_date=next((t for t in previous if DATE.match(t)), ""),
    )


def _label_twins(results: list[Result]) -> dict[int, str]:
    """Label results that share a base name across specimens; return {index of the first twin:
    note line}. "Protein, Total, Urine" and "Protein/Creat Ratio" are different tests (no note)."""
    groups: dict[str, list[int]] = {}
    for i, r in enumerate(results):
        groups.setdefault(_base_name(r.test), []).append(i)
    notes: dict[int, str] = {}
    for base, idx in groups.items():
        specimens = {results[i].specimen or "blood" for i in idx}
        if len(idx) < 2 or len(specimens) < 2:
            continue
        for i in idx:
            r = results[i]
            r.specimen = r.specimen or "blood"
            if not re.search(rf"\b{r.specimen}\b", r.test, re.I):
                r.label = r.specimen
        listed = "; ".join(
            f"{results[i].specimen} {' '.join(results[i].values) or 'no numeric value'}"
            f"{' ' + results[i].units if results[i].units and results[i].values else ''}"
            for i in idx
        )
        notes[idx[0]] = f"This report has {len(idx)} different {base} results: {listed}."
    return notes


def twin_notes(text: str) -> list[tuple[str, str]]:
    """(base test name, "blood 1.31 mg/dL; urine 88.2 mg/dL") for each same-name note in text."""
    return [(m["base"], m["listed"]) for m in TWIN_NOTE.finditer(text)]


def _older_lines(older: list[Result]) -> list[str]:
    by_date: dict[str, list[str]] = {}
    for r in older:
        by_date.setdefault(r.previous_date, []).append(r.older())
    return [
        f"{HISTORY_PREFIX} {'from ' + date if date else '(date not given)'} (not current): "
        + "; ".join(results)
        + "."
        for date, results in by_date.items()
    ]


HISTORY_PREFIX = "Older results"


def page_text(words: list[Word]) -> tuple[str, bool]:
    """Rebuild a page's text. Returns (text, found_table). Boilerplate lines are dropped."""
    current, older, found = page_parts(words)
    return "\n".join(p for p in (current, older) if p), found


def page_parts(words: list[Word]) -> tuple[str, str, bool]:
    """(current-results text, older-results text, found_table). Older results are kept apart so
    they can be indexed as separate "history" chunks (see Retriever)."""
    out: list[str | Result] = []
    tables: list[list[Result]] = []  # previous results, grouped by the table they came from
    columns: list[tuple[float, str]] | None = None
    section: str | None = None  # specimen named by the latest heading ("Urine Protein ...")
    found_table = False

    for line in _lines(words):
        if not line:
            continue
        plain = " ".join(w.text for w in line)
        if is_boilerplate(plain):
            continue
        header = _header_columns(line)
        if header:
            columns, found_table = header, True
            tables.append([])  # previous results belong right after their own table
            continue  # the header's meaning is now carried by every row
        if columns:
            result = _format(_assign(line, columns), section)
            if result:
                out.append(result)
                if result.previous:
                    tables[-1].append(result)
                continue
        section = specimen_of(plain)
        out.append(plain)

    results = [r for r in out if isinstance(r, Result)]
    notes = _label_twins(results)  # labels are set before any line is rendered
    lines: list[str] = []
    for item in out:
        if isinstance(item, str):
            lines.append(item)
            continue
        lines.append(item.line())
        if (i := results.index(item)) in notes:
            lines.append(notes[i])
    history = [line for older in tables for line in _older_lines(older)]
    return "\n".join(lines), "\n".join(history), found_table


def extract_pages(data: bytes) -> list[tuple[str, str, bool]] | None:
    """Per page (current text, older-results text, found_table) via word geometry, or None."""
    import io

    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = []
            for page in pdf.pages:
                raw = page.extract_words(x_tolerance=1.5, y_tolerance=2, extra_attrs=["size"])
                words = [Word(w["text"], w["x0"], w["top"], w["size"]) for w in raw]
                pages.append(page_parts(words))
            return pages
    except Exception:
        return None
