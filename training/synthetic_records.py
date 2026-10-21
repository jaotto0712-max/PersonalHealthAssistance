# ruff: noqa: E501  (phrase pools and answer wordings read better one per line)
"""Synthetic personal health records + grounded Q&A for fine-tuning (fictional patients only).

Targets the v1 failure: reading values from the user's documents, comparing them to the
reference range in the right direction, citing [n], and saying when something is absent.
v2 layouts intentionally differ from eval/fixtures (no dotted lab tables, no pipe medication
tables). v3 (generate_v3) adds the app's extraction format, which the fixtures also pass through,
so for v3 only the fixtures' patients, values and phrasings are held out.
"""

import random
import re
from dataclasses import dataclass

from prompt_format import Excerpt

BANNER = "SYNTHETIC TRAINING RECORD - FICTIONAL PATIENT"
FIRST = [
    "Avery",
    "Riley",
    "Casey",
    "Morgan",
    "Taylor",
    "Quinn",
    "Rowan",
    "Elliot",
    "Harper",
    "Sage",
    "Parker",
    "Reese",
    "Emerson",
    "Dakota",
    "Skyler",
    "Finley",
    "Hayden",
    "Lennon",
]
LAST = [
    "Alvarez",
    "Brennan",
    "Chowdhury",
    "Delgado",
    "Eriksen",
    "Fofana",
    "Galloway",
    "Hoang",
    "Ibarra",
    "Jansen",
    "Kowalski",
    "Lindqvist",
    "Moreau",
    "Nakamura",
    "Okafor",
    "Petrov",
]
FIXTURE_NAMES = {"Jordan Sample"}  # eval/fixtures patient: never generated


@dataclass(frozen=True)
class Analyte:
    name: str
    unit: str
    low: float | None  # inclusive lower bound of normal, None = no lower bound
    high: float | None  # inclusive upper bound of normal, None = no upper bound
    mean: float
    sd: float
    decimals: int
    aliases: tuple[str, ...]

    def range_text(self) -> str:
        fmt = f"{{:.{self.decimals}f}}"
        if self.low is None:
            return f"below {fmt.format(self.high + 10**-self.decimals)} {self.unit}"
        if self.high is None:
            return f"{fmt.format(self.low)} {self.unit} or higher"
        return f"{fmt.format(self.low)}-{fmt.format(self.high)} {self.unit}"

    @property
    def display(self) -> str:
        """Name for mid-sentence use: lowercase first letter unless it's an acronym (LDL, eGFR)."""
        acronym = self.name[:2].isupper() or self.name.startswith("eGFR")
        return self.name if acronym else self.name[0].lower() + self.name[1:]

    @property
    def was(self) -> str:
        return "were" if self.name.endswith("s") else "was"

    def status(self, value: float) -> str:
        if self.high is not None and value > self.high:
            return "high"
        if self.low is not None and value < self.low:
            return "low"
        return "normal"


ANALYTES = [
    Analyte(
        "Total cholesterol", "mg/dL", None, 199, 195, 35, 0, ("total cholesterol", "cholesterol")
    ),
    Analyte(
        "LDL cholesterol",
        "mg/dL",
        None,
        99,
        115,
        35,
        0,
        ("LDL", "LDL cholesterol", "bad cholesterol"),
    ),
    Analyte(
        "HDL cholesterol",
        "mg/dL",
        40,
        None,
        52,
        14,
        0,
        ("HDL", "HDL cholesterol", "good cholesterol"),
    ),
    Analyte("Triglycerides", "mg/dL", None, 149, 140, 55, 0, ("triglycerides",)),
    Analyte("Hemoglobin A1c", "%", None, 5.6, 5.7, 0.8, 1, ("A1c", "hemoglobin A1c", "HbA1c")),
    Analyte("Fasting glucose", "mg/dL", 70, 99, 98, 18, 0, ("fasting glucose", "blood sugar")),
    Analyte("Creatinine", "mg/dL", 0.6, 1.3, 1.0, 0.3, 2, ("creatinine",)),
    Analyte("eGFR", "mL/min/1.73m2", 60, None, 82, 22, 0, ("eGFR", "kidney function (eGFR)")),
    Analyte("ALT", "U/L", 7, 56, 35, 20, 0, ("ALT", "liver enzyme ALT")),
    Analyte("AST", "U/L", 10, 40, 28, 14, 0, ("AST",)),
    Analyte("TSH", "mIU/L", 0.4, 4.0, 2.2, 1.6, 2, ("TSH", "thyroid (TSH)")),
    Analyte("Hemoglobin", "g/dL", 12.0, 17.5, 13.8, 1.8, 1, ("hemoglobin",)),
    Analyte(
        "White blood cell count",
        "x10^3/uL",
        4.0,
        11.0,
        7.0,
        2.6,
        1,
        ("white blood cell count", "WBC"),
    ),
    Analyte("Platelets", "x10^3/uL", 150, 400, 250, 75, 0, ("platelets", "platelet count")),
    Analyte("Sodium", "mmol/L", 135, 145, 139, 3.5, 0, ("sodium",)),
    Analyte("Potassium", "mmol/L", 3.5, 5.1, 4.3, 0.5, 1, ("potassium",)),
    Analyte("Vitamin D, 25-hydroxy", "ng/mL", 30, 100, 33, 14, 0, ("vitamin D",)),
    Analyte("Ferritin", "ng/mL", 24, 336, 110, 90, 0, ("ferritin", "iron stores (ferritin)")),
]

