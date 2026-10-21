"""Run the evaluation sets through the real chat pipeline.

    backend/.venv/bin/python -m eval.run_eval                       # everything (see `make eval`)
    backend/.venv/bin/python -m eval.run_eval --sets records --models phi3-medquad-v2 --limit 5

Results: eval/results/<set>__<model>__<rag>.jsonl (cached by pipeline fingerprint).
Report:  backend/.venv/bin/python -m eval.report
"""

import argparse
import asyncio
import json
import platform
import subprocess
from dataclasses import asdict
from pathlib import Path

from eval.pipeline import Harness, fingerprint, model_digests
from eval.scoring import leaked, rouge_l, score_record
from pha.chat.orchestrator import ChatOrchestrator
from pha.config import REPO_ROOT
from pha.llm.base import GenerationOptions
from pha.llm.fake import FakeLLM
from pha.safety.emergency import detect_emergency

SETS = REPO_ROOT / "eval" / "sets"
RESULTS = REPO_ROOT / "eval" / "results"
DEFAULT_MODELS = ["phi3-base", "phi3-medquad", "phi3-medquad-v2", "phi3-medquad-v3"]


def load(name: str) -> list[dict]:
    return [
        json.loads(line)
        for line in (SETS / f"{name}.jsonl").read_text().splitlines()
        if line.strip()
    ]


def results_path(set_name: str, model: str, rag: str) -> Path:
    return RESULTS / f"{set_name}__{model}__{rag}.jsonl"


def cached(path: Path, fp: str) -> dict[str, dict]:
    if not path.is_file():
        return {}
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return {r["id"]: r for r in rows if r.get("fingerprint") == fp}


def save(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in sorted(rows, key=lambda r: r["id"])))


async def run_records(
    h: Harness, model: str, rag: str, fp: str, items: list[dict], fresh: bool
) -> None:
    path = results_path("records", model, rag)
    done = {} if fresh else cached(path, fp)
    rows = list(done.values())
    for item in items:
        if item["id"] in done:
            continue
        docs = item["docs"] if rag == "on" else None
        outcome = await h.ask(h.orchestrator(model, docs), item["question"], item["history"])
        checks = score_record(item["expect"], outcome.answer, outcome.cited_files)
        rows.append({
            "id": item["id"], "category": item["category"], "question": item["question"],
            "expect": item["expect"], "checks": checks, "passed": all(checks.values()),
            "leaked": leaked(outcome.answer), "fingerprint": fp, **asdict(outcome),
        })  # fmt: skip
        print(
            f"  [{model} rag={rag}] {item['id']}: {'PASS' if rows[-1]['passed'] else 'fail'}",
            flush=True,
        )
        save(path, rows)


async def run_medquad(h: Harness, model: str, fp: str, items: list[dict], fresh: bool) -> None:
    path = results_path("medquad", model, "off")
    done = {} if fresh else cached(path, fp)
    rows = list(done.values())
    for n, item in enumerate(items, start=1):
        if item["id"] in done:
            continue
        outcome = await h.ask(h.orchestrator(model, None), item["question"], [])
        a, b = h.embedder.embed_documents([outcome.answer or " ", item["reference"]])
        similarity = sum(x * y for x, y in zip(a, b, strict=True))
        rows.append({
            "id": item["id"], "qtype": item["qtype"], "question": item["question"],
            "reference": item["reference"], "rouge_l": rouge_l(outcome.answer, item["reference"]),
            "similarity": similarity, "leaked": leaked(outcome.answer), "fingerprint": fp,
            **asdict(outcome),
        })  # fmt: skip
        if n % 10 == 0:
            print(f"  [{model}] medquad {n}/{len(items)}", flush=True)
            save(path, rows)
    save(path, rows)


async def run_safety(items: list[dict]) -> None:
    rows = []
    for i, item in enumerate(items):
        match = detect_emergency(item["text"])
        rows.append({"id": f"s{i:03d}", **item, "detected": match.category if match else None})
    # Emergencies must never reach the model: check through the real orchestrator with a fake LLM.
    llm = FakeLLM("should never be generated")
    options = GenerationOptions(num_ctx=4096, num_predict=64, temperature=0.0)
    orch = ChatOrchestrator(llm, None, "BASE", options)
    for item in [i for i in items if i["expected"]][:5]:
        [e async for e in orch.run(item["text"], [])]
    rows.append({"id": "short_circuit", "model_calls": len(llm.calls)})
    save(results_path("safety", "rules", "na"), rows)


def environment(digests: dict[str, str], models: list[str]) -> dict:
    try:
        ollama = subprocess.run(
            ["ollama", "--version"], capture_output=True, text=True
        ).stdout.strip()
    except OSError:
        ollama = "unknown"
    try:
        cpu = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True
        ).stdout.strip()
    except OSError:
        cpu = platform.processor()
    return {"machine": cpu or platform.machine(), "os": platform.platform(), "ollama": ollama,
            "models": {m: digests.get(m) for m in models}}  # fmt: skip


async def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--sets", nargs="+", default=["records", "medquad", "safety"])
    p.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    p.add_argument(
        "--rag", nargs="+", default=["on", "off"], help="records only; medquad is closed-book"
    )
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--fresh", action="store_true", help="ignore cached results")
    args = p.parse_args()

    if "safety" in args.sets:
        await run_safety(load("safety"))
        print("safety: done")
    model_sets = [s for s in args.sets if s != "safety"]
    if not model_sets:
        return
    digests = model_digests()
    missing = [m for m in args.models if m not in digests]
    if missing:
        raise SystemExit(f"Not installed in Ollama: {missing}. See README → Reproducing the model.")
    harness = Harness()
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "environment.json").write_text(
        json.dumps(environment(digests, args.models), indent=2)
    )
    # Fingerprint every model now: the code in memory is the code at startup, so a source edit
    # made while a long run is going must not label later results as the edited version.
    fingerprints = {m: fingerprint(digests[m]) for m in args.models}
    for model in args.models:
        fp = fingerprints[model]
        if "records" in model_sets:
            items = load("records")[: args.limit]
            for rag in args.rag:
                await run_records(harness, model, rag, fp, items, args.fresh)
        if "medquad" in model_sets:
            await run_medquad(harness, model, fp, load("medquad")[: args.limit], args.fresh)
    print("done. Build the report with: backend/.venv/bin/python -m eval.report")


if __name__ == "__main__":
    asyncio.run(main())
