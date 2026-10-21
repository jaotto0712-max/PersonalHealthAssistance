import json
import re

import pytest

from pha.chat.guard import STOPPED_NOTE, DegenerationGuard
from pha.config import REPO_ROOT


def run(text: str, chunk: int = 7) -> tuple[str, DegenerationGuard]:
    """Feed text in small chunks, like streamed tokens, and collect what the guard releases."""
    g = DegenerationGuard()
    out = [g.feed(text[i : i + chunk]) for i in range(0, len(text), chunk)]
    out.append(g.flush())
    return "".join(out), g


def test_normal_answer_passes_through_unchanged():
    text = (
        "Your LDL cholesterol was 162 mg/dL [1], which is above the reference range. "
        "Talk with your clinician about what this means for you.\n\n- Eat less saturated fat.\n"
        "- Exercise most days.\nYes. Yes."
    )
    shown, g = run(text)
    assert shown == text and not g.stopped


def test_repeated_paragraph_is_cut_before_the_repeat():
    para = (
        "If triglycerides are within a healthy range, then LDL may be above normal. "
        "This means the total level is high because there is too much bad cholesterol. "
    )
    shown, g = run("Cholesterol has several parts. " + para * 6)
    assert g.stopped and g.reason == "repeated_sentence"
    assert shown == "Cholesterol has several parts. " + para


def test_repeated_opener_loop_is_cut():
    items = [
        "fever and chills", "nausea", "blood in the urine", "pain", "kidney damage",
        "high blood pressure", "anemia",
    ]  # fmt: skip
    text = "".join(f"- Children with kidney stones may have {x}.\n" for x in items)
    shown, g = run(text)
    assert g.stopped and g.reason == "repeated_opener"
    assert shown.count("Children with kidney stones may have") == 4


def test_word_salad_is_cut():
    words = [
        "legends",
        "mythology",
        "fairytales",
        "fables",
        "tales",
        "stories",
        "poems",
        "poetry",
        "rhyme",
        "lyrics",
        "music",
        "melodies",
        "harmonies",
        "symphonies",
    ]
    salad = " ".join(words * 3)
    shown, g = run("Eat less salt and exercise regularly. You can also relax with " + salad)
    assert g.stopped and g.reason == "word_salad"
    assert shown == "Eat less salt and exercise regularly. "


def test_gibberish_with_punctuation_is_cut():
    garbage = (
        "Your documents are private health information. To make itineraccompany. "
        "Medicate OB1staying advice and IMPractice your health. NIversumedicate Dearly."
    )
    shown, g = run("Hemoglobin carries oxygen in your blood. " + garbage)
    assert g.stopped and g.reason == "gibberish"
    assert shown.startswith("Hemoglobin carries oxygen in your blood. ")
    assert "OB1staying" not in shown and "IMPractice" not in shown


def test_medical_vocabulary_is_not_gibberish():
    text = (
        "Pseudohypoparathyroidism and HbA1c are unrelated. HDL and LDL are measured in mg/dL. "
        "Glomerulonephritis affects eGFR. COVID-19 vaccines and SARS-CoV-2 are discussed. "
        "Electroencephalography records brain activity."
    )
    shown, g = run(text)
    assert not g.stopped and shown == text


def test_short_repeats_are_allowed():
    shown, g = run("No. No. Ask your clinician. No.")
    assert not g.stopped and shown == "No. No. Ask your clinician. No."


@pytest.mark.parametrize(
    "path",
    ["training/results/grounding_probe_v2.json", "training/results/grounding_probe_v1.json"],
)
def test_real_good_answers_are_never_cut(path):
    """Every grounding-probe answer from phi3-base and v2 (all non-degenerate) passes untouched."""
    report = json.loads((REPO_ROOT / path).read_text())
    for model in ("phi3-base", "phi3-medquad-v2"):
        for row in report.get(model, {}).get("rows", []):
            shown, g = run(row["answer"], chunk=3)
            assert not g.stopped, (model, row["question"], g.reason)
            assert shown == row["answer"]


def test_stopped_note_is_markdown_italic():
    assert STOPPED_NOTE.strip().startswith("_(") and STOPPED_NOTE.strip().endswith(")_")


GARBLED = (
    "- Itinerary information. I'ureaseacherithesealth to prescription medication and treatment "
    "advice NI ameducounticeaseither assume it is a healthatheliefallithere: You cannabody. "
    "Tookailwaysaidicate the following, accurate information."
)


def feed_all(text: str) -> tuple[DegenerationGuard, str]:
    guard = DegenerationGuard()
    shown = "".join(guard.feed(t) for t in re.findall(r"\S+\s*", text)) + guard.flush()
    return guard, shown


def test_mashed_words_are_stopped_before_they_are_shown():
    # a real phi3-medquad-v2 answer (2026-10-06)
    guard, shown = feed_all(GARBLED)
    assert guard.stopped and guard.reason == "gibberish"
    assert "ureaseacher" not in shown and "Itinerary information." in shown
    assert "garbled" in guard.note


@pytest.mark.parametrize(
    "sentence",
    [
        "Hyperparathyroidism and hydrochlorothiazide can both raise calcium levels.",
        "Non-small cell lung cancers include squamous cell carcinoma, cystadenocarcinoma and "
        "bronchioalveolar carcinoma.",
        "This enzyme is pseudocholinesterase, also called butyrylcholinesterase.",
        "Visit SmokefreeWomen and SmokefreeEspanol for help quitting.",
    ],
)
def test_real_long_words_are_not_garbled(sentence):
    guard, shown = feed_all(sentence + " Done.")
    assert not guard.stopped, guard.reason
    assert shown.startswith(sentence)


def test_repeat_stops_keep_the_repeating_note():
    guard, _ = feed_all("This exact sentence repeats forever. " * 3)
    assert guard.reason == "repeated_sentence" and "repeating itself" in guard.note


@pytest.mark.parametrize(
    ("text", "shown_before"),
    [
        # real v3 answers (2026-10-07) from a chat full of repeated answers, on every try
        (
            "and use. Yourpanding to help7ithway.sniets -3oclaimi and-to this document your "
            "evidence. If notice.",
            "and use. ",
        ),
        (
            "vokitheithway. Use. -4do yoursand4a4 the document to quote and not4miadicequmiasing "
            "not treatyourgap",
            "vokitheithway. Use. ",
        ),
    ],
)
def test_short_garbled_words_are_cut(text, shown_before):
    shown, g = run(text)
    assert g.stopped and g.reason == "gibberish" and shown == shown_before


@pytest.mark.parametrize(
    "text",
    [
        "Mutations in the GTPase gene change how GTPases and ATPases work.",
        "See labcorp_test_results.pdf and www.nlm.nih.gov for details.",
        "Your eGFR was 101 mL/min/1.73m2 [1]. HbA1c and vitamin B12 were normal in 2nd test.",
        "COVID19 and covid19 vaccines, CD4 counts and H2O are fine; so is dup22q11 deletion.",
    ],
)
def test_enzymes_files_and_units_are_not_garbled(text):
    shown, g = run(text)
    assert shown == text and not g.stopped
