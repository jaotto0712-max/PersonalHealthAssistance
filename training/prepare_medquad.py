"""Prepare MedQuAD for LoRA fine-tuning: parse → clean → dedupe → leak-free split → chat JSONL.

Standard library only, so it runs unchanged locally and in Colab.

    python training/prepare_medquad.py --download            # fetch pinned MedQuAD, then prepare
    python training/prepare_medquad.py --source path/to/MedQuAD-dir-or.zip

Outputs (default data/medquad/): train.jsonl, val.jsonl, test.jsonl, stats.json

Dataset: MedQuAD (Ben Abacha & Demner-Fushman, "A question-entailment approach to question
answering", BMC Bioinformatics 2019), CC BY 4.0, https://github.com/abachaa/MedQuAD
"""

import argparse
import io
import json
import random
import re
import statistics
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

import prompt_format as pf

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
MEDQUAD_COMMIT = "577bd37b96c02d1833b2c9eed2de9f96964e96cb"
MEDQUAD_URL = f"https://github.com/abachaa/MedQuAD/archive/{MEDQUAD_COMMIT}.zip"
SYSTEM_PROMPT_PATH = pf.SYSTEM_PROMPT_PATH

MIN_ANSWER_CHARS = 40
MAX_ANSWER_CHARS = 2800  # ~700 tokens, so prompt + answer fit max_seq_length=1024
SPLITS = (("train", 0.8), ("val", 0.1), ("test", 0.1))


@dataclass(frozen=True)
class Record:
    id: str
    question: str
    answer: str
    focus: str
    qtype: str
    source: str


# ---------------------------------------------------------------- parsing


def _text(el: ET.Element | None) -> str:
    return "".join(el.itertext()) if el is not None else ""


def parse_document(xml_bytes: bytes, collection: str) -> list[Record]:
    root = ET.fromstring(xml_bytes)
    focus = _text(root.find("Focus")).strip()
    records = []
    for pair in root.iter("QAPair"):
        q = pair.find("Question")
        records.append(
            Record(
                id=(q.get("qid") if q is not None else None)
                or f"{root.get('id')}_{pair.get('pid')}",
                question=_text(q),
                answer=_text(pair.find("Answer")),
                focus=focus,
                qtype=(q.get("qtype") if q is not None else "") or "unknown",
                source=collection,
            )
        )
    return records


def iter_xml(source: Path):
    """Yield (collection, xml_bytes) from a MedQuAD directory or zip archive."""
    if source.suffix == ".zip":
        with zipfile.ZipFile(source) as zf:
            for name in sorted(zf.namelist()):
                if name.endswith(".xml"):
                    yield Path(name).parent.name, zf.read(name)
    else:
        for path in sorted(source.rglob("*.xml")):
            yield path.parent.name, path.read_bytes()


def load_records(source: Path) -> list[Record]:
    return [r for collection, data in iter_xml(source) for r in parse_document(data, collection)]


# ---------------------------------------------------------------- cleaning


def normalize(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)  # stray markup
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" *\n[ \n]*", "\n", text)
    return text.strip()


def clean_question(q: str) -> str:
    q = normalize(q).replace("\n", " ")
    q = re.sub(r"\s+\?", "?", q)
    return q.replace("What is (are)", "What is").replace("What are (is)", "What are")


def truncate_answer(answer: str, limit: int = MAX_ANSWER_CHARS) -> str:
    if len(answer) <= limit:
        return answer
    cut = answer[:limit]
    end = max(cut.rfind(". "), cut.rfind(".\n"))
    return cut[: end + 1] if end > limit // 2 else cut.rsplit(" ", 1)[0] + " …"


def clean(records: list[Record]) -> tuple[list[Record], Counter]:
    """Normalize, drop empty/short answers (incl. subsets whose answers were removed), dedupe."""
    dropped: Counter = Counter()
    seen: set[tuple[str, str]] = set()
    out = []
    for r in records:
        question, answer = clean_question(r.question), normalize(r.answer)
        if not answer:
            dropped["empty_answer"] += 1
            continue
        if len(answer) < MIN_ANSWER_CHARS:
            dropped["short_answer"] += 1
            continue
        key = (question.lower(), answer.lower())
        if key in seen:
            dropped["duplicate"] += 1
            continue
        seen.add(key)
        out.append(
            Record(r.id, question, truncate_answer(answer), r.focus.strip(), r.qtype, r.source)
        )
    return out, dropped


