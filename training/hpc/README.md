# Training on UF HiPerGator (Open OnDemand Jupyter, 1× L4)

This guide runs `training/train_lora.ipynb` on HiPerGator. In the commands, replace
`<group>` with your Slurm group/account and `<gatorlink>` with your GatorLink username.

> HiPerGator details change over time (GPU type names, form fields, module versions). Where this
> guide says *check*, confirm against the UF Research Computing docs: <https://help.rc.ufl.edu>.

## 0. Copy the training folder to /blue (from your laptop)

Only the repo's `training/` folder is needed. Copy it into your `pha` folder on `/blue`:

```bash
rsync -avP --exclude tests --exclude __pycache__ --exclude results \
      training <gatorlink>@hpg.rc.ufl.edu:/blue/<group>/<gatorlink>/pha/
```

Resulting layout (setup and training create the other folders):

```
/blue/<group>/<gatorlink>/pha/
├── training/            ← copied (notebook, pipeline, scripts)
├── venv/                ← Python env with CUDA torch (~6 GB)
├── hf-cache/            ← Phi-3 weights (~7.6 GB)
├── runs/                ← data splits, checkpoints, merged model, GGUFs (~15 GB)
└── llama.cpp-b11347/    ← pinned llama.cpp build for the GGUF export
```

## 1. One-time environment setup (about 10 minutes)

**Easiest: in Jupyter.** Open `pha/training/hpc/setup_env.ipynb` with the default *Python 3* kernel and run all
cells. Then reload the tab. The steps below do the same thing from a shell.


Open a shell on HiPerGator: `ssh <gatorlink>@hpg.rc.ufl.edu`, or Open OnDemand → *Clusters → HiPerGator Shell Access*. Package installs are better run in a short dev session than on a login node:

```bash
srundev --time=60 --mem=8gb          # check: UF's dev-session helper
bash /blue/<group>/<gatorlink>/pha/training/hpc/setup_env.sh
```

With no argument, everything goes into the `pha` folder that contains `training/`. The script also
registers a Jupyter kernel, **"PHA training"**, with those paths built in.

The script's last line should show a version like `torch 2.x | CUDA build 12.x`. If the CUDA build shows
`None`, you got a CPU wheel. Stop and check before training.

## 2. Start Jupyter with an L4

Open OnDemand (<https://ood.rc.ufl.edu>) → *Interactive Apps* → **Jupyter Notebook** (or JupyterLab):

| Field | Value |
|---|---|
| Account / QoS | your group (`<group>`; the burst QoS also works if available) |
| Partition | the GPU partition (check: usually `gpu`) |
| GPUs | `gpu:l4:2` (2× L4, data parallel, ~2× faster) or `gpu:l4:1`. Partition `hpg-turin` has L4s |
| CPUs | 4 |
| Memory | 48 GB (the merge step loads the full fp16 model in RAM) |
| Time | 4 h for the full run (1 h is plenty for the smoke test) |

## 3. Run the notebook

1. In Jupyter, open `/blue/<group>/<gatorlink>/pha/training/train_lora.ipynb`.
2. *Kernel → Change kernel → **PHA training***.
3. Run the first two cells. The second should print `GPU: NVIDIA L4, 22 GB, bf16=True` plus
   `WORK=…/pha/training` and `OUT=…/pha/runs`.
4. **Smoke test:** leave `SMOKE_TEST = True` and choose *Run → Run All Cells* (about 5–10 minutes). Check for:
   - a numeric `best_eval_loss`
   - the base vs fine-tuned answer table (answers will still be poor at 50 steps)
   - `phi3-medquad-Q4_K_M.gguf` in the final `ls`
5. **Full run:** set `SMOKE_TEST = False` and choose *Run All* again. That's about 820 optimizer steps (one epoch).
   Rough estimate on one L4: about 1–1.5 h for training, plus about 15 minutes for merge and export.
   - If the session ends, start a new one and *Run All*. Training resumes from the last checkpoint, saved every 200 steps.

**L4 notes**
- bf16 is detected automatically.
- With 24 GB you may set `load_in_4bit=False` (plain bf16 LoRA, no bitsandbytes). It is usually a little faster and slightly more accurate. QLoRA (`True`) is what the design specifies and what the smoke test covered.
- If you hit CUDA out-of-memory, set `per_device_train_batch_size=2, gradient_accumulation_steps=8`. The effective batch stays 16.

**If the GGUF export cell fails** (compiler too old or missing), run the export from a shell instead:

```bash
module load gcc            # check: `module spider gcc` for available versions
source /blue/<group>/<gatorlink>/pha/venv/bin/activate
export HF_HOME=/blue/<group>/<gatorlink>/pha/hf-cache LLAMA_CPP_DIR=/blue/<group>/<gatorlink>/pha/llama.cpp-b11347
P=/blue/<group>/<gatorlink>/pha
bash $P/training/export_gguf.sh $P/runs/outputs/phi3-medquad-merged phi3-medquad $P/runs/gguf
bash $P/training/export_gguf.sh microsoft/Phi-3-mini-4k-instruct phi3-base $P/runs/gguf
```

## 4. Bring the results home (on your laptop, from the repo root)

```bash
R=/blue/<group>/<gatorlink>/pha/runs
rsync -avP <gatorlink>@hpg.rc.ufl.edu:$R/gguf/'*.gguf' models/
mkdir -p training/results
rsync -avP <gatorlink>@hpg.rc.ufl.edu:$R/outputs/phi3-medquad/adapter/{training_config.json,qualitative_samples.json} training/results/
cd models && ollama create phi3-medquad -f Modelfile.medquad && ollama create phi3-base -f Modelfile.base
```

Then `make dev`. The header should read **Model ready · phi3-medquad**.
