import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import prepare_medquad as pm  # noqa: E402

DOC = """<?xml version="1.0" encoding="UTF-8"?>
<Document id="{doc}" source="Test">
<Focus>{focus}</Focus>
<QAPairs>{pairs}</QAPairs>
</Document>"""
PAIR = (
    '<QAPair pid="{pid}"><Question qid="{doc}_{pid}" qtype="{qtype}">{q}</Question>'
    "<Answer>{a}</Answer></QAPair>"
)
LONG = "This is a sufficiently long answer about the condition and how it is treated. "


def make_doc(doc: str, focus: str, pairs: list[tuple[str, str, str]]) -> str:
    body = "".join(
        PAIR.format(pid=i, doc=doc, q=q, a=a, qtype=t) for i, (q, a, t) in enumerate(pairs, 1)
    )
    return DOC.format(doc=doc, focus=focus, pairs=body)


@pytest.fixture
def corpus(tmp_path) -> Path:
    """60 documents with distinct foci, plus edge cases."""
    root = tmp_path / "MedQuAD"
    (root / "2_GARD_QA").mkdir(parents=True)
    (root / "11_MPlusDrugs_QA").mkdir()
    for i in range(60):
        pairs = [
            (f"What is (are) Disease {i} ?", LONG * 2, "information"),
            (f"What causes Disease {i} ?", LONG, "causes"),
        ]
        (root / "2_GARD_QA" / f"{i:07d}.xml").write_text(
            make_doc(f"{i:07d}", f"Disease {i}", pairs)
        )
    # removed-answer subset, duplicate pair, too-short answer, missing focus
    (root / "11_MPlusDrugs_QA" / "d1.xml").write_text(
        make_doc("9000001", "Drug X", [("What is Drug X?", "", "information")])
    )
    (root / "2_GARD_QA" / "dup.xml").write_text(
        make_doc(
            "9000002",
            "Disease 0",
            [("What is (are) Disease 0 ?", LONG * 2, "information"), ("Short?", "Too short.", "x")],
        )
    )
    (root / "2_GARD_QA" / "nofocus.xml").write_text(
        make_doc(
            "9000003",
            "",
            [
                ("Q one about a thing?", LONG, "information"),
                ("Q two about a thing?", LONG + "x", "x"),
            ],
        )
    )
    return root


def test_parse_document_fields():
    recs = pm.parse_document(
        make_doc(
            "0000001", "Asthma", [("What is asthma ?", "<b>Asthma</b> is...", "information")]
        ).encode(),
        "3_GHR_QA",
    )
    assert recs == [
        pm.Record(
            "0000001_1", "What is asthma ?", "Asthma is...", "Asthma", "information", "3_GHR_QA"
        )
    ]


def test_clean_drops_empty_short_and_duplicates(corpus):
    records, dropped = pm.clean(pm.load_records(corpus))
    assert dropped == {"empty_answer": 1, "short_answer": 1, "duplicate": 1}
    assert all(r.answer and len(r.answer) >= pm.MIN_ANSWER_CHARS for r in records)
    assert not any(r.source == "11_MPlusDrugs_QA" for r in records)


def test_question_normalization():
    assert (
        pm.clean_question("What is (are) Adult Acute Leukemia ?") == "What is Adult Acute Leukemia?"
    )
    assert pm.clean_question("  How  to\n prevent  flu ?") == "How to prevent flu?"


def test_truncation_ends_on_sentence_boundary():
    text = "Sentence number one is here. " * 200
    out = pm.truncate_answer(text, limit=500)
    assert len(out) <= 500 and out.endswith(".")


def test_group_split_has_no_focus_leakage_and_rough_ratios(corpus):
    records, _ = pm.clean(pm.load_records(corpus))
    splits = pm.group_split(records, seed=13)
    keys = {name: {pm.group_key(r) for r in rs} for name, rs in splits.items()}
    assert (
        not (keys["train"] & keys["val"])
        and not (keys["train"] & keys["test"])
        and not (keys["val"] & keys["test"])
    )
    total = sum(len(rs) for rs in splits.values())
    assert total == len(records)
    assert 0.7 <= len(splits["train"]) / total <= 0.9
    assert splits["val"] and splits["test"]


def test_records_without_focus_stay_together(corpus):
    records, _ = pm.clean(pm.load_records(corpus))
    splits = pm.group_split(records, seed=13)
    homes = {name for name, rs in splits.items() for r in rs if r.id.startswith("9000003_")}
    assert len(homes) == 1


def test_end_to_end_outputs_are_reproducible_chat_jsonl(corpus, tmp_path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("SYSTEM PROMPT")
    zpath = tmp_path / "medquad.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        for p in corpus.rglob("*.xml"):
            zf.write(p, p.relative_to(corpus.parent))
    out1, out2 = tmp_path / "o1", tmp_path / "o2"
    stats = pm.main(["--source", str(corpus), "--out", str(out1), "--system-prompt", str(prompt)])
    pm.main(["--source", str(zpath), "--out", str(out2), "--system-prompt", str(prompt)])
    for name in ("train", "val", "test"):
        assert (out1 / f"{name}.jsonl").read_bytes() == (out2 / f"{name}.jsonl").read_bytes()
    line = json.loads((out1 / "train.jsonl").read_text().splitlines()[0])
    assert [m["role"] for m in line["messages"]] == ["system", "user", "assistant"]
    assert line["messages"][0]["content"] == "SYSTEM PROMPT"
    assert {"id", "focus", "qtype", "source"} <= set(line)
    assert json.loads((out1 / "stats.json").read_text())["splits"] == stats["splits"]


def test_inference_and_training_share_the_system_prompt():
    # The backend's default PHA_SYSTEM_PROMPT_PATH points at this same file.
    shared = Path(__file__).resolve().parents[2] / "training" / "system_prompt.txt"
    used_by_training = pm.SYSTEM_PROMPT_PATH
    assert used_by_training == shared and shared.is_file()
