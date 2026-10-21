"""Grounding probe: can a model answer questions about the user's own records correctly?

Builds prompts exactly like the app (shared prompt files + excerpt format) from the evaluation
fixtures in eval/fixtures (layouts never used in training), sends them to local Ollama models
and scores:
  value      - the expected value appears in the answer
  direction  - high/normal is stated correctly (and never "normal"/"desirable" for a high value)
  citation   - the answer cites the excerpt that holds the answer, as [n]
  absence    - for items not in the documents: says so and invents no value

    backend/.venv/bin/python training/grounding_probe.py phi3-base phi3-medquad phi3-medquad-v2
"""

import json
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "eval" / "fixtures"))
import make_fixtures as fx  # noqa: E402
import prompt_format as pf  # noqa: E402

OLLAMA = "http://127.0.0.1:11434/api/chat"
HIGH_WORDS = re.compile(
    r"\b(high|higher|above|elevated|exceeds?|over the|outside|prediabet\w*)\b", re.I
)
# Claims that a value IS normal (a bare mention of "normal" is not a claim).
CLAIMS_NORMAL = re.compile(
    r"\b(is|are|was|were|falls?|lies?)\s+(within|in)\s+(the\s+)?(normal|healthy|reference)"
    r"|\b(is|are|was|were)\s+(normal|desirable|optimal|healthy)\b|\bdesirable\b",
    re.I,
)
NORMAL_WORDS = re.compile(r"\b(normal|within|desirable|healthy range|optimal|not high)\b", re.I)
CLAIMS_ABNORMAL = re.compile(
    r"\b(elevated|too high|abnormal|is high|falls? below|is below the|above the reference)\b", re.I
)
ABSENT_WORDS = re.compile(
    r"(couldn'?t find|could not find|not (?:included|listed|found|present|mentioned)|"
    r"no (?:\w+ )?(?:result|record|value|information)|no mention|not (?:currently )?prescribed|"
    r"don'?t see|isn'?t (?:included|listed)|doesn'?t (?:include|list|mention))",
    re.I,
)

LAB_P1, LAB_P2, LAB_P3 = ("\n".join(lines) for lines in fx.LAB_PAGES)
MEDS = "\n".join(
    [
        fx.BANNER,
        "Medication List - Jordan Sample",
        "Last updated: 2026-08-21 by Dr. Example",
        "Medication | Dose | How often | Reason | Started",
    ]
    + [" | ".join(row) for row in fx.MEDICATIONS]
    + ["Allergies", "Penicillin - hives (2015).", "No known food allergies."]
)  # mirrors how the app's DOCX parser renders the fixture


def _column_report_text() -> str:
    """Current-results text of the column-layout fixture as the app extracts it (needs backend)."""
    try:
        sys.path.insert(0, str(HERE.parent / "backend"))
        from pha.rag.parsers import parse  # noqa: PLC0415

        pdf = HERE.parent / "eval" / "fixtures" / "docs" / "lab-report-columns.pdf"
        return parse(pdf.read_bytes(), ".pdf").pages[0][1]  # page block 0 = current results
    except Exception:  # run without the backend env: column probes are skipped
        return ""


COLUMN_REPORT = _column_report_text()
DOCS = {
    "lab1": pf.Excerpt("lab-report.pdf", 1, LAB_P1),
    "lab2": pf.Excerpt("lab-report.pdf", 2, LAB_P2),
    "lab3": pf.Excerpt("lab-report.pdf", 3, LAB_P3),
    "visit": pf.Excerpt("visit-summary.txt", 1, fx.VISIT_SUMMARY.strip()),
    "meds": pf.Excerpt("medication-list.docx", 1, MEDS),
    "cols": pf.Excerpt("lab-report-columns.pdf", 1, COLUMN_REPORT),
}


@dataclass(frozen=True)
class Probe:
    question: str
    docs: tuple[str, ...]  # excerpt order as the model sees it (≤4, like the app's top_k)
    gold: str | None  # doc key holding the answer; None = absent
    value: str | None = None
    direction: str | None = None  # "high" | "normal"


