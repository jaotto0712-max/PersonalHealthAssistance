"""Training data and the app must build byte-identical prompts (add-grounded-finetune-v2)."""

import sys

from pha.chat.prompt import (
    NO_CONTEXT_INSTRUCTIONS,
    RAG_INSTRUCTIONS,
    build_prompt,
    format_excerpts,
    load_system_prompt,
)
from pha.config import REPO_ROOT, get_settings
from pha.rag.store import StoredHit

sys.path.insert(0, str(REPO_ROOT / "training"))
import prompt_format as pf  # noqa: E402

CHUNKS = [
    ("labs-2026-05-02.pdf", 2, "LDL cholesterol: 162 mg/dL (reference below 100 mg/dL) H"),
    ("medications.txt", 1, "- Atorvastatin 20 mg, once nightly (for high cholesterol)"),
]


def test_excerpt_formatting_is_identical():
    backend = format_excerpts(
        [StoredHit(t, "d", f, p, 0, 0.9 - i) for i, (f, p, t) in enumerate(CHUNKS)]
    )
    training = pf.format_excerpts([pf.Excerpt(f, p, t) for f, p, t in CHUNKS])
    assert backend == training


def test_full_system_prompts_are_identical():
    base = load_system_prompt(get_settings().system_prompt_path)
    assert base == pf.read(pf.SYSTEM_PROMPT_PATH)
    assert pf.read(pf.RAG_INSTRUCTIONS_PATH) == RAG_INSTRUCTIONS
    assert pf.read(pf.NO_CONTEXT_INSTRUCTIONS_PATH) == NO_CONTEXT_INSTRUCTIONS

    hits = [StoredHit(t, "d", f, p, 0, 0.9 - i) for i, (f, p, t) in enumerate(CHUNKS)]
    grounded = build_prompt(base, "q", [], hits, num_ctx=4096, num_predict=768).messages[0].content
    excerpts = [pf.Excerpt(f, p, t) for f, p, t in CHUNKS]
    assert grounded == pf.system_with_excerpts(base, RAG_INSTRUCTIONS, excerpts)

    closed = build_prompt(base, "q", [], [], num_ctx=4096, num_predict=768).messages[0].content
    assert closed == pf.system_without_excerpts(base, NO_CONTEXT_INSTRUCTIONS)