DRUGS = [
    ("Metformin", ["500 mg", "1000 mg"], ["twice daily with meals"], "type 2 diabetes"),
    ("Lisinopril", ["10 mg", "20 mg"], ["once daily"], "blood pressure"),
    ("Rosuvastatin", ["10 mg", "20 mg"], ["once daily at bedtime"], "high cholesterol"),
    ("Amlodipine", ["5 mg", "10 mg"], ["once daily"], "blood pressure"),
    (
        "Levothyroxine",
        ["50 mcg", "75 mcg", "100 mcg"],
        ["once daily before breakfast"],
        "hypothyroidism",
    ),
    ("Omeprazole", ["20 mg", "40 mg"], ["once daily before breakfast"], "acid reflux"),
    ("Sertraline", ["50 mg", "100 mg"], ["once daily"], "depression"),
    ("Losartan", ["25 mg", "50 mg"], ["once daily"], "blood pressure"),
    ("Metoprolol succinate", ["25 mg", "50 mg"], ["once daily"], "heart rate"),
    ("Montelukast", ["10 mg"], ["once daily in the evening"], "asthma"),
    ("Escitalopram", ["10 mg"], ["once daily"], "anxiety"),
    ("Hydrochlorothiazide", ["12.5 mg", "25 mg"], ["once daily in the morning"], "blood pressure"),
    ("Gabapentin", ["300 mg"], ["three times daily"], "nerve pain"),
    ("Albuterol inhaler", ["2 puffs"], ["every 4-6 hours as needed"], "wheezing"),
]
ALLERGIES = [
    ("penicillin", "hives"),
    ("sulfa drugs", "rash"),
    ("codeine", "nausea and vomiting"),
    ("aspirin", "wheezing"),
    ("amoxicillin", "rash"),
    ("latex", "itching"),
]

CLINICIAN = "Talk with your clinician about what this result means for you."


@dataclass(frozen=True)
class Example:
    question: str
    answer: str
    excerpts: list[Excerpt]
    kind: str


def _name(rng: random.Random) -> str:
    while (name := f"{rng.choice(FIRST)} {rng.choice(LAST)}") in FIXTURE_NAMES:
        pass
    return name


def _date(rng: random.Random) -> str:
    return f"{rng.randint(2024, 2026)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"


def _value(a: Analyte, rng: random.Random) -> float:
    roll = rng.random()
    if roll < 0.55:  # normal
        lo = a.low if a.low is not None else a.mean - 2 * a.sd
        hi = a.high if a.high is not None else a.mean + 2 * a.sd
        v = rng.uniform(max(lo, a.mean - 1.5 * a.sd), min(hi, a.mean + 1.5 * a.sd))
    elif roll < 0.85 and a.high is not None:  # high
        v = a.high + rng.uniform(0.05, 1.5) * a.sd
    elif a.low is not None:  # low
        v = a.low - rng.uniform(0.05, 1.0) * a.sd
    else:
        v = a.high + rng.uniform(0.05, 1.5) * a.sd
    # Status is always computed from this rounded, displayed value, so answers can't contradict it.
    return round(max(v, 10**-a.decimals), a.decimals)


def _fmt(a: Analyte, v: float) -> str:
    return f"{v:.{a.decimals}f}"


def _flag(status: str) -> str:
    return {"high": "H", "low": "L", "normal": ""}[status]


def lab_document(rng: random.Random, patient: str) -> tuple[str, str, list[tuple[Analyte, float]]]:
    analytes = rng.sample(ANALYTES, rng.randint(5, 8))
    results = [(a, _value(a, rng)) for a in analytes]
    date = _date(rng)
    layout = rng.randrange(3)
    head = f"{BANNER}\nLaboratory results for {patient}. Collected {date}.\n"
    if layout == 0:
        rows = [
            f"{a.name}: {_fmt(a, v)} {a.unit} "
            f"(reference {a.range_text()}) {_flag(a.status(v))}".rstrip()
            for a, v in results
        ]
    elif layout == 1:
        rows = ["Test,Result,Units,Reference,Flag"] + [
            f"{a.name},{_fmt(a, v)},{a.unit},{a.range_text()},{_flag(a.status(v)) or '-'}"
            for a, v in results
        ]
    else:
        rows = [
            f"Your {a.name} result is {_fmt(a, v)} {a.unit}; "
            f"the reference range is {a.range_text()}."
            for a, v in results
        ]
    return f"labs-{date}.pdf", head + "\n".join(rows), results


def medication_document(rng: random.Random, patient: str):
    meds = [
        (d, rng.choice(doses), rng.choice(freqs), reason)
        for d, doses, freqs, reason in rng.sample(DRUGS, rng.randint(2, 5))
    ]
    allergies = rng.sample(ALLERGIES, rng.choice([0, 1, 1, 2]))
    layout = rng.randrange(3)
    if layout == 0:
        lines = [f"- {d} {dose}, {freq} (for {reason})" for d, dose, freq, reason in meds]
    elif layout == 1:
        lines = [f"{d} -- {dose} -- {freq} -- {reason}" for d, dose, freq, reason in meds]
    else:
        lines = [
            f"{patient} takes {d} {dose} {freq} for {reason}." for d, dose, freq, reason in meds
        ]
    allergy_line = (
        ("Allergies: " + "; ".join(f"{a} ({r})" for a, r in allergies))
        if allergies
        else ("Allergies: no known drug allergies")
    )
    text = f"{BANNER}\nCurrent medications for {patient}, updated {_date(rng)}.\n" + "\n".join(
        lines
    )
    return "medications.txt", f"{text}\n{allergy_line}", meds, allergies


