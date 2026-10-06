"""End-to-end CPU smoke test of the training pipeline with a tiny random Phi-3.

Needs the training stack (transformers/peft/trl/datasets), which the backend env does not
install; run with a training env:  python -m pytest training/tests/test_lora_pipeline.py
"""

import json
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("trl")
pytest.importorskip("peft")

import torch  # noqa: E402
from transformers import AutoModelForCausalLM, Phi3Config  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lora_pipeline as lp  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
TOKENIZER_ID = "microsoft/Phi-3-mini-4k-instruct"


@pytest.fixture(scope="module")
def tiny_phi3(tmp_path_factory) -> Path:
    """Random 2-layer Phi-3 with the real tokenizer + chat template (needs HF hub once)."""
    os.environ.pop("HF_HUB_OFFLINE", None)
    out = tmp_path_factory.mktemp("tiny-phi3")
    tok = lp.load_tokenizer(TOKENIZER_ID)
    config = Phi3Config(
        vocab_size=len(tok), hidden_size=64, intermediate_size=128, num_hidden_layers=2,
        num_attention_heads=4, num_key_value_heads=4, max_position_embeddings=4096,
        pad_token_id=tok.pad_token_id, eos_token_id=tok.eos_token_id, bos_token_id=tok.bos_token_id,
    )  # fmt: skip
    torch.manual_seed(0)
    AutoModelForCausalLM.from_config(config).save_pretrained(out)
    lp.copy_base_tokenizer(TOKENIZER_ID, out)  # original files, incl. tokenizer.model
    return out


@pytest.fixture(scope="module")
def tiny_data(tmp_path_factory) -> Path:
    """First records of the real prepared splits if present, else synthetic ones."""
    out = tmp_path_factory.mktemp("data")
    real = REPO / "data" / "medquad"
    prompt = (REPO / "training" / "system_prompt.txt").read_text().strip()
    for split, n in (("train", 48), ("val", 16)):
        src = real / f"{split}.jsonl"
        if src.is_file():
            lines = src.read_text().splitlines()[:n]
        else:
            lines = [
                json.dumps({"messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"What is condition {i}?"},
                    {"role": "assistant", "content": f"Condition {i} is a disorder. " * 5},
                ]})
                for i in range(n)
            ]  # fmt: skip
        # one over-length example that must be dropped
        lines.append(json.dumps({"messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "long?"},
            {"role": "assistant", "content": "word " * 3000},
        ]}))  # fmt: skip
        (out / f"{split}.jsonl").write_text("\n".join(lines) + "\n")
    return out


def make_cfg(tiny_phi3, tiny_data, tmp_path, **kw) -> lp.TrainConfig:
    return lp.TrainConfig(
        base_model=str(tiny_phi3), data_dir=str(tiny_data), output_dir=str(tmp_path / "run"),
        max_length=1024, max_steps=4, eval_steps=2, save_steps=2, logging_steps=1,
        per_device_train_batch_size=2, gradient_accumulation_steps=1, per_device_eval_batch_size=4,
        gradient_checkpointing=False, **kw,
    )  # fmt: skip


def test_data_is_prompt_completion_and_drops_overlength(tiny_phi3, tiny_data, tmp_path):
    cfg = make_cfg(tiny_phi3, tiny_data, tmp_path)
    tok = lp.load_tokenizer(cfg.base_model)
    train_ds, val_ds, stats = lp.load_splits(cfg, tok)
    assert stats["train_dropped_too_long"] >= 1
    assert not any(len(ex["completion"][0]["content"]) > 10_000 for ex in train_ds)
    ex = train_ds[0]
    assert [m["role"] for m in ex["prompt"]] == ["system", "user"]
    assert [m["role"] for m in ex["completion"]] == ["assistant"]


def test_loss_is_masked_to_the_answer(tiny_phi3, tiny_data, tmp_path):
    cfg = make_cfg(tiny_phi3, tiny_data, tmp_path)
    tok = lp.load_tokenizer(cfg.base_model)
    train_ds, val_ds, _ = lp.load_splits(cfg, tok)
    trainer = lp.SFTTrainer(
        model=lp.load_base_model(cfg), args=lp.sft_config(cfg), train_dataset=train_ds,
        eval_dataset=val_ds, processing_class=tok, peft_config=lp.lora_config(cfg),
    )  # fmt: skip
    batch = trainer.data_collator([trainer.train_dataset[0]])
    ids, labels = batch["input_ids"][0], batch["labels"][0]
    untrained = tok.decode(ids[labels == -100])
    trained = tok.decode(ids[labels != -100])
    answer = train_ds[0]["completion"][0]["content"]
    question = train_ds[0]["prompt"][1]["content"]
    # system prompt + question (+ the <|assistant|> tag) are masked; only the answer is learned
    assert question in untrained and untrained.rstrip().endswith("<|assistant|>")
    assert trained.startswith(answer[:40])
    assert "<|end|>" in trained  # the model learns to stop
    assert "<|user|>" not in trained and "<|system|>" not in trained


