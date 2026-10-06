"""v2 grounded training data: template cleaning, RAFT rendering, synthetic records."""

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import prepare_medquad as pm  # noqa: E402
import prompt_format as pf  # noqa: E402
import synthetic_records as sr  # noqa: E402

LONG = "This condition affects how the body processes certain nutrients and is treated with diet. "


def rec(i: int, focus: str, answer: str = LONG * 3, source: str = "2_GARD_QA") -> pm.Record:
    return pm.Record(f"{i:07d}_1", f"What is {focus}?", answer, focus, "information", source)


PROMPTS = pm.Prompts(
    "BASE", pf.read(pf.RAG_INSTRUCTIONS_PATH), pf.read(pf.NO_CONTEXT_INSTRUCTIONS_PATH)
)


# ---------------------------------------------------------------- cleaning


def test_clean_templates_drops_boilerplate_and_strips_echo():
    records = [
        rec(1, "A", "These resources address the diagnosis or management of A: - Gene Review"),
        rec(2, "B", "The Human Phenotype Ontology provides the following list of signs. " + LONG),
        rec(3, "C", "What causes C? " + LONG),
        rec(4, "D", "What is D? Short."),  # remainder too short: keep as is
        rec(5, "E", LONG),
    ]
    out, counts = pm.clean_templates(records)
    assert [r.focus for r in out] == ["C", "D", "E"]
    assert out[0].answer == LONG.strip() or out[0].answer.startswith("This condition")
    assert out[1].answer == "What is D? Short."
    assert counts == {
        "template_resource_list": 1,
        "template_hpo_table": 1,
        "template_echo_stripped": 1,
    }


# ---------------------------------------------------------------- RAFT rendering


@pytest.fixture
def split_records():
    return [
        rec(i, f"Disease {i}", f"Disease {i} fact. " * 30 + f"Unique marker {i}.")
        for i in range(300)
    ]


def test_modes_follow_configured_mix(split_records):
    rows = pm.render_grounded(split_records, PROMPTS, seed=1)
    modes = [r["mode"] for r in rows]
    for mode, share in pm.MODES:
        assert abs(modes.count(mode) / len(rows) - share) < 0.08


def test_closed_book_uses_no_context_prompt(split_records):
    row = next(r for r in pm.render_grounded(split_records, PROMPTS, 1) if r["mode"] == "closed")
    system = row["messages"][0]["content"]
    assert system == pf.system_without_excerpts("BASE", PROMPTS.no_context)
    assert "User documents:" not in system


def test_oracle_contains_gold_and_cites_its_numbers(split_records):
    rows = [r for r in pm.render_grounded(split_records, PROMPTS, 1) if r["mode"] == "oracle"]
    for row in rows[:50]:
        system, target = row["messages"][0]["content"], row["messages"][2]["content"]
        marker = re.search(
            r"Unique marker \d+\.", next(r.answer for r in split_records if r.id == row["id"])
        )
        assert marker.group(0) in system  # gold passage is among the excerpts
        cited = {int(n) for n in re.findall(r"\[(\d+)\]", target)}
        blocks = re.findall(r"\[(\d+)\] \([^)]+\)\n(.*?)(?=\n\n\[\d+\] \(|\Z)", system, re.S)
        gold_numbers = {int(n) for n, text in blocks if text.startswith(f"{row['focus']} fact.")}
        assert cited == gold_numbers and cited
        assert not target.startswith(pm.NOT_FOUND)


def test_distractor_only_excludes_gold_and_says_not_found(split_records):
    rows = [r for r in pm.render_grounded(split_records, PROMPTS, 1) if r["mode"] == "distractor"]
    assert rows
    for row in rows:
        system, target = row["messages"][0]["content"], row["messages"][2]["content"]
        gold = next(r.answer for r in split_records if r.id == row["id"])
        assert gold not in system and gold.split(" fact.")[0] + " fact." not in system
        assert target.startswith(pm.NOT_FOUND) and "[" not in target.split("\n\n")[0]


def test_grounded_prompts_never_exceed_app_top_k(split_records):
    long = [rec(i, f"Long {i}", f"Long {i} fact. " * 400) for i in range(40)]
    for row in pm.render_grounded(long + split_records, PROMPTS, 3):
        assert row["messages"][0]["content"].count("\n\n[") <= pm.MAX_EXCERPTS


def test_distractors_come_only_from_the_same_split(split_records):
    train, other = split_records[:150], split_records[150:]
    rows = pm.render_grounded(train, PROMPTS, 1)
    text = "".join(r["messages"][0]["content"] for r in rows)
    assert not any(f"Unique marker {i}." in text for i in range(150, 300))
    assert other  # sanity


def test_rendering_is_deterministic(split_records):
    a = pm.render_grounded(split_records, PROMPTS, 7)
    b = pm.render_grounded(split_records, PROMPTS, 7)
    assert json.dumps(a) == json.dumps(b)