def visit_document(rng: random.Random, patient: str):
    date = _date(rng)
    bp = f"{rng.randint(104, 162)}/{rng.randint(62, 98)}"
    hr = rng.randint(54, 104)
    weight = rng.randint(52, 118)
    text = (
        f"{BANNER}\nClinic visit note for {patient}, {date}.\n"
        f"Vitals: blood pressure {bp} mmHg, heart rate {hr} bpm, weight {weight} kg.\n"
        f"Plan: continue current medications; follow up in {rng.choice([3, 6, 12])} months."
    )
    return f"visit-note-{date}.txt", text, {"date": date, "bp": bp, "hr": hr, "weight": weight}


def _lab_answer(a: Analyte, v: float, n: int, polarity: str, ref: str | None = None) -> str:
    """`ref`: the reference as the document prints it (v3 app format); v2 uses range_text."""
    status = a.status(v)
    where = {"high": "above", "low": "below", "normal": "within"}[status]
    fact = (
        f"your {a.display} {a.was} {_fmt(a, v)} {a.unit} [{n}], "
        f"which is {where} the reference range ({ref or a.range_text()})"
    )
    if polarity == "value":
        return f"According to your lab report, {fact}." + (
            f" {CLINICIAN}" if status != "normal" else ""
        )
    yes = (polarity == status) or (polarity == "normal" and status == "normal")
    opener = "Yes" if yes else "No"
    tail = f" {CLINICIAN}" if status != "normal" else ""
    return f"{opener}. According to your lab report, {fact}.{tail}"


def _was(alias: str) -> str:
    return "were" if alias.endswith("s") else "was"


def make_example(rng: random.Random) -> Example:
    patient = _name(rng)
    lab_name, lab_text, results = lab_document(rng, patient)
    med_name, med_text, meds, allergies = medication_document(rng, patient)
    visit_name, visit_text, vitals = visit_document(rng, patient)
    docs = [
        Excerpt(lab_name, 1, lab_text),
        Excerpt(med_name, 1, med_text),
        Excerpt(visit_name, 1, visit_text),
    ]
    rng.shuffle(docs)
    keep = rng.randint(2, 3)  # sometimes only 2 of the 3 documents are retrieved
    kind = rng.choices(
        ["lab_value", "lab_direction", "dose", "allergy", "vital", "absent"],
        [0.25, 0.25, 0.12, 0.1, 0.08, 0.2],
    )[0]
    gold = {
        "lab_value": lab_name,
        "lab_direction": lab_name,
        "dose": med_name,
        "allergy": med_name,
        "vital": visit_name,
    }.get(kind)
    excerpts = [d for d in docs if d.filename == gold] + [d for d in docs if d.filename != gold]
    excerpts = excerpts[:keep]
    rng.shuffle(excerpts)
    n = next((i for i, d in enumerate(excerpts, 1) if d.filename == gold), None)

    if kind in ("lab_value", "lab_direction"):
        a, v = rng.choice(results)
        alias = rng.choice(a.aliases)
        if kind == "lab_value":
            q = rng.choice(
                [
                    f"What {_was(alias)} my {alias}?",
                    f"What did my {alias} come back as?",
                    f"Can you tell me my {alias} result?",
                ]
            )
            return Example(q, _lab_answer(a, v, n, "value"), excerpts, kind)
        polarity = rng.choice(["high", "low", "normal"])
        be = "Are" if alias.endswith("s") else "Is"
        q = {
            "high": f"{be} my {alias} high?",
            "low": f"{be} my {alias} too low?",
            "normal": f"{be} my {alias} normal?",
        }[polarity]
        return Example(q, _lab_answer(a, v, n, polarity), excerpts, kind)
    if kind == "dose":
        d, dose, freq, _ = rng.choice(meds)
        q = rng.choice(
            [f"What dose of {d.lower()} am I taking?", f"How much {d.lower()} do I take?"]
        )
        return Example(
            q,
            f"According to your medication list, you take {d} {dose} {freq} [{n}].",
            excerpts,
            kind,
        )
    if kind == "allergy":
        q = rng.choice(["Am I allergic to any medications?", "Do I have any drug allergies?"])
        if allergies:
            listed = " and ".join(f"{a} ({r})" for a, r in allergies)
            return Example(
                q, f"Your medication list records an allergy to {listed} [{n}].", excerpts, kind
            )
        return Example(
            q, f"Your medication list notes no known drug allergies [{n}].", excerpts, kind
        )
    if kind == "vital":
        q = rng.choice(
            ["What was my blood pressure at my last visit?", "What was my blood pressure?"]
        )
        a = f"At your visit on {vitals['date']}, your blood pressure was {vitals['bp']} mmHg [{n}]."
        return Example(q, a, excerpts, kind)
    present = {a.name for a, _ in results}
    missing = rng.choice([a for a in ANALYTES if a.name not in present])
    alias = rng.choice(missing.aliases)
    q = f"What {_was(alias)} my {alias}?"
    a = (
        f"I couldn't find any {missing.display} result in your documents. If you've had this test, "
        "you can upload that report, or ask your clinician whether it's needed."
    )
    return Example(q, a, excerpts, kind)


def generate(count: int, seed: int) -> list[Example]:
    rng = random.Random(seed)
    return [make_example(rng) for _ in range(count)]