# ---------------------------------------------------------------- template cleaning (v2)

RESOURCE_LIST = re.compile(r"^These resources address the diagnosis or management", re.I)
HPO_TABLE = re.compile(r"Human Phenotype Ontology provides the following list", re.I)
LEADING_QUESTION = re.compile(r"^[^.?!\n]{3,250}\?\s+")


def clean_templates(records: list[Record]) -> tuple[list[Record], Counter]:
    """Drop dataset boilerplate the v1 model learned to imitate; strip echoed questions."""
    counts: Counter = Counter()
    out = []
    for r in records:
        if RESOURCE_LIST.search(r.answer):
            counts["template_resource_list"] += 1
            continue
        if HPO_TABLE.search(r.answer):
            counts["template_hpo_table"] += 1
            continue
        stripped = LEADING_QUESTION.sub("", r.answer, count=1)
        if stripped != r.answer and len(stripped) >= MIN_ANSWER_CHARS:
            counts["template_echo_stripped"] += 1
            r = Record(r.id, r.question, stripped, r.focus, r.qtype, r.source)
        out.append(r)
    return out, counts


KEY_POINTS = re.compile(r"\AKey Points\s*\n[^\n]*\n+")


def strip_key_points(records: list[Record]) -> tuple[list[Record], Counter]:
    """v3: CancerGov answers open with a "Key Points" bullet summary whose points then return as
    section headings, so a model that copies the format repeats itself (the guard stopped 25/200
    v2 answers this way). Keep the body, drop the summary."""
    counts: Counter = Counter()
    out = []
    for r in records:
        body = KEY_POINTS.sub("", r.answer, count=1)
        if body != r.answer and len(body) >= MIN_ANSWER_CHARS:
            counts["template_key_points_stripped"] += 1
            r = Record(r.id, r.question, body, r.focus, r.qtype, r.source)
        out.append(r)
    return out, counts


# ---------------------------------------------------------------- splitting


def group_key(r: Record) -> str:
    """Focus topic; records without one are grouped by their source document instead."""
    return r.focus.lower() or f"__doc__{r.source}/{r.id.rsplit('_', 1)[0]}"


def group_split(records: list[Record], seed: int) -> dict[str, list[Record]]:
    """Assign whole focus groups to splits (≈80/10/10 by record count) so no focus leaks."""
    groups: dict[str, list[Record]] = {}
    for r in records:
        groups.setdefault(group_key(r), []).append(r)
    keys = sorted(groups)
    random.Random(seed).shuffle(keys)
    total = len(records)
    bounds = []
    acc = 0.0
    for _, frac in SPLITS:
        acc += frac
        bounds.append(acc * total)
    splits: dict[str, list[Record]] = {name: [] for name, _ in SPLITS}
    count = 0
    for key in keys:
        idx = next(i for i, b in enumerate(bounds) if count < b or i == len(bounds) - 1)
        splits[SPLITS[idx][0]].extend(groups[key])
        count += len(groups[key])
    return {name: sorted(rs, key=lambda r: r.id) for name, rs in splits.items()}


# ---------------------------------------------------------------- grounded rendering (v2, RAFT)

MODES = (("closed", 0.45), ("oracle", 0.40), ("distractor", 0.15))
MAX_EXCERPTS = 4  # the app retrieves top_k=4 chunks; never train on prompts it can't produce
MAX_GOLD_CHUNKS = 3
NOT_FOUND = (
    "I couldn't find information about this in your documents, so here is general information."
)


def _slug(text: str, limit: int = 40) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:limit] or "document"


def _filename(r: Record) -> str:
    source = re.sub(r"^\d+_|_QA.*$", "", r.source).lower()
    return f"{source}-{_slug(r.focus or r.id)}.pdf"


