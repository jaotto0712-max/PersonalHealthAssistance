# ruff: noqa: E501  (test data: real model answers quoted verbatim)
"""Scorers judged against real answers seen during development (both passes and failures)."""

import json
from pathlib import Path

import pytest

from eval.scoring import first_number, normalize, rouge_l, score_record

REPO = Path(__file__).resolve().parents[2]


def passes(expect, answer, cited=()):
    return all(score_record(expect, answer, list(cited)).values())


def test_previous_value_reported_as_current_fails():
    # real v2 answer before the lab-table fix
    answer = "According to your lab report, your BUN was 37 mg/dL [2], which is above the reference range (6-20 mg/dL)."
    assert not passes({"values": ["12"], "not_values": ["37"]}, answer)
    good = "According to your lab report, your BUN was 12 mg/dL [1], which is within the reference range (6-20 mg/dL)."
    assert passes({"values": ["12"], "not_values": ["37"]}, good)


def test_citation_must_name_the_right_file():
    expect = {"values": ["20 mg"], "first": False, "cite": "medication-list.docx"}
    answer = "According to your medication list, you take Atorvastatin 20 mg once nightly [2]."
    assert passes(expect, answer, ["medication-list.docx"])
    assert not passes(expect, answer, ["visit-summary.txt"])


def test_direction_rules_from_real_answers():
    # real base-model error: 48 is above 40, the answer claims below
    wrong = "Your HDL cholesterol level is reported to be at 48 mg/dL. This value falls below the recommended range of over 40 mg/dL."
    assert not passes({"values": ["48"], "direction": "normal"}, wrong)
    right = "According to your lab report, your HDL cholesterol was 48 mg/dL [1], which is within the reference range (>40)."
    assert passes({"values": ["48"], "direction": "normal"}, right)
    # real v1 error: "desirable" for a high LDL
    assert not passes(
        {"values": ["162"], "direction": "high"}, "Your LDL of 162 mg/dL is in the desirable range."
    )
    assert passes(
        {"values": ["11.8"], "direction": "low"},
        "Yes. Your hemoglobin was 11.8 g/dL [1], which is below the reference range.",
    )


def test_absent_with_stray_control_character_still_passes():
    answer = " I couldn'\x9dt find any TSH result in your documents. If you've had this test, you can upload that report."
    assert passes({"absent": True}, answer)
    assert not passes(
        {"absent": True}, "Your TSH was 2.7 mIU/L, within the normal range."
    )  # invented


def test_same_name_ambiguity():
    expect = {"ambiguous_values": ["1.31", "88.2"]}
    assert not passes(
        expect, "According to your lab report, your total urinary creatinine was 88.2 mg/dL [1]."
    )
    assert passes(
        expect,
        "Your report lists two creatinine results: blood 1.31 mg/dL [1] and urine 88.2 mg/dL [1].",
    )
    assert passes(expect, "Your report has a blood and a urine creatinine. Which one do you mean?")


def test_no_reference_must_not_claim_a_direction():
    expect = {"values": ["88.2"], "first": False, "no_reference": True}
    assert not passes(
        expect,
        "Your urine creatinine was 88.2 mg/dL, which is above the reference range (not established).",
    )
    assert passes(
        expect,
        "Your urine creatinine was 88.2 mg/dL [1]; the lab gives no reference range (not established).",
    )


def test_no_documents_notice():
    notice = "You haven't uploaded any documents yet, so I can't see your health records. Here is general information.\n\n..."
    assert passes({"notice": "no_documents"}, notice)
    assert not passes({"notice": "none"}, notice)
    assert passes({"notice": "none"}, "Vaccines train your immune system.")


def test_first_number_ignores_citations_and_ranges():
    assert first_number("Your eGFR [1] was 95 mL/min/1.73 (reference >59).") == "95"
    assert first_number("Range 0.76-1.27, value 1.06") == "1.06"
    assert first_number("The reference is >59 and yours is 95.") == "95"


def test_rouge_l():
    assert rouge_l("the cat sat", "the cat sat") == pytest.approx(1.0)
    assert rouge_l("", "x") == 0.0
    assert (
        0
        < rouge_l("diabetes is a disease of blood sugar", "diabetes affects blood sugar levels")
        < 1
    )


def test_normalize_unifies_quotes():
    assert normalize("couldn’t") == "couldn't"


@pytest.mark.parametrize("path", ["training/results/grounding_probe_v3.json"])
def test_saved_v2_probe_answers_pass_their_probe_expectations(path):
    """Cross-check: the v2 answers judged correct by hand also pass these scorers."""
    report = json.loads((REPO / path).read_text())
    rows = {r["question"]: r["answer"] for r in report["phi3-medquad-v2"]["rows"]}
    assert passes({"values": ["162"], "direction": "high"}, rows["Is my LDL cholesterol high?"])
    assert passes({"values": ["0.98"], "not_values": ["1.62"]}, rows["What was my creatinine?"])
    assert passes({"absent": True}, rows["What was my TSH?"])


def test_month_dates_are_not_the_stated_value():
    a = "According to your lab report from August 14, the hemoglobin A1c level is at 6.1%, prediabetes."
    assert first_number(a) == "6.1"
    a = "Your previous Creatinine level [1], dated from March 2nd, 2026, is reported as 1.62 mg/dL."
    assert first_number(a) == "1.62"
    assert first_number("Taken May 5 2026: 7.2 mmol/L") == "7.2"


def test_absent_accepts_not_provided_and_quoted_document_values():
    a = (
        "Your Vitamin D3 supplementation started with a dose of 1000 IU once daily [3]. However, "
        "the exact current levels are not provided in any excerpt from your documents."
    )
    assert passes({"absent": True, "allow_values": ["1000 IU"]}, a)
    assert not passes({"absent": True}, a)  # without the allowance the dose looks invented
    assert not passes({"absent": True}, "Metformin isn't listed, but the usual dose is 500 mg.")


def test_cite_accepts_any_listed_source():
    expect = {"values": ["6.1"], "cite": ["lab-report.pdf", "visit-summary.txt"]}
    assert passes(expect, "Your A1C is 6.1% [2].", ["visit-summary.txt"])
    assert not passes(expect, "Your A1C is 6.1% [2].", ["medication-list.docx"])


def test_ambiguity_needs_each_value_attributed_to_the_test():
    expect = {"ambiguous_values": ["1.31", "88.2"]}
    mislabelled = (
        "According to your lab report, the total urinary protein in your sample was 88.2 mg/dL [1], "
        "and the serum creatinine level was 1.31 mg/dL, which is flagged high."
    )
    assert not passes(expect, mislabelled)
    good = "Your blood creatinine was 1.31 mg/dL [1]; your urine creatinine was 88.2 mg/dL [1]."
    assert passes(expect, good)
    assert passes(expect, "Do you mean your blood or your urine creatinine?")