# ================================================================ v3 (add-grounded-finetune-v3)
# Multi-turn follow-ups, the app's extraction format (incl. older-results blocks and comments),
# tests with no reference range, absent medications and off-topic messages. Questions and
# answers are drawn from pools of phrasings so the model learns the task, not one template
# (v2's failures came from slot-filling a single answer template). v2's generate() is unchanged.


@dataclass(frozen=True)
class NoRangeTest:
    """A test the lab reports without a reference range ("Not Estab.")."""

    name: str
    unit: str
    mean: float
    sd: float
    decimals: int
    aliases: tuple[str, ...]

    @property
    def display(self) -> str:
        return self.aliases[0]  # "urine creatinine", not "creatinine, Urine"


NO_RANGE_TESTS = [
    NoRangeTest("Creatinine, Urine", "mg/dL", 120, 50, 1, ("urine creatinine",)),
    NoRangeTest("Protein, Total, Urine", "mg/dL", 10, 5, 1, ("urine protein",)),
    NoRangeTest("Sodium, Urine", "mmol/L", 100, 35, 0, ("urine sodium",)),
    NoRangeTest("Microalbumin, Urine", "mg/L", 12, 8, 1, ("urine microalbumin", "microalbumin")),
]
NO_RANGE_SENTENCE = "The lab gives no reference range for this test."
LAB_COMMENTS = [
    ("Potassium", "Specimen slightly hemolyzed; potassium may be falsely elevated."),
    ("Fasting glucose", "Non-fasting specimen; glucose may be affected."),
    ("Triglycerides", "Non-fasting specimen; triglycerides may be affected."),
    (None, "Specimen received after the stability window; results may be affected."),
]

# ---------------------------------------------------------------- phrasing pools

Q_VALUE = [
    "What {was} my {alias}?", "Can you tell me my {alias} result?", "What did my {alias} come back as?",
    "what {was} my {alias}", "How {was} my {alias}?", "Look up my {alias} for me.",
]  # fmt: skip
Q_IS_HIGH = [
    "Is that high?", "Is that too high?", "Is that elevated?", "Is that above normal?",
    "Does that mean it's high?", "is that high", "That seems high, is it?", "Is it too high?",
    "Is that higher than it should be?", "Is that over the limit?",
]  # fmt: skip
Q_IS_LOW = [
    "Is that low?", "Is that too low?", "Is that below normal?", "is it low", "Is that under the range?",
    "Does that mean it's low?", "Is it lower than it should be?",
]  # fmt: skip
Q_IS_NORMAL = [
    "Is that normal?", "Is that okay?", "Is that in the normal range?", "Is that fine?",
    "Is that a healthy number?", "is that ok", "Is that within range?", "Is that good?",
]  # fmt: skip
Q_HOW_IS_IT = [  # neutral: answered with the value and where it falls, no yes/no
    "What does that mean?", "How does that look?", "Should I be worried about that?",
    "Is that something to worry about?", "How bad is that?", "What do you make of that?",
]  # fmt: skip
Q_RANGE = [
    "What should it be?", "What's the normal range for it?", "What range is it supposed to be in?",
    "What's a normal level?", "What number is normal?", "What's the target?", "what is normal for that",
    "What should that number be?", "What's considered normal?", "What's the healthy range for it?",
]  # fmt: skip
Q_PREVIOUS = [  # every one must retrieve the older-results excerpt in the app (HISTORY_QUERY)
    "What was it last time?", "What was it before?", "Has it changed since last time?",
    "How does that compare to my last test?", "Was it different before?", "Is it going up?",
    "Is it getting better?", "Has it improved?", "what was it previously", "Did it change?",
    "What was it on my last report?", "Is it going down?", "Was it better on my last test?",
]  # fmt: skip
Q_OTHER = [
    "And my {alias}?", "What about my {alias}?", "How about my {alias}?", "and {alias}",
    "Can you also check my {alias}?", "What about {alias}?", "Same for my {alias}?",
]  # fmt: skip
Q_MED_REASON = [
    "What is it for?", "Why am I taking it?", "What's that for?", "What does it treat?",
    "Why was it prescribed?", "what do I take it for", "What condition is it for?",
]  # fmt: skip
Q_MED_START = [
    "When did I start it?", "How long have I been taking it?", "When was it started?",
    "Since when have I been on it?", "When did I begin taking it?", "how long have I been on that",
]  # fmt: skip
Q_MED_FREQ = [
    "How often do I take it?", "When should I take it?", "How many times a day?",
    "How often is that?", "When do I take that one?",
]  # fmt: skip
Q_PLAN = [
    "When should I get it rechecked?", "When is my next check?", "When should I follow up?",
    "How soon should I retest?", "When do I need to come back?", "When should I test it again?",
    "What's the plan for it?", "Do I need to repeat the test?",
]  # fmt: skip
Q_COMMENT = [
    "Could anything have affected that result?", "Is that result reliable?",
    "Was there anything wrong with the sample?", "Could that be a mistake?",
    "Should I trust that result?", "Is there a note about that test?",
]  # fmt: skip
Q_DOSE = ["What dose of {drug} am I taking?", "How much {drug} do I take?", "What's my {drug} dose?",
          "how much {drug} am I on", "What strength is my {drug}?"]  # fmt: skip