def _excerpts_for(r: Record, rng: random.Random) -> list[pf.Excerpt]:
    first_page = rng.randint(1, 3)
    return [
        pf.Excerpt(_filename(r), first_page + i, chunk)
        for i, chunk in enumerate(pf.chunk_text(r.answer))
    ]


@dataclass(frozen=True)
class Prompts:
    base: str
    rag: str
    no_context: str


def render_grounded(records: list[Record], prompts: Prompts, seed: int) -> list[dict]:
    """Render one split's records as closed-book / oracle / distractor-only chat examples.

    Distractors are drawn from other focus groups *of the same split*, so nothing leaks.
    """
    rng = random.Random(seed)
    by_group: dict[str, list[Record]] = {}
    for r in records:
        by_group.setdefault(group_key(r), []).append(r)
    groups = sorted(by_group)
    rows = []
    for r in records:
        mode = rng.choices([m for m, _ in MODES], [w for _, w in MODES])[0]
        if mode == "closed":
            system = pf.system_without_excerpts(prompts.base, prompts.no_context)
            rows.append(_row(r, system, r.answer, mode))
            continue
        others = [g for g in rng.sample(groups, min(len(groups), 6)) if g != group_key(r)]
        if mode == "oracle":
            gold = _excerpts_for(r, rng)[:MAX_GOLD_CHUNKS]
            n_distractors = max(1, MAX_EXCERPTS - len(gold))
            distractors = [
                _excerpts_for(rng.choice(by_group[g]), rng)[0] for g in others[:n_distractors]
            ]
            excerpts = gold + distractors
            rng.shuffle(excerpts)
            number = {id(e): n for n, e in enumerate(excerpts, start=1)}
            target = "\n\n".join(f"{e.text} [{number[id(e)]}]" for e in gold)
        else:
            k = rng.randint(2, 3)
            excerpts = [_excerpts_for(rng.choice(by_group[g]), rng)[0] for g in others[:k]]
            target = f"{NOT_FOUND}\n\n{r.answer}"
        system = pf.system_with_excerpts(prompts.base, prompts.rag, excerpts)
        rows.append(_row(r, system, target, mode))
    return rows


def synthetic_rows(
    count: int, seed: int, prompts: Prompts, split: str, version: int = 2
) -> list[dict]:
    import synthetic_records as sr

    examples = sr.generate_v3(count, seed) if version >= 3 else sr.generate(count, seed)
    rows = []
    for i, ex in enumerate(examples):
        system = pf.system_with_excerpts(prompts.base, prompts.rag, ex.excerpts)
        rows.append(
            {
                "id": f"syn-{split}-{i:05d}",
                "focus": f"synthetic:{ex.kind}",
                "qtype": ex.kind,
                "source": "synthetic_records",
                "mode": "synthetic",
                # the app's order: system (with excerpts), earlier turns, the new question
                "messages": [
                    {"role": "system", "content": system},
                    *getattr(ex, "history", []),
                    {"role": "user", "content": ex.question},
                    {"role": "assistant", "content": ex.answer},
                ],
            }
        )
    return rows


def _row(r: Record, system: str, target: str, mode: str) -> dict:
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": r.question},
            {"role": "assistant", "content": target},
        ],
        "mode": mode,
        **{k: v for k, v in asdict(r).items() if k not in ("question", "answer")},
    }


# ---------------------------------------------------------------- output


def to_chat(record: Record, system_prompt: str) -> dict:
    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": record.question},
            {"role": "assistant", "content": record.answer},
        ],
        **{k: v for k, v in asdict(record).items() if k not in ("question", "answer")},
    }


