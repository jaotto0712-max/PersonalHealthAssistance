"""v3 training data (add-grounded-finetune-v3): multi-turn, app format, no-range, absent meds."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import prepare_medquad as pm  # noqa: E402
import prompt_format as pf  # noqa: E402
import synthetic_records as sr  # noqa: E402

EXAMPLES = sr.generate_v3(3000, seed=11)
CITATION = re.compile(r"\[(\d+)\]")
VALUE = re.compile(r"(\d+(?:\.\d+)?) (?:mg/dL|mmol/L|mg/L|U/L|%|ng/mL|mIU/L|g/dL|x10\^3/uL|mL/min)")


def of_kind(kind: str) -> list[sr.ExampleV3]:
    found = [e for e in EXAMPLES if e.kind == kind]
    assert found, kind
    return found


def test_key_points_summary_is_stripped_and_body_kept():
    body = "Adult ALL is a cancer of the blood and bone marrow. " * 4
    answer = "Key Points\n- Adult ALL is a type of cancer. - Signs include fever.\n" + body
    rec = pm.Record("0000001_1", "What is adult ALL?", answer, "ALL", "information", "1_CancerGov")
    out, counts = pm.strip_key_points([rec])
    assert out[0].answer == body and counts["template_key_points_stripped"] == 1
    short = pm.Record("0000002_1", "q", "Key Points\n- a\nshort", "X", "information", "1_CancerGov")
    assert pm.strip_key_points([short])[0][0].answer == short.answer  # too short: unchanged


def test_mix_is_deterministic_and_covers_every_kind():
    assert [e.answer for e in sr.generate_v3(50, seed=3)] == [
        e.answer for e in sr.generate_v3(50, seed=3)
    ]
    kinds = {e.kind for e in EXAMPLES}
    new = {
        "fu_direction",
        "fu_range",
        "fu_previous",
        "fu_other",
        "fu_med",
        "topic_switch",
        "after_upload",
    }
    assert new | {"no_range", "absent_med", "lab_value"} <= kinds
    multi = sum(bool(e.history) for e in EXAMPLES) / len(EXAMPLES)
    assert 0.45 < multi < 0.7  # most v3 examples are conversations; v2 skills stay in the mix


def test_history_is_well_formed():
    lengths = set()
    for e in EXAMPLES:
        if e.history:
            roles = [t["role"] for t in e.history]
            assert roles == ["user", "assistant"] * (len(roles) // 2), roles
            assert all(t["content"].strip() for t in e.history)
            lengths.add(len(roles))
    assert lengths == {2, 4}  # two- and three-turn conversations


def test_documents_arriving_mid_conversation_are_used():
    for e in of_kind("after_upload"):
        assert all(
            t["content"].startswith("You haven't uploaded")
            for t in e.history
            if t["role"] == "assistant"
        )
        assert CITATION.search(e.answer) and not e.answer.startswith(("I couldn't", "You haven't"))


def test_citations_point_at_excerpts_holding_the_stated_values():
    for e in EXAMPLES:
        for match in CITATION.finditer(e.answer):
            n = int(match.group(1))
            assert 1 <= n <= len(e.excerpts), (e.kind, e.answer)
            # the value stated right before a citation is in the cited excerpt
            before = e.answer[: match.start()]
            values = VALUE.findall(before[-60:])
            if values:
                assert values[-1] in e.excerpts[n - 1].text, (e.kind, e.answer)


def test_no_range_answers_make_no_high_or_low_claim():
    for e in of_kind("no_range"):
        assert re.search(r"no reference range|doesn't list a reference range", e.answer)
        assert not re.search(r"\b(above|below|within) the reference range", e.answer)
        assert sr.NO_RANGE_SENTENCE in "\n".join(x.text for x in e.excerpts)


def test_absent_medication_answers_give_no_dose():
    for e in of_kind("absent_med"):
        drug = re.search(r"couldn't find (.+?) in your medication list", e.answer).group(1)
        med_list = next(x.text for x in e.excerpts if x.filename == "medications.txt")
        assert drug not in med_list
        assert not re.search(r"\d+(\.\d+)?\s*(mg|mcg|puffs)\b", e.answer)


def test_previous_results_come_from_an_earlier_older_results_block():
    for e in of_kind("fu_previous"):
        older = next(x.text for x in e.excerpts if x.text.startswith("Older results from"))
        current = next(x.text for x in e.excerpts if "Date Collected" in x.text)
        older_year = int(re.search(r"from \d\d/\d\d/(\d{4})", older).group(1))
        current_year = int(re.search(r"Collected: \d\d/\d\d/(\d{4})", current).group(1))
        assert older_year < current_year
        if e.answer.startswith("Your previous"):
            date = re.search(r"from (\d\d/\d\d/\d{4})", e.answer).group(1)
            assert date in older


def test_app_format_lines_match_the_extractor():
    lines = [
        line
        for e in EXAMPLES
        for x in e.excerpts
        if "Date Collected" in x.text
        for line in x.text.splitlines()[2:]
    ]
    pattern = re.compile(
        r"^[A-Za-z0-9 ,/()^-]+: [\d.]+ \S+ \(reference [<>]?[\d.]+(-[\d.]+)?\)"
        r"(, flagged (High|Low))?\.$|^[A-Za-z ,]+: [\d.]+ \S+\. The lab gives no reference range"
    )
    comments = {c for _, c in sr.LAB_COMMENTS}
    lines = [line for line in lines if line not in comments]
    assert lines and all(pattern.match(line) for line in lines), next(
        line for line in lines if not pattern.match(line)
    )


def test_no_eval_fixture_patient_or_layout():
    text = "\n".join(x.text for e in EXAMPLES for x in e.excerpts)
    assert "Jordan Sample" not in text and "SYNTHETIC TEST DOCUMENT" not in text


def test_rows_put_history_between_system_and_question():
    prompts = pm.Prompts(
        "BASE", pf.read(pf.RAG_INSTRUCTIONS_PATH), pf.read(pf.NO_CONTEXT_INSTRUCTIONS_PATH)
    )
    rows = pm.synthetic_rows(200, 5, prompts, "train", version=3)
    multi = next(r for r in rows if len(r["messages"]) == 5)
    roles = [m["role"] for m in multi["messages"]]
    assert roles == ["system", "user", "assistant", "user", "assistant"]
    v2 = pm.synthetic_rows(20, 5, prompts, "train")  # v2 stays single-turn and unchanged
    assert all(len(r["messages"]) == 3 for r in v2)


def test_quoted_reference_ranges_appear_in_app_format_excerpts():
    checked = 0
    for e in EXAMPLES:
        for m in re.finditer(
            r"reference range \(([^)]+)\)|reference range for .+? as (\S+) \[", e.answer
        ):
            ref = m.group(1) or m.group(2)
            cited = [int(c) for c in CITATION.findall(e.answer)]
            docs = [
                e.excerpts[c - 1].text for c in cited if "Date Collected" in e.excerpts[c - 1].text
            ]
            if docs:
                assert any(f"(reference {ref})" in d for d in docs), (e.kind, e.answer)
                checked += 1
    assert checked > 100


def test_held_out_eval_follow_ups_never_appear_in_training():
    import json

    records = Path(__file__).resolve().parents[2] / "eval" / "sets" / "records.jsonl"
    held_out = [
        json.loads(line)["question"]
        for line in records.read_text().splitlines()
        if json.loads(line)["category"] == "followup_heldout"
    ]
    assert len(held_out) >= 8
    training = {e.question.lower().strip(" ?!.") for e in sr.generate_v3(20000, seed=1)}
    assert not [q for q in held_out if q.lower().strip(" ?!.") in training]


def test_previous_questions_retrieve_older_results_in_the_app():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
    from pha.rag.retriever import HISTORY_QUERY

    assert all(HISTORY_QUERY.search(q) for q in sr.Q_PREVIOUS)
    for e in of_kind("fu_previous") + of_kind("chain3"):
        assert any(x.text.startswith("Older results from") for x in e.excerpts)


def test_off_topic_and_greetings_do_not_summarise_excerpts():
    for e in of_kind("off_topic") + of_kind("greeting"):
        assert e.excerpts  # retrieval returned something unrelated
        assert not CITATION.search(e.answer) and not VALUE.search(e.answer)


def test_comment_and_plan_answers_quote_the_documents():
    for e in of_kind("fu_comment"):
        quoted = re.search(r'"(.+?)"', e.answer).group(1)
        n = int(CITATION.search(e.answer).group(1))
        assert quoted in e.excerpts[n - 1].text
    for e in of_kind("fu_plan"):
        months = re.search(r"(\d+) months", e.answer).group(1)
        n = int(CITATION.search(e.answer).group(1))
        assert f"follow up in {months} months" in e.excerpts[n - 1].text


def test_phrasing_variety():
    multi = [e.question for e in EXAMPLES if e.history]
    assert len(set(multi)) > 150  # v3 first draft: 44
    answers_start = {e.answer.split(",")[0][:25] for e in EXAMPLES if e.kind == "fu_direction"}
    assert len(answers_start) >= 4  # several answer wordings, not one template