OFF_TOPIC = [
    "How is the weather today?", "Tell me a joke", "What's the capital of France?",
    "Can you write me a poem?", "Who won the game last night?", "What time is it?",
    "Can you help me with my taxes?", "Recommend a good movie", "What's 15 times 12?",
]  # fmt: skip
GREETINGS = ["Hi", "Hello", "Hey there", "Good morning", "hi!", "Thanks!", "thank you"]
OFF_TOPIC_ANSWER = (
    "I'm a health assistant, so I can't help with that. I can answer questions about your "
    "health documents, like lab results and medications, or give general health information."
)
GREETING_ANSWER = (
    "Hi! I can answer questions about your health documents, like lab reports, medication lists "
    "and visit notes, and give general health information. What would you like to know?"
)
THANKS_ANSWER = "You're welcome! Is there anything else you'd like to know?"


@dataclass(frozen=True)
class ExampleV3:
    question: str
    answer: str
    excerpts: list[Excerpt]
    kind: str
    history: list[dict[str, str]]  # earlier turns, oldest first: {"role", "content"}


@dataclass
class LabReport:
    filename: str
    current: str  # the current-results excerpt
    older: str | None  # the app's separate "Older results …" excerpt, if any
    results: list[tuple[Analyte, float]]
    previous: dict[str, tuple[float, str]]  # analyte name -> (older value, date)
    no_range: list[tuple[NoRangeTest, float]]
    comment: tuple[str | None, str] | None = None  # (affected analyte or None, comment text)
    app_format: bool = False

    def ref(self, a: Analyte) -> str:
        """The reference as this document prints it, so answers quote only what's there."""
        return _app_ref(a) if self.app_format else a.range_text()


def _us_date(rng: random.Random, years: tuple[int, int] = (2024, 2026)) -> str:
    return f"{rng.randint(1, 12):02d}/{rng.randint(1, 28):02d}/{rng.randint(*years)}"


def _app_ref(a: Analyte) -> str:
    """Reference as the lab prints it and the app copies it: 70-99, <100, >59."""
    fmt = f"{{:.{a.decimals}f}}"
    if a.low is None:
        return f"<{fmt.format(a.high + 10**-a.decimals)}"
    if a.high is None:
        return f">{fmt.format(a.low - 10**-a.decimals)}"
    return f"{fmt.format(a.low)}-{fmt.format(a.high)}"


def _no_range_value(t: NoRangeTest, rng: random.Random) -> float:
    return round(max(rng.gauss(t.mean, t.sd), 10**-t.decimals), t.decimals)


def lab_report_v3(rng: random.Random, patient: str) -> LabReport:
    """60% the app's extraction format (what users' PDFs become), else a v2 layout."""
    if rng.random() < 0.4:
        name, text, results = lab_document(rng, patient)
        return LabReport(name, text, None, results, {}, [])
    analytes = rng.sample(ANALYTES, rng.randint(4, 7))
    results = [(a, _value(a, rng)) for a in analytes]
    no_range = [
        (t, _no_range_value(t, rng)) for t in rng.sample(NO_RANGE_TESTS, rng.choice([0, 1, 1, 2]))
    ]
    date = _us_date(rng, (2025, 2026))
    lines = [f"{BANNER}", f"{patient} Date Collected: {date} Patient Report"]
    for a, v in results:
        flag = {"high": ", flagged High", "low": ", flagged Low", "normal": ""}[a.status(v)]
        lines.append(f"{a.name}: {_fmt(a, v)} {a.unit} (reference {_app_ref(a)}){flag}.")
    for t, v in no_range:
        lines.append(f"{t.name}: {v:.{t.decimals}f} {t.unit}. {NO_RANGE_SENTENCE}")
    comment = None
    if rng.random() < 0.4:
        names = {a.name for a, _ in results}
        options = [c for c in LAB_COMMENTS if c[0] is None or c[0] in names]
        comment = rng.choice(options)
        lines.append(comment[1])
    previous: dict[str, tuple[float, str]] = {}
    older = None
    if rng.random() < 0.6:
        prev_date = _us_date(rng, (2021, 2024))  # always before the current report
        for a, _ in rng.sample(results, rng.randint(2, len(results))):
            previous[a.name] = (_value(a, rng), prev_date)
        by_name = {a.name: a for a, _ in results}
        older = (
            f"Older results from {prev_date} (not current): "
            + "; ".join(
                f"{name} {_fmt(by_name[name], v)} {by_name[name].unit}"
                for name, (v, _) in previous.items()
            )
            + "."
        )
    return LabReport(
        f"labs-{date.replace('/', '-')}.pdf",
        "\n".join(lines),
        older,
        results,
        previous,
        no_range,
        comment=comment,
        app_format=True,
    )


def medication_document_v3(rng: random.Random, patient: str):
    """Medication list; half the time with a "started" date per drug."""
    meds = [
        (
            d,
            rng.choice(doses),
            rng.choice(freqs),
            reason,
            _date(rng) if rng.random() < 0.8 else None,
        )
        for d, doses, freqs, reason in rng.sample(DRUGS, rng.randint(2, 5))
    ]
    if rng.random() < 0.5:
        lines = [
            f"- {d} {dose}, {freq} (for {reason})" + (f", started {s}" if s else "")
            for d, dose, freq, reason, s in meds
        ]
    else:
        meds = [(d, dose, freq, reason, None) for d, dose, freq, reason, _ in meds]
        lines = [f"- {d} {dose}, {freq} (for {reason})" for d, dose, freq, reason, _ in meds]
    text = f"{BANNER}\nCurrent medications for {patient}, updated {_date(rng)}.\n" + "\n".join(
        lines
    )
    return "medications.txt", text, meds