def write_outputs(
    splits: dict[str, list[Record]],
    rows: dict[str, list[dict]],
    dropped: Counter,
    raw_count: int,
    out_dir: Path,
    seed: int,
    extra_stats: dict | None = None,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, split_rows in rows.items():
        with open(out_dir / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for row in split_rows:
                f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    lengths = [len(r.answer) for rs in splits.values() for r in rs]
    stats = {
        "seed": seed,
        "medquad_commit": MEDQUAD_COMMIT,
        "raw_records": raw_count,
        "dropped": dict(sorted(dropped.items())),
        "kept_records": len(lengths),
        "splits": {n: len(rs) for n, rs in rows.items()},
        "focus_groups": {n: len({r.focus.lower() for r in rs}) for n, rs in splits.items()},
        "per_source": dict(sorted(Counter(r.source for rs in splits.values() for r in rs).items())),
        "per_qtype": dict(Counter(r.qtype for rs in splits.values() for r in rs).most_common()),
        "answer_chars": {
            "min": min(lengths),
            "median": int(statistics.median(lengths)),
            "p95": int(sorted(lengths)[int(0.95 * (len(lengths) - 1))]),
            "max": max(lengths),
            "truncated": sum(1 for x in lengths if x >= MAX_ANSWER_CHARS - 200),
        },
        **(extra_stats or {}),
    }
    (out_dir / "stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    return stats


def download(dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / f"MedQuAD-{MEDQUAD_COMMIT[:7]}.zip"
    if not target.exists():
        print(f"Downloading MedQuAD @ {MEDQUAD_COMMIT[:7]} ...")
        with urllib.request.urlopen(MEDQUAD_URL, timeout=120) as resp:  # noqa: S310 (pinned https)
            target.write_bytes(io.BytesIO(resp.read()).getvalue())
    return target


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--source", type=Path, help="MedQuAD directory or zip")
    parser.add_argument("--download", action="store_true", help="download pinned MedQuAD first")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "medquad")
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--system-prompt", type=Path, default=SYSTEM_PROMPT_PATH)
    v2 = parser.add_argument_group("v2 (grounded fine-tune)")
    v2.add_argument("--clean-templates", action="store_true", help="drop/strip dataset boilerplate")
    v2.add_argument(
        "--grounded", action="store_true", help="RAFT mix in the app's RAG prompt format"
    )
    v2.add_argument(
        "--synthetic-train", type=int, default=0, help="synthetic record examples (train)"
    )
    v2.add_argument("--synthetic-val", type=int, default=0, help="synthetic record examples (val)")
    v3 = parser.add_argument_group("v3 (multi-turn, app extraction format)")
    v3.add_argument(
        "--v3",
        action="store_true",
        help="strip MedQuAD Key Points summaries; v3 synthetic mix (multi-turn, no-range tests)",
    )
    args = parser.parse_args(argv)
    if not args.source and not args.download:
        parser.error("pass --source or --download")
    source = download(args.out / "raw") if args.download else args.source

    raw = load_records(source)
    records, dropped = clean(raw)
    if args.clean_templates:
        records, template_counts = clean_templates(records)
        dropped.update(template_counts)
    if args.v3:
        records, key_point_counts = strip_key_points(records)
        dropped.update(key_point_counts)
    splits = group_split(records, args.seed)
    system_prompt = args.system_prompt.read_text().strip()

    extra: dict = {}
    if args.grounded:
        prompts = Prompts(
            system_prompt,
            pf.read(pf.RAG_INSTRUCTIONS_PATH),
            pf.read(pf.NO_CONTEXT_INSTRUCTIONS_PATH),
        )
        no_context = pf.system_without_excerpts(prompts.base, prompts.no_context)
        rows = {
            "train": render_grounded(splits["train"], prompts, args.seed + 1)
            + synthetic_rows(
                args.synthetic_train, args.seed + 101, prompts, "train", 3 if args.v3 else 2
            ),
            "val": render_grounded(splits["val"], prompts, args.seed + 2)
            + synthetic_rows(
                args.synthetic_val, args.seed + 102, prompts, "val", 3 if args.v3 else 2
            ),
            # test stays closed-book so held-out QA metrics remain comparable across versions
            "test": [to_chat(r, no_context) for r in splits["test"]],
        }
        extra["modes"] = {
            n: dict(Counter(r.get("mode", "closed") for r in rs)) for n, rs in rows.items()
        }
    else:
        rows = {n: [to_chat(r, system_prompt) for r in rs] for n, rs in splits.items()}
    stats = write_outputs(splits, rows, dropped, len(raw), args.out, args.seed, extra)
    keys = ("raw_records", "dropped", "kept_records", "splits", "modes")
    print(json.dumps({k: stats[k] for k in keys if k in stats}, indent=2))
    return stats


if __name__ == "__main__":
    main()
