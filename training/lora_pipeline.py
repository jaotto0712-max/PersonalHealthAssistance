"""QLoRA fine-tuning of Phi-3-mini on prepared MedQuAD splits (driven by train_lora.ipynb).

Kept as a plain module so the exact training code is unit-tested (tests/test_lora_pipeline.py
runs it end to end on CPU with a tiny Phi-3) before spending Colab GPU time.

Pinned stack (verified): transformers 5.18.0, peft 0.21.2, trl 1.14.1, accelerate 1.15.0,
datasets 5.0.1, bitsandbytes 0.50.2 (CUDA only).
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import torch
from datasets import Dataset, load_dataset
from peft import LoraConfig, PeftModel, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from transformers.trainer_utils import get_last_checkpoint
from trl import SFTConfig, SFTTrainer

PHI3_LORA_TARGETS = ("qkv_proj", "o_proj", "gate_up_proj", "down_proj")  # fused projections
# Original tokenizer files. llama.cpp's Phi-3 converter needs the SentencePiece tokenizer.model,
# which transformers' save_pretrained() no longer writes, so exports copy them from the base.
TOKENIZER_FILES = (
    "tokenizer.model",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "added_tokens.json",
)


@dataclass
class TrainConfig:
    base_model: str = "microsoft/Phi-3-mini-4k-instruct"
    data_dir: str = "data/medquad"
    output_dir: str = "outputs/phi3-medquad"
    seed: int = 13
    max_length: int = 1024  # examples longer than this are dropped, not truncated
    load_in_4bit: bool = True  # QLoRA (NF4); ignored when CUDA is unavailable
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    target_modules: list[str] = field(default_factory=lambda: list(PHI3_LORA_TARGETS))
    learning_rate: float = 2e-4
    lr_scheduler_type: str = "cosine"
    warmup: float = 0.03  # fraction of total steps
    num_train_epochs: float = 1.0
    per_device_train_batch_size: int = 4
    gradient_accumulation_steps: int = 4  # effective batch 16
    per_device_eval_batch_size: int = (
        4  # eval scores full batches: 8 × 1024 tokens nearly OOMs an L4
    )
    eval_steps: int = 200
    save_steps: int = 200  # must be a multiple of eval_steps (best-checkpoint tracking)
    save_total_limit: int = 3
    logging_steps: int = 20
    max_steps: int = -1  # > 0 overrides epochs (smoke test: 50)
    eval_subset: int | None = None  # cap validation size (smoke test)
    gradient_checkpointing: bool = True

    @property
    def adapter_dir(self) -> Path:
        return Path(self.output_dir) / "adapter"


# ---------------------------------------------------------------- data


def to_prompt_completion(example: dict[str, Any]) -> dict[str, Any]:
    """Conversational prompt/completion format: trl then trains on the completion only."""
    messages = example["messages"]
    return {"prompt": messages[:-1], "completion": messages[-1:]}


def token_length(tokenizer, messages: list[dict[str, str]]) -> int:
    text = tokenizer.apply_chat_template(messages, tokenize=False)
    return len(tokenizer(text, add_special_tokens=False)["input_ids"])


def load_splits(cfg: TrainConfig, tokenizer) -> tuple[Dataset, Dataset, dict[str, int]]:
    files = {s: str(Path(cfg.data_dir) / f"{s}.jsonl") for s in ("train", "val")}
    raw = load_dataset("json", data_files=files)
    stats: dict[str, int] = {}
    out = {}
    for split in ("train", "val"):
        ds = raw[split]
        before = len(ds)
        ds = ds.filter(lambda ex: token_length(tokenizer, ex["messages"]) <= cfg.max_length)
        if split == "val" and cfg.eval_subset:
            ds = ds.shuffle(seed=cfg.seed).select(range(min(cfg.eval_subset, len(ds))))
        stats[f"{split}_examples"] = len(ds)
        stats[f"{split}_dropped_too_long"] = before - len(ds) if split == "train" else 0
        out[split] = ds.map(to_prompt_completion, remove_columns=ds.column_names)
    return out["train"], out["val"], stats


# ---------------------------------------------------------------- model


def precision() -> dict[str, bool]:
    if not torch.cuda.is_available():
        return {"bf16": False, "fp16": False}
    bf16 = torch.cuda.is_bf16_supported()
    return {"bf16": bf16, "fp16": not bf16}  # T4 → fp16, A100/L4 → bf16


def use_4bit(cfg: TrainConfig) -> bool:
    return cfg.load_in_4bit and torch.cuda.is_available()


def load_tokenizer(name: str):
    tokenizer = AutoTokenizer.from_pretrained(name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer


def world_size() -> int:
    return int(os.environ.get("WORLD_SIZE", "1"))


def local_rank() -> int:
    return int(os.environ.get("LOCAL_RANK", "0"))


def gpu_device_map() -> dict[str, int]:
    """Whole model on this process's GPU. Multi-GPU is data parallel (one process and one full
    model copy per GPU, via torchrun). device_map="auto" would instead split layers across GPUs
    (naive model parallelism): only one GPU computes at a time, which is slower, not faster."""
    return {"": local_rank() if world_size() > 1 else torch.cuda.current_device()}


def load_base_model(cfg: TrainConfig):
    compute_dtype = torch.bfloat16 if precision()["bf16"] else torch.float16
    kwargs: dict[str, Any] = {}
    if use_4bit(cfg):
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=compute_dtype,
        )
        kwargs["device_map"] = gpu_device_map()
    elif torch.cuda.is_available():
        kwargs.update(dtype=compute_dtype, device_map=gpu_device_map())
    model = AutoModelForCausalLM.from_pretrained(cfg.base_model, **kwargs)
    model.config.use_cache = False  # incompatible with gradient checkpointing
    if use_4bit(cfg):
        model = prepare_model_for_kbit_training(
            model, use_gradient_checkpointing=cfg.gradient_checkpointing
        )
    return model


def lora_config(cfg: TrainConfig) -> LoraConfig:
    return LoraConfig(
        r=cfg.lora_r,
        lora_alpha=cfg.lora_alpha,
        lora_dropout=cfg.lora_dropout,
        target_modules=list(cfg.target_modules),
        bias="none",
        task_type="CAUSAL_LM",
    )


def accumulation_steps(cfg: TrainConfig) -> int:
    """Keep the effective batch (per-device × accumulation × GPUs) constant across GPU counts."""
    return max(1, cfg.gradient_accumulation_steps // world_size())


def sft_config(cfg: TrainConfig) -> SFTConfig:
    if cfg.save_steps % cfg.eval_steps:
        raise ValueError("save_steps must be a multiple of eval_steps")
    distributed: dict[str, Any] = {}
    if world_size() > 1:
        distributed["ddp_find_unused_parameters"] = False  # LoRA: every adapter gets gradients
    return SFTConfig(
        output_dir=cfg.output_dir,
        max_length=cfg.max_length,
        completion_only_loss=True,
        # Standard NLL. trl's default "chunked_nll" patches lm_head.forward and crashes when
        # accelerate has hooked the model (device_map="auto" on GPU): forward is a partial.
        loss_type="nll",
        packing=False,
        num_train_epochs=cfg.num_train_epochs,
        max_steps=cfg.max_steps,
        per_device_train_batch_size=cfg.per_device_train_batch_size,
        per_device_eval_batch_size=cfg.per_device_eval_batch_size,
        gradient_accumulation_steps=accumulation_steps(cfg),
        learning_rate=cfg.learning_rate,
        lr_scheduler_type=cfg.lr_scheduler_type,
        warmup_steps=cfg.warmup,
        logging_steps=cfg.logging_steps,
        eval_strategy="steps",
        eval_steps=cfg.eval_steps,
        save_strategy="steps",
        save_steps=cfg.save_steps,
        save_total_limit=cfg.save_total_limit,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        gradient_checkpointing=cfg.gradient_checkpointing,
        gradient_checkpointing_kwargs={"use_reentrant": False},  # required for DDP, fine for 1 GPU
        # Plain AdamW: LoRA trains ~25M params, so optimizer state is ~200 MB. bitsandbytes' paged
        # optimizer buys nothing here and its managed-memory prefetch failed under DDP on an L4
        # ("invalid argument ... pythonInterface.cpp:578", cudaMemPrefetchAsync).
        optim="adamw_torch",
        report_to="none",
        seed=cfg.seed,
        **precision(),
        **distributed,
    )


# ---------------------------------------------------------------- train


def train(cfg: TrainConfig, resume: bool = True) -> dict[str, Any]:
    """Train, keep the best checkpoint (lowest eval loss), save adapter + training_config.json."""
    args = sft_config(cfg)
    tokenizer = load_tokenizer(cfg.base_model)
    with args.main_process_first(desc="prepare data"):  # rank 0 builds the datasets cache first
        train_ds, val_ds, data_stats = load_splits(cfg, tokenizer)
    trainer = SFTTrainer(
        model=load_base_model(cfg),
        args=args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        processing_class=tokenizer,
        peft_config=lora_config(cfg),
    )
    last = get_last_checkpoint(cfg.output_dir) if resume and Path(cfg.output_dir).is_dir() else None
    if last:
        print(f"Resuming from {last}")
    result = trainer.train(resume_from_checkpoint=last)
    final_eval = trainer.evaluate()

    trainer.save_model(str(cfg.adapter_dir))  # best checkpoint; only rank 0 writes
    report = {
        "config": asdict(cfg),
        "data": data_stats,
        "best_checkpoint": trainer.state.best_model_checkpoint,
        "best_eval_loss": trainer.state.best_metric,
        "final_eval_loss": final_eval.get("eval_loss"),
        "train_loss": result.training_loss,
        "global_steps": trainer.state.global_step,
        "resumed_from": last,
        "gpus": world_size(),
        "effective_batch_size": cfg.per_device_train_batch_size
        * accumulation_steps(cfg)
        * world_size(),
        "versions": library_versions(),
    }
    if trainer.is_world_process_zero():
        tokenizer.save_pretrained(cfg.adapter_dir)
        (cfg.adapter_dir / "training_config.json").write_text(
            json.dumps(report, indent=2, default=str)
        )
    return report


def free_port() -> int:
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def train_multi_gpu(cfg: TrainConfig, n_gpus: int, resume: bool = True) -> dict[str, Any]:
    """Data-parallel training on n_gpus via torchrun (a notebook kernel can't host DDP itself).

    Streams the workers' output, raises if they fail, and returns rank 0's training report.
    """
    run_config = Path(cfg.output_dir).with_name(Path(cfg.output_dir).name + "_run_config.json")
    run_config.parent.mkdir(parents=True, exist_ok=True)
    run_config.write_text(json.dumps(asdict(cfg), indent=2))
    report_path = cfg.adapter_dir / "training_config.json"
    report_path.unlink(missing_ok=True)  # never read a stale report from an earlier run

    # Single node: a fixed loopback rendezvous. (--standalone's c10d rendezvous can hang on
    # reverse-DNS lookups, e.g. IPv6 on macOS; loopback + a free port works everywhere.)
    cmd = [
        sys.executable, "-m", "torch.distributed.run", "--nnodes=1",
        f"--nproc_per_node={n_gpus}", "--master-addr=127.0.0.1", f"--master-port={free_port()}",
        str(Path(__file__).with_name("train_cli.py")), "--config", str(run_config),
    ]  # fmt: skip
    if not resume:
        cmd.append("--no-resume")
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as proc:
        assert proc.stdout is not None
        try:
            for line in proc.stdout:
                print(line, end="", flush=True)
        except BaseException:  # notebook interrupt: stop the GPU workers too, don't orphan them
            proc.terminate()  # torchrun forwards SIGTERM to every worker
            try:
                proc.wait(timeout=60)
            except subprocess.TimeoutExpired:
                proc.kill()
            raise
    if proc.returncode != 0:
        raise RuntimeError(f"torchrun failed with exit code {proc.returncode} (see output above)")
    return json.loads(report_path.read_text())


def library_versions() -> dict[str, str]:
    import accelerate
    import datasets
    import peft
    import transformers
    import trl

    versions = {m.__name__: m.__version__ for m in (transformers, peft, trl, accelerate, datasets)}
    versions |= {"torch": torch.__version__, "python": platform.python_version()}
    if torch.cuda.is_available():
        versions["gpu"] = torch.cuda.get_device_name(0)
    return versions


# ---------------------------------------------------------------- inspect / export


@torch.no_grad()
def generate(model, tokenizer, system_prompt: str, question: str, max_new_tokens: int = 200) -> str:
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": question}]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt", add_special_tokens=False).to(model.device)
    output = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    return tokenizer.decode(output[0, inputs["input_ids"].shape[1] :], skip_special_tokens=True)


def compare_answers(model, tokenizer, system_prompt: str, questions: list[str], **kw) -> list[dict]:
    """Same questions with and without the LoRA adapter (model must be a PeftModel)."""
    model.eval()
    model.config.use_cache = True
    rows = []
    for q in questions:
        tuned = generate(model, tokenizer, system_prompt, q, **kw)
        with model.disable_adapter():
            base = generate(model, tokenizer, system_prompt, q, **kw)
        rows.append({"question": q, "base": base, "fine_tuned": tuned})
    return rows


def merge_adapter(base_model: str, adapter_dir: str | Path, out_dir: str | Path) -> Path:
    """Merge LoRA into a full-precision (fp16) base. Never merge into a 4-bit base."""
    out = Path(out_dir)
    kwargs: dict[str, Any] = {"dtype": torch.float16}
    if torch.cuda.is_available():
        kwargs["device_map"] = gpu_device_map()  # fp16 Phi-3 (~7.6 GB) fits one L4
    base = AutoModelForCausalLM.from_pretrained(base_model, **kwargs)
    merged = PeftModel.from_pretrained(base, str(adapter_dir)).merge_and_unload()
    merged.save_pretrained(out, safe_serialization=True)
    copy_base_tokenizer(base_model, out)
    return out


def copy_base_tokenizer(base_model: str, out_dir: str | Path) -> list[str]:
    """Copy the base model's original tokenizer files (training does not change them)."""
    src = Path(base_model)
    if not src.is_dir():
        from huggingface_hub import snapshot_download

        src = Path(snapshot_download(base_model, allow_patterns=list(TOKENIZER_FILES)))
    copied = []
    for name in TOKENIZER_FILES:
        if (src / name).is_file():
            shutil.copy2(src / name, Path(out_dir) / name)
            copied.append(name)
    if "tokenizer.model" not in copied:
        raise FileNotFoundError(f"{base_model} has no tokenizer.model; GGUF conversion needs it")
    return copied