def test_train_resume_compare_and_merge(tiny_phi3, tiny_data, tmp_path):
    cfg = make_cfg(tiny_phi3, tiny_data, tmp_path)
    report = lp.train(cfg)
    assert (cfg.adapter_dir / "adapter_config.json").is_file()
    saved = json.loads((cfg.adapter_dir / "training_config.json").read_text())
    assert saved["config"]["lora_r"] == 16
    assert saved["config"]["target_modules"] == list(lp.PHI3_LORA_TARGETS)
    assert saved["best_eval_loss"] is not None and saved["global_steps"] == 4
    assert report["data"]["train_dropped_too_long"] >= 1

    # resume: continuing to 6 steps starts from the step-4 checkpoint, not from 0
    cfg2 = make_cfg(tiny_phi3, tiny_data, tmp_path)
    cfg2.max_steps = 6
    report2 = lp.train(cfg2)
    assert report2["resumed_from"] and report2["resumed_from"].endswith("checkpoint-4")
    assert report2["global_steps"] == 6

    from peft import PeftModel

    tok = lp.load_tokenizer(str(cfg.adapter_dir))
    base = AutoModelForCausalLM.from_pretrained(cfg.base_model)
    peft_model = PeftModel.from_pretrained(base, str(cfg.adapter_dir))
    rows = lp.compare_answers(peft_model, tok, "SYS", ["What is asthma?"], max_new_tokens=5)
    assert set(rows[0]) == {"question", "base", "fine_tuned"}

    merged_dir = lp.merge_adapter(cfg.base_model, cfg.adapter_dir, tmp_path / "merged")
    merged = AutoModelForCausalLM.from_pretrained(merged_dir)
    assert not any("lora" in n for n, _ in merged.named_parameters())
    assert (merged_dir / "tokenizer.json").is_file()
    assert (merged_dir / "tokenizer.model").is_file()  # required by llama.cpp's converter
    assert lp.generate(merged, tok, "SYS", "hi", max_new_tokens=3) is not None


def test_trainer_builds_on_accelerate_hooked_model(tiny_phi3, tiny_data, tmp_path):
    """GPU loads use device_map="auto", which wraps model.forward in an accelerate hook
    (a functools.partial). Regression: trl's chunked_nll patch crashed on that."""
    from accelerate.hooks import ModelHook, add_hook_to_module

    cfg = make_cfg(tiny_phi3, tiny_data, tmp_path)
    tok = lp.load_tokenizer(cfg.base_model)
    train_ds, val_ds, _ = lp.load_splits(cfg, tok)
    model = lp.load_base_model(cfg)
    add_hook_to_module(model, ModelHook())
    assert type(model.forward).__name__ == "partial"
    trainer = lp.SFTTrainer(
        model=model, args=lp.sft_config(cfg), train_dataset=train_ds, eval_dataset=val_ds,
        processing_class=tok, peft_config=lp.lora_config(cfg),
    )  # fmt: skip
    trainer.train()
    assert trainer.state.global_step == cfg.max_steps


def test_data_parallel_two_processes(tiny_phi3, tiny_data, tmp_path):
    """Real 2-process DDP via torchrun (gloo on CPU; NCCL on GPUs). Same code path as 2× L4."""
    cfg = make_cfg(tiny_phi3, tiny_data, tmp_path)
    cfg.gradient_accumulation_steps = 2  # → 1 per process with 2 processes
    report = lp.train_multi_gpu(cfg, n_gpus=2)
    assert report["gpus"] == 2
    assert report["effective_batch_size"] == cfg.per_device_train_batch_size * 1 * 2
    assert report["global_steps"] == cfg.max_steps
    assert (cfg.adapter_dir / "adapter_config.json").is_file()
    run_config = json.loads((tmp_path / "run_run_config.json").read_text())
    assert run_config["base_model"] == cfg.base_model


def test_failed_workers_raise(tiny_phi3, tiny_data, tmp_path):
    cfg = make_cfg(tiny_phi3, tiny_data, tmp_path)
    cfg.base_model = str(tmp_path / "does-not-exist")
    with pytest.raises(RuntimeError, match="torchrun failed"):
        lp.train_multi_gpu(cfg, n_gpus=2)


def test_accumulation_keeps_effective_batch(monkeypatch):
    cfg = lp.TrainConfig(per_device_train_batch_size=4, gradient_accumulation_steps=4)
    assert lp.accumulation_steps(cfg) == 4
    monkeypatch.setenv("WORLD_SIZE", "2")
    assert lp.accumulation_steps(cfg) * 2 * 4 == 16


def test_save_steps_must_align_with_eval():
    with pytest.raises(ValueError):
        lp.sft_config(lp.TrainConfig(save_steps=3, eval_steps=2))
