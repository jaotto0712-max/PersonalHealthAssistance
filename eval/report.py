# ruff: noqa: E501  (Markdown table/prose templates read better unbroken)
"""Build eval/report/REPORT.md from eval/results/*.jsonl.

backend/.venv/bin/python -m eval.report
"""

import json
import statistics
from collections import Counter, defaultdict
from datetime import date

from eval.scoring import score_record
from pha.config import REPO_ROOT

RESULTS = REPO_ROOT / "eval" / "results"
OUT = REPO_ROOT / "eval" / "report" / "REPORT.md"
CATEGORIES = ["value", "citation", "direction", "absent", "followup", "current_vs_previous",
              "same_name_ambiguity", "no_documents"]  # fmt: skip
MODEL_ORDER = ["phi3-base", "phi3-medquad", "phi3-medquad-v2"]
LABEL = {"phi3-base": "base", "phi3-medquad": "v1", "phi3-medquad-v2": "v2"}


def rows(set_name: str) -> dict[tuple[str, str], list[dict]]:
    out = {}
    for path in sorted(RESULTS.glob(f"{set_name}__*.jsonl")):
        _, model, rag = path.stem.split("__")
        out[(model, rag)] = [
            json.loads(line) for line in path.read_text().splitlines() if line.strip()
        ]
    return out


def rescored(results: dict[tuple[str, str], list[dict]]) -> dict[tuple[str, str], list[dict]]:
    """Re-apply the current scorer and expectations to the stored answers (no model calls)."""
    sets = REPO_ROOT / "eval" / "sets" / "records.jsonl"
    expect = {i["id"]: i["expect"] for i in map(json.loads, sets.read_text().splitlines())}
    for items in results.values():
        for r in items:
            r["expect"] = expect.get(r["id"], r["expect"])
            r["checks"] = score_record(r["expect"], r["answer"], r["cited_files"])
            r["passed"] = all(r["checks"].values())
    return results


def pct(n: int, d: int) -> str:
    return f"{n}/{d} ({100 * n / d:.0f}%)" if d else "–"


def median(values: list[float]) -> str:
    vals = [v for v in values if v is not None]
    return f"{statistics.median(vals):.2f}" if vals else "–"


def ordered(keys):
    return sorted(
        keys, key=lambda k: (MODEL_ORDER.index(k[0]) if k[0] in MODEL_ORDER else 99, k[1] != "on")
    )


def name(model: str) -> str:
    return f"`{model}` ({LABEL.get(model, '?')})"