def test_chunk_text_respects_size_and_keeps_words():
    text = "\n".join(" ".join(f"w{i}_{j}" for j in range(120)) + "." for i in range(5))
    chunks = pf.chunk_text(text, size=300)
    assert all(len(c) <= 300 for c in chunks)
    assert " ".join(chunks).split() == text.split()


# ---------------------------------------------------------------- synthetic records

SYN = sr.generate(3000, seed=11)
LAB_LINE = re.compile(
    r"(?:Your )?(?P<name>[A-Za-z][\w ,\-]*?)(?:: | result is |,)(?P<v>[\d.]+)[ ,]"
)


def _cited(answer: str) -> set[int]:
    return {int(n) for n in re.findall(r"\[(\d+)\]", answer)}


LAB_EXAMPLES = [e for e in SYN if e.kind in ("lab_value", "lab_direction")][:800]


@pytest.mark.parametrize("ex", LAB_EXAMPLES)
def test_lab_answers_match_the_document_and_direction(ex):
    (n,) = _cited(ex.answer)
    doc = ex.excerpts[n - 1]
    assert doc.filename.startswith("labs-")
    pattern = (
        r"lab report, your (?P<name>.+?) (?:was|were) (?P<v>[\d.]+) (?P<unit>\S+) \[\d+\], "
        r"which is (?P<where>above|below|within) the reference range"
    )
    m = re.search(pattern, ex.answer)
    analyte = next(a for a in sr.ANALYTES if a.display == m["name"])
    value = float(m["v"])
    assert m["v"] in doc.text  # the stated value is literally in the cited document
    expected = {"high": "above", "low": "below", "normal": "within"}[analyte.status(value)]
    assert m["where"] == expected
    assert "desirable" not in ex.answer
    if ex.kind == "lab_direction":
        polarity = (
            "high" if "high?" in ex.question else "low" if "too low?" in ex.question else "normal"
        )
        assert ex.answer.startswith("Yes") == (analyte.status(value) == polarity)


def test_absent_items_cite_nothing_and_are_really_absent():
    absent = [e for e in SYN if e.kind == "absent"]
    assert len(absent) > 300
    for ex in absent:
        assert not _cited(ex.answer) and ex.answer.startswith("I couldn't find")
        name = re.search(r"any (.+?) result", ex.answer).group(1)
        assert all(f"{name}:" not in d.text.lower() and f"your {name} result" not in d.text.lower()
                   for d in ex.excerpts)  # fmt: skip


def test_cited_document_type_matches_question():
    prefix = {"dose": "medications", "allergy": "medications", "vital": "visit-note"}
    for ex in SYN:
        if ex.kind in prefix:
            (n,) = _cited(ex.answer)
            assert ex.excerpts[n - 1].filename.startswith(prefix[ex.kind])


def test_records_are_fictional_marked_and_fit_one_chunk():
    for ex in SYN[:500]:
        for doc in ex.excerpts:
            assert doc.text.startswith(sr.BANNER)
            assert len(doc.text) <= pf.CHUNK_CHARS  # the app would retrieve it as a single chunk
            assert "Jordan Sample" not in doc.text


def test_layouts_differ_from_eval_fixtures():
    fixture_like = re.compile(r"\.{4,}|\s\|\s")  # dotted lab tables, pipe medication tables
    assert not any(fixture_like.search(d.text) for ex in SYN for d in ex.excerpts)


def test_end_to_end_v2_outputs(tmp_path):
    corpus = tmp_path / "MedQuAD" / "2_GARD_QA"
    corpus.mkdir(parents=True)
    for i in range(80):
        xml = (
            f'<Document id="{i:07d}"><Focus>Disease {i}</Focus><QAPairs><QAPair pid="1">'
            f'<Question qid="{i:07d}_1" qtype="information">What is Disease {i}?</Question>'
            f"<Answer>{LONG * 3}Marker {i}.</Answer></QAPair></QAPairs></Document>"
        )
        (corpus / f"{i}.xml").write_text(xml)
    out = tmp_path / "v2"
    argv = ["--source", str(corpus.parent), "--out", str(out), "--clean-templates", "--grounded"]
    stats = pm.main(argv + ["--synthetic-train", "20", "--synthetic-val", "5"])
    assert stats["modes"]["train"]["synthetic"] == 20 and stats["modes"]["val"]["synthetic"] == 5
    test_rows = [json.loads(line) for line in (out / "test.jsonl").read_text().splitlines()]
    assert all("User documents:" not in r["messages"][0]["content"] for r in test_rows)
    assert stats["splits"]["train"] == stats["modes"]["train"]["synthetic"] + sum(
        v for k, v in stats["modes"]["train"].items() if k != "synthetic"
    )