PROBES = [
    Probe("Is my LDL cholesterol high?", ("lab2", "visit", "lab3"), "lab2", "162", "high"),
    Probe("What was my A1C?", ("visit", "lab2", "lab1"), "lab2", "6.1", "high"),
    Probe("What was my HDL cholesterol?", ("lab2", "lab3", "meds"), "lab2", "48", "normal"),
    Probe("Is my fasting glucose normal?", ("lab1", "lab3", "visit"), "lab3", "108", "high"),
    Probe("What were my triglycerides?", ("lab3", "lab2"), "lab2", "140", "normal"),
    Probe("Is my creatinine okay?", ("lab3", "lab1", "visit"), "lab3", "0.9", "normal"),
    Probe("What was my hemoglobin?", ("lab2", "lab1"), "lab1", "14.2", "normal"),
    Probe("What dose of atorvastatin am I taking?", ("visit", "meds", "lab2"), "meds", "20 mg"),
    Probe("How much lisinopril do I take?", ("meds", "lab1"), "meds", "10 mg"),
    Probe("Am I allergic to any medications?", ("lab1", "meds", "visit"), "meds", "enicillin"),
    Probe("What was my blood pressure at my visit?", ("lab2", "visit"), "visit", "138/88"),
    Probe("What was my vitamin D level?", ("lab1", "lab2", "lab3"), None),
    Probe("What was my TSH?", ("lab3", "visit", "lab1"), None),
    Probe("Am I taking metformin? What dose?", ("meds", "visit"), None),
]
# Commercial-lab layout with current AND previous results (previous values must not be reported).
COLUMN_PROBES = [
    Probe("What was my creatinine?", ("cols", "visit"), "cols", "0.98", "normal"),
    Probe("Is my potassium high?", ("cols",), "cols", "5.6", "high"),
    Probe("What was my eGFR?", ("meds", "cols"), "cols", "101", "normal"),
    Probe("What was my glucose?", ("cols", "lab3"), "cols", "108", "high"),
    Probe("What was my BUN?", ("cols",), "cols", "15", "normal"),
]
if COLUMN_REPORT:
    PROBES += COLUMN_PROBES


def ask(model: str, probe: Probe, prompts: tuple[str, str]) -> str:
    excerpts = [DOCS[k] for k in probe.docs]
    system = pf.system_with_excerpts(prompts[0], prompts[1], excerpts)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": probe.question},
    ]
    options = {"temperature": 0, "seed": 0, "num_ctx": 4096, "num_predict": 300}
    body = json.dumps({"model": model, "stream": False, "options": options, "messages": messages})
    body = body.encode()
    req = urllib.request.Request(OLLAMA, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:  # noqa: S310 (loopback)
        return json.load(resp)["message"]["content"]


CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def normalize(answer: str) -> str:
    """Score what the user sees: the app strips control characters and quotes vary."""
    return CONTROL_CHARS.sub("", answer).replace("\u2019", "'").replace("\u2018", "'")


def score(probe: Probe, answer: str) -> dict[str, bool | None]:
    answer = normalize(answer)
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", answer)}
    if probe.gold is None:
        invented = re.search(r"\b\d+(\.\d+)?\s*(mg|ng|%|mIU|mmol|g/dL|mcg)", answer, re.I)
        return {"absence": bool(ABSENT_WORDS.search(answer)) and not invented}
    result: dict[str, bool | None] = {
        "value": probe.value.lower() in answer.lower(),
        "citation": probe.docs.index(probe.gold) + 1 in cited,
    }
    # Direction only counts when grounded: the correct value must be stated too.
    if probe.direction == "high":
        ok = bool(HIGH_WORDS.search(answer)) and not CLAIMS_NORMAL.search(answer)
        result["direction"] = ok and bool(result["value"])
    elif probe.direction == "normal":
        ok = bool(NORMAL_WORDS.search(answer)) and not CLAIMS_ABNORMAL.search(answer)
        result["direction"] = ok and bool(result["value"])
    return result


def run(models: list[str], out: Path | None = None) -> dict:
    prompts = (pf.read(pf.SYSTEM_PROMPT_PATH), pf.read(pf.RAG_INSTRUCTIONS_PATH))
    report = {}
    for model in models:
        rows = []
        for p in PROBES:
            answer = ask(model, p, prompts)
            rows.append({"question": p.question, "answer": answer, **score(p, answer)})
        rates = {}
        for key in ("value", "direction", "citation", "absence"):
            vals = [r[key] for r in rows if r.get(key) is not None]
            rates[key] = f"{sum(vals)}/{len(vals)}"
        report[model] = {"rates": rates, "rows": rows}
        print(f"{model:18} " + "  ".join(f"{k}={v}" for k, v in rates.items()), flush=True)
    if out:
        out.write_text(json.dumps(report, indent=2))
    return report


def rescore(path: Path) -> None:
    """Re-score saved answers after changing the scorer (no model calls)."""
    report = json.loads(path.read_text())
    by_question = {p.question: p for p in PROBES}
    for model, data in report.items():
        for row in data["rows"]:
            for key in ("value", "direction", "citation", "absence"):
                row.pop(key, None)
            row.update(score(by_question[row["question"]], row["answer"]))
        rates = {}
        for key in ("value", "direction", "citation", "absence"):
            vals = [r[key] for r in data["rows"] if r.get(key) is not None]
            rates[key] = f"{sum(vals)}/{len(vals)}"
        data["rates"] = rates
        print(f"{model:18} " + "  ".join(f"{k}={v}" for k, v in rates.items()))
    path.write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    if sys.argv[1:2] == ["--rescore"]:
        rescore(Path(sys.argv[2]))
        sys.exit()
    args = [a for a in sys.argv[1:] if not a.startswith("--out=")]
    out = next((Path(a[6:]) for a in sys.argv[1:] if a.startswith("--out=")), None)
    run(args or ["phi3-base"], out)