def build() -> str:
    env = (
        json.loads((RESULTS / "environment.json").read_text())
        if (RESULTS / "environment.json").exists()
        else {}
    )
    records, medquad = rescored(rows("records")), rows("medquad")
    safety = next(iter(rows("safety").values()), [])
    md: list[str] = [
        "# Evaluation report: Personal Health Assistant",
        "",
        f"Generated {date.today().isoformat()} by `eval/report.py` from `eval/results/` "
        "(run: `make eval`). Every number comes from the real chat pipeline (retrieval, prompts, safety rules, "
        "degeneration guard) with local Ollama models. Small sets: differences of 1–2 items are within noise.",
        "",
    ]

    # ---------------------------------------------------------------- headline
    md += ["## Headline", "",
           "| Model | Records, with documents | Records, without documents | MedQuAD ROUGE-L | MedQuAD similarity |",
           "|---|---|---|---|---|"]  # fmt: skip
    for model in MODEL_ORDER:
        on, off = records.get((model, "on"), []), records.get((model, "off"), [])
        mq = medquad.get((model, "off"), [])
        if not (on or off or mq):
            continue
        md.append(
            f"| {name(model)} | {pct(sum(r['passed'] for r in on), len(on))} | "
            f"{pct(sum(r['passed'] for r in off), len(off))} | "
            f"{statistics.mean(r['rouge_l'] for r in mq):.3f} | {statistics.mean(r['similarity'] for r in mq):.3f} |"
            if mq else
            f"| {name(model)} | {pct(sum(r['passed'] for r in on), len(on))} | "
            f"{pct(sum(r['passed'] for r in off), len(off))} | – | – |"
        )  # fmt: skip
    md += ["", "*Records* = questions about the user's own (fictional) documents; *MedQuAD* = 200 held-out "
           "closed-book questions (topics unseen in training), scored against NIH reference answers by ROUGE-L "
           "(word overlap) and cosine similarity of bge embeddings (meaning).", ""]  # fmt: skip

    # ---------------------------------------------------------------- per category
    md += ["## Records by failure category (with documents)", "",
           "| Category | " + " | ".join(name(m) for m in MODEL_ORDER if (m, "on") in records) + " |",
           "|---|" + "---|" * sum((m, "on") in records for m in MODEL_ORDER)]  # fmt: skip
    for cat in CATEGORIES:
        cells = []
        for model in MODEL_ORDER:
            if (model, "on") not in records:
                continue
            items = [r for r in records[(model, "on")] if r["category"] == cat]
            cells.append(pct(sum(r["passed"] for r in items), len(items)))
        md.append(f"| `{cat}` | " + " | ".join(cells) + " |")
    md.append("")

    md += ["### Previous result reported as current", "",
           "Items with a known previous value (`not_values`): how often the first value stated was the old one.", "",
           "| Model | Previous-as-current |", "|---|---|"]  # fmt: skip
    for model, rag in ordered(k for k in records if k[1] == "on"):
        items = [r for r in records[(model, rag)] if "not_previous" in r["checks"]]
        bad = sum(not r["checks"]["not_previous"] for r in items)
        md.append(f"| {name(model)} | {pct(bad, len(items))} |")
    md.append("")

    # ---------------------------------------------------------------- output quality + latency
    md += ["## Output quality", "",
           "All answers from every run (records with and without documents, MedQuAD).", "",
           "| Model | Answers | Guard stops (reason) | Leaked template tokens | Median answer tokens |",
           "|---|---|---|---|---|"]  # fmt: skip
    for model in MODEL_ORDER:
        everything = [r for (m, _), rs in {**records, **medquad}.items() if m == model for r in rs]
        if not everything:
            continue
        reasons = Counter(r["stop_reason"] for r in everything if r.get("stopped_early"))
        stops = ", ".join(f"{k}: {v}" for k, v in reasons.items()) or "none"
        md.append(f"| {name(model)} | {len(everything)} | {sum(reasons.values())} ({stops}) | "
                  f"{sum(r['leaked'] for r in everything)} | "
                  f"{median([r.get('completion_tokens') for r in everything])} |")  # fmt: skip
    md += [
        "",
        "## Latency",
        "",
        "| Model | Time to first text (s), records | Tokens/s, MedQuAD |",
        "|---|---|---|",
    ]
    for model in MODEL_ORDER:
        rec = records.get((model, "on"), [])
        mq = medquad.get((model, "off"), [])
        if rec or mq:
            md.append(f"| {name(model)} | {median([r.get('ttft_s') for r in rec])} | "
                      f"{median([r.get('tokens_per_s') for r in mq])} |")  # fmt: skip
    md.append("")

    # ---------------------------------------------------------------- safety
    if safety:
        cases = [r for r in safety if "expected" in r]
        positives = [r for r in cases if r["expected"]]
        negatives = [r for r in cases if not r["expected"]]
        caught = [r for r in positives if r["detected"]]
        false_pos = [r for r in negatives if r["detected"]]
        recall = len(caught) / len(positives)
        md += ["## Safety (rule-based emergency detection; model-independent)", "",
               f"- **Recall:** {pct(len(caught), len(positives))}"
               + ("  ⚠ below the 95% target" if recall < 0.95 else ""),
               f"- **False alarms on hard negatives:** {pct(len(false_pos), len(negatives))}",
               f"- **Emergencies reaching the model:** {next((r['model_calls'] for r in safety if r['id'] == 'short_circuit'), '?')} calls (must be 0)",
               "", "| Category | Caught |", "|---|---|"]  # fmt: skip
        by_cat = defaultdict(list)
        for r in positives:
            by_cat[r["expected"]].append(r)
        for cat, rs in sorted(by_cat.items()):
            md.append(f"| {cat} | {pct(sum(bool(r['detected']) for r in rs), len(rs))} |")
        misses = [r["text"] for r in positives if not r["detected"]]
        if misses:
            md += ["", "Missed: " + "; ".join(f'"{t}"' for t in misses)]
        if false_pos:
            md += ["", "False alarms: " + "; ".join(f'"{r["text"]}"' for r in false_pos)]
        md.append("")

    # ---------------------------------------------------------------- examples
    md += ["## Failures with raw answers (with documents)", "",
           "Shown so scorer mistakes are visible. Up to 6 per model.", ""]  # fmt: skip
    for model, rag in ordered(k for k in records if k[1] == "on"):
        fails = [r for r in records[(model, rag)] if not r["passed"]][:6]
        md.append(
            f"### {name(model)}: {len([r for r in records[(model, rag)] if not r['passed']])} failures"
        )
        md.append("")
        for r in fails:
            failed = [k for k, v in r["checks"].items() if not v]
            answer = " ".join(r["answer"].split())[:280]
            md.append(
                f"- **{r['question']}** (`{r['category']}`, failed: {', '.join(failed)})  \n  > {answer}"
            )
        md.append("")

    # ---------------------------------------------------------------- environment
    md += ["## Environment", "", f"- Machine: {env.get('machine', '?')}; OS: {env.get('os', '?')}",
           f"- Ollama: {env.get('ollama', '?')}",
           "- Models (digest): " + ", ".join(f"`{m}` {d}" for m, d in env.get("models", {}).items()),
           "- Decoding: app defaults (temperature 0 with documents, 0.2 without; seed 0; 768 max tokens)", "",
           "## Limitations", "",
           f"- Small sets ({len((REPO_ROOT / 'eval' / 'sets' / 'records.jsonl').read_text().splitlines())} record questions, 200 MedQuAD, {len([r for r in safety if 'expected' in r])} safety); treat 1–2 item differences as noise.",
           "- Safety recall is optimistic: the first rules caught 30/34. The rules were then broadened, and 21 "
           "phrasings written while testing that fix were added to the set. New phrasings may still be missed.",
           "- Record documents are fictional fixtures; one real lab report was checked separately (10/11; "
           "see `openspec/changes/archive/2026-10-06-add-lab-table-extraction`).",
           "- Scorers are rules (unit-tested on real answers in `eval/tests`); ROUGE-L and embedding similarity "
           "reward resemblance to NIH answers, not clinical correctness.",
           "- Not a clinical validation. The assistant gives general information only."]  # fmt: skip
    return "\n".join(md) + "\n"


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build())
    print(f"wrote {OUT.relative_to(REPO_ROOT)}")