# ---------------------------------------------------------------- answers (several wordings)


def _lab_answer_v3(
    a: Analyte, v: float, n: int, polarity: str, ref: str, rng: random.Random
) -> str:
    """Same facts as v2's _lab_answer (value, citation, where it falls, the printed reference),
    in one of several wordings. polarity: value | high | low | normal | neutral."""
    status = a.status(v)
    where = {"high": "above", "low": "below", "normal": "within"}[status]
    value = f"{_fmt(a, v)} {a.unit}"
    fact = rng.choice(
        [
            f"your {a.display} {a.was} {value} [{n}], which is {where} the reference range ({ref})",
            f"your {a.display} {a.was} {value} [{n}]. That is {where} the reference range ({ref})",
            f"your lab report shows {a.display} at {value} [{n}], {where} the reference range "
            f"({ref})",
        ]
    )
    if fact.startswith("your lab report"):
        sentence = fact[0].upper() + fact[1:] + "."
    else:
        sentence = (
            rng.choice(["According to your lab report, ", "On your lab report, "]) + fact + "."
        )
    tail = f" {CLINICIAN}" if status != "normal" else ""
    if polarity in ("value", "neutral"):
        return sentence + tail
    yes = polarity == status
    return f"{'Yes' if yes else 'No'}. {sentence}{tail}"


def _no_range_answer(t: NoRangeTest, v: float, n: int, rng: random.Random) -> str:
    value = f"{v:.{t.decimals}f} {t.unit}"
    return (
        rng.choice(
            [
                f"According to your lab report, your {t.display} was {value} [{n}]. The lab gives no "
                "reference range for this test, so it isn't rated high or low.",
                f"Your {t.display} was {value} [{n}]. Your report doesn't list a reference range for "
                "this test, so I can't say whether it's high or low.",
                f"Your lab report shows {t.display} at {value} [{n}], with no reference range given, "
                "so it isn't marked high or low.",
            ]
        )
        + f" {CLINICIAN}"
    )


def _absent_lab_answer(a: Analyte, rng: random.Random) -> str:
    return rng.choice(
        [
            f"I couldn't find any {a.display} result in your documents. If you've had this test, "
            "you can upload that report, or ask your clinician whether it's needed.",
            f"Your documents don't include a {a.display} result. If you've had the test, upload "
            "that report and I can look at it.",
        ]
    )


def _turns(question: str, answer: str) -> list[dict[str, str]]:
    return [{"role": "user", "content": question}, {"role": "assistant", "content": answer}]


def _q(rng: random.Random, pool: list[str], **fields: str) -> str:
    return rng.choice(pool).format(**fields)


# ---------------------------------------------------------------- examples

FOLLOW_UPS = {
    # kind: (weight, needs)
    "fu_direction": (0.14, None),
    "fu_neutral": (0.05, None),
    "fu_range": (0.08, None),
    "fu_previous": (0.28, "older"),
    "fu_other": (0.08, None),
    "fu_after_absent": (0.04, None),
    "fu_med": (0.10, None),
    "fu_plan": (0.05, None),
    "fu_comment": (0.30, "comment"),
    "chain3": (0.16, "older"),
    "topic_switch": (0.07, None),
    "no_range": (0.30, "no_range"),
    "absent_med": (0.05, None),
    "off_topic": (0.04, None),
    "greeting": (0.02, None),
    "after_upload": (0.08, None),
}
# The app's own notices, as they appear in earlier assistant turns (pha.chat.orchestrator)
NO_DOCUMENTS_NOTICE = (
    "You haven't uploaded any documents yet, so I can't see your health records. "
    "Here is general information.\n\n"
)
GENERAL_LINES = [
    "{name} is a common blood test; your clinician can explain what your result means.",
    "{name} is measured with a blood test and compared with a reference range from the lab.",
    "Results for {name} are interpreted against the lab's reference range and your health history.",
]


