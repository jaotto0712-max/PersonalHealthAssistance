"""Synthetic personal health records + grounded Q&A for fine-tuning (fictional patients only).

Targets the v1 failure: reading values from the user's documents, comparing them to the
reference range in the right direction, citing [n], and saying when something is absent.
Layouts intentionally differ from eval/fixtures (no dotted lab tables, no pipe medication
tables) so evaluation on the fixtures stays held-out.
"""

import random
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


def _lab_answer(a: Analyte, v: float, n: int, polarity: str) -> str:
    status = a.status(v)
    where = {"high": "above", "low": "below", "normal": "within"}[status]
    fact = (
        f"your {a.display} {a.was} {_fmt(a, v)} {a.unit} [{n}], "
        f"which is {where} the reference range ({a.range_text()})"
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