def make_example_v3(rng: random.Random) -> ExampleV3:
    patient = _name(rng)
    lab = lab_report_v3(rng, patient)
    med_name, med_text, meds = medication_document_v3(rng, patient)
    visit_name, visit_text, _ = visit_document(rng, patient)
    months = re.search(r"follow up in (\d+) months", visit_text).group(1)
    base = [
        Excerpt(lab.filename, 1, lab.current),
        Excerpt(med_name, 1, med_text),
        Excerpt(visit_name, 1, visit_text),
    ]
    available = {
        k: w
        for k, (w, needs) in FOLLOW_UPS.items()
        if needs is None or (needs == "older" and lab.older) or (needs == "comment" and lab.comment)
        or (needs == "no_range" and lab.no_range)
    }  # fmt: skip
    kind = rng.choices(list(available), list(available.values()))[0]

    def excerpts_with(gold: list[str], extra: Excerpt | None = None) -> tuple[list[Excerpt], dict]:
        """Gold documents always retrieved, others sometimes; numbered as the app numbers them."""
        chosen = [e for e in base if e.filename in gold]
        chosen += [e for e in base if e.filename not in gold and rng.random() < 0.6]
        if extra:
            chosen.append(extra)
        rng.shuffle(chosen)
        return chosen, {id(e): i for i, e in enumerate(chosen, 1)}

    def number(excerpts: list[Excerpt], filename: str) -> int:
        return next(
            i for i, e in enumerate(excerpts, 1) if e.filename == filename and e.text != lab.older
        )

    def value_turns(a: Analyte, v: float) -> list[dict[str, str]]:
        # the earlier answer cites the excerpt numbering of that turn
        q = _q(rng, Q_VALUE, was=_was(alias := rng.choice(a.aliases)), alias=alias)
        return _turns(q, _lab_answer_v3(a, v, rng.randint(1, 3), "value", lab.ref(a), rng))

    def previous_answer(a: Analyte, v: float, c: int, h: int) -> str:
        if a.name in lab.previous:
            pv, date = lab.previous[a.name]
            change = "higher" if v > pv else "lower" if v < pv else "the same"
            return rng.choice(
                [
                    f"Your previous {a.display} was {_fmt(a, pv)} {a.unit}, from {date} [{h}]. "
                    f"Your current result is {_fmt(a, v)} {a.unit} [{c}].",
                    f"On {date} your {a.display} was {_fmt(a, pv)} {a.unit} [{h}]; now it is "
                    f"{_fmt(a, v)} {a.unit} [{c}], so it is {change} than before.",
                ]
            )
        return (
            f"I couldn't find an earlier {a.display} result in your documents. The only one "
            f"listed is your current result, {_fmt(a, v)} {a.unit} [{c}]."
        )

    if kind in ("fu_direction", "fu_neutral", "fu_range", "fu_other", "fu_plan", "fu_comment"):
        if kind == "fu_comment" and lab.comment[0]:
            a, v = next((b, w) for b, w in lab.results if b.name == lab.comment[0])
        else:
            a, v = rng.choice(lab.results)
        history = value_turns(a, v)
        gold = [visit_name] if kind == "fu_plan" else [lab.filename]
        excerpts, _ = excerpts_with(gold)
        n = number(excerpts, gold[0])
        if kind == "fu_direction":
            polarity = rng.choice(["high", "low", "normal"])
            pool = {"high": Q_IS_HIGH, "low": Q_IS_LOW, "normal": Q_IS_NORMAL}[polarity]
            ans = _lab_answer_v3(a, v, n, polarity, lab.ref(a), rng)
            return ExampleV3(rng.choice(pool), ans, excerpts, kind, history)
        if kind == "fu_neutral":
            ans = _lab_answer_v3(a, v, n, "neutral", lab.ref(a), rng)
            return ExampleV3(rng.choice(Q_HOW_IS_IT), ans, excerpts, kind, history)
        if kind == "fu_range":
            ans = rng.choice(
                [
                    f"Your lab report lists the reference range for {a.display} as {lab.ref(a)} [{n}].",
                    f"The reference range on your report is {lab.ref(a)} [{n}].",
                    f"On your lab report, the normal range for {a.display} is {lab.ref(a)} [{n}].",
                ]
            )
            return ExampleV3(rng.choice(Q_RANGE), ans, excerpts, kind, history)
        if kind == "fu_plan":
            ans = rng.choice(
                [
                    f"Your visit note says to follow up in {months} months [{n}].",
                    f"According to your visit note, the plan is a follow-up in {months} months "
                    f"[{n}]. Your clinician can tell you whether this test will be repeated then.",
                ]
            )
            return ExampleV3(rng.choice(Q_PLAN), ans, excerpts, kind, history)
        if kind == "fu_comment":
            ans = (
                f'Your lab report includes this note: "{lab.comment[1]}" [{n}]. '
                "Ask your clinician whether the test should be repeated."
            )
            return ExampleV3(rng.choice(Q_COMMENT), ans, excerpts, kind, history)
        # fu_other: "And my HDL?" about another test, present or not
        present = [(b, w) for b, w in lab.results if b.name != a.name]
        if present and rng.random() < 0.75:
            b, w = rng.choice(present)
            q = _q(rng, Q_OTHER, alias=rng.choice(b.aliases))
            return ExampleV3(
                q, _lab_answer_v3(b, w, n, "value", lab.ref(b), rng), excerpts, kind, history
            )
        names = {b.name for b, _ in lab.results}
        missing = rng.choice([b for b in ANALYTES if b.name not in names])
        q = _q(rng, Q_OTHER, alias=rng.choice(missing.aliases))
        return ExampleV3(q, _absent_lab_answer(missing, rng), excerpts, kind, history)

    if kind in ("fu_previous", "chain3"):
        a, v = rng.choice(lab.results)
        history = value_turns(a, v)
        older = Excerpt(lab.filename, 1, lab.older)
        excerpts, num = excerpts_with([lab.filename], older)
        c, h = number(excerpts, lab.filename), num[id(older)]
        if kind == "chain3":  # value -> direction -> previous: three user turns
            polarity = rng.choice(["high", "low", "normal"])
            pool = {"high": Q_IS_HIGH, "low": Q_IS_LOW, "normal": Q_IS_NORMAL}[polarity]
            history += _turns(
                rng.choice(pool), _lab_answer_v3(a, v, rng.randint(1, 3), polarity, lab.ref(a), rng)
            )
        return ExampleV3(
            rng.choice(Q_PREVIOUS), previous_answer(a, v, c, h), excerpts, kind, history
        )

    if kind == "fu_after_absent":
        names = {b.name for b, _ in lab.results}
        missing = rng.choice([b for b in ANALYTES if b.name not in names])
        history = _turns(
            _q(rng, Q_VALUE, was=_was(alias := rng.choice(missing.aliases)), alias=alias),
            _absent_lab_answer(missing, rng),
        )
        b, w = rng.choice(lab.results)
        excerpts, _ = excerpts_with([lab.filename])
        n = number(excerpts, lab.filename)
        q = _q(rng, Q_OTHER, alias=rng.choice(b.aliases))
        return ExampleV3(
            q, _lab_answer_v3(b, w, n, "value", lab.ref(b), rng), excerpts, kind, history
        )

    if kind == "fu_med":
        d, dose, freq, reason, started = rng.choice(meds)
        excerpts, _ = excerpts_with([med_name])
        n = number(excerpts, med_name)
        history = _turns(
            _q(rng, Q_DOSE, drug=d.lower()),
            f"According to your medication list, you take {d} {dose} {freq} [{rng.randint(1, 3)}].",
        )
        roll = rng.random()
        if roll < 0.4:
            q = rng.choice(Q_MED_REASON)
            ans = rng.choice(
                [f"Your medication list says you take {d} for {reason} [{n}].",
                 f"{d} is listed for {reason} [{n}]."]
            )  # fmt: skip
        elif roll < 0.75:
            q = rng.choice(Q_MED_START)
            ans = (
                f"Your medication list says you started {d} on {started} [{n}]."
                if started
                else (
                    f"Your medication list [{n}] doesn't say when you started {d}. "
                    "Your clinician or pharmacy records would have that date."
                )
            )
        else:
            q = rng.choice(Q_MED_FREQ)
            ans = f"Your medication list says to take {d} {dose} {freq} [{n}]."
        return ExampleV3(q, ans, excerpts, kind, history)

    if kind == "no_range":
        t, v = rng.choice(lab.no_range)
        excerpts, _ = excerpts_with([lab.filename])
        n = number(excerpts, lab.filename)
        alias = rng.choice(t.aliases)
        q = rng.choice([f"Is my {alias} normal?", f"What was my {alias}?", f"Is my {alias} high?",
                        f"Is my {alias} okay?", f"Is my {alias} too low?", f"How is my {alias}?"])  # fmt: skip
        history = value_turns(*rng.choice(lab.results)) if rng.random() < 0.3 else []
        return ExampleV3(q, _no_range_answer(t, v, n, rng), excerpts, kind, history)

    if kind == "absent_med":
        listed = {d for d, *_ in meds}
        drug = rng.choice([d for d, *_ in DRUGS if d not in listed])
        excerpts, _ = excerpts_with([med_name])
        n = number(excerpts, med_name)
        ans = (
            f"I couldn't find {drug} in your medication list [{n}], so I can't tell you a dose. "
            "Your clinician or pharmacist can tell you whether you should be taking it."
        )
        return ExampleV3(_q(rng, Q_DOSE, drug=drug.lower()), ans, excerpts, kind, [])

    if kind in ("off_topic", "greeting"):
        # retrieval can return unrelated excerpts for these; the answer must not summarise them
        excerpts, _ = excerpts_with([rng.choice([lab.filename, med_name, visit_name])])
        history = value_turns(*rng.choice(lab.results)) if rng.random() < 0.3 else []
        if kind == "off_topic":
            return ExampleV3(rng.choice(OFF_TOPIC), OFF_TOPIC_ANSWER, excerpts, kind, history)
        q = rng.choice(GREETINGS)
        ans = THANKS_ANSWER if q.lower().startswith("thank") else GREETING_ANSWER
        return ExampleV3(q, ans, excerpts, kind, history)

    if kind == "after_upload":
        # earlier turns were answered before any document existed ("I can't see your records");
        # now the report is retrieved, and the answer must come from it, not repeat the notice
        a, v = rng.choice(lab.results)
        alias = rng.choice(a.aliases)
        q = _q(rng, Q_VALUE, was=_was(alias), alias=alias)
        history = _turns(q, NO_DOCUMENTS_NOTICE + rng.choice(GENERAL_LINES).format(name=a.name))
        if rng.random() < 0.5:  # an unrelated turn in between, also from before the upload
            other = rng.choice([b for b in ANALYTES if b.name != a.name])
            history += _turns(
                f"What is {other.display}?",
                NO_DOCUMENTS_NOTICE + rng.choice(GENERAL_LINES).format(name=other.name),
            )
        excerpts, _ = excerpts_with([lab.filename])
        n = number(excerpts, lab.filename)
        ask = rng.choice([q, f"I uploaded my report. {q}", f"Now can you check my {alias}?"])
        return ExampleV3(
            ask, _lab_answer_v3(a, v, n, "value", lab.ref(a), rng), excerpts, kind, history
        )

    # topic_switch: history about one thing, a self-contained question about another
    a, v = rng.choice(lab.results)
    history = value_turns(a, v)
    d, dose, freq, _, _ = rng.choice(meds)
    excerpts, _ = excerpts_with([med_name])
    n = number(excerpts, med_name)
    ans = f"According to your medication list, you take {d} {dose} {freq} [{n}]."
    return ExampleV3(_q(rng, Q_DOSE, drug=d.lower()), ans, excerpts, kind, history)


def generate_v3(count: int, seed: int, single_turn_share: float = 0.35) -> list[ExampleV3]:
    """v3 mix: v2's single-turn examples (kept so earlier skills don't regress) + the new kinds."""
    rng = random.Random(seed)
    out = []
    for _ in range(count):
        if rng.random() < single_turn_share:
            ex = make_example(rng)
            out.append(ExampleV3(ex.question, ex.answer, ex.excerpts, ex.kind, []))
        else:
            out.append(make_example_v3(rng))
    return out
