---
title: Heretic Grimoire
emoji: ⚡
colorFrom: yellow
colorTo: red
sdk: gradio
sdk_version: 6.19.0
python_version: '3.13'
app_file: app.py
pinned: true
license: agpl-3.0
short_description: Archive for heretic generated models which are reproducible.
---

<p align="center">
  <a href="https://github.com/instax-dutta/heretic-grimoire">
    <img src="https://img.shields.io/badge/GitHub-Heretic%20Grimoire-181717?style=for-the-badge&logo=github">
  </a>
  <a href="https://huggingface.co/spaces/heretic-org/Heretic-Grimoire">
    <img src="https://img.shields.io/badge/%F0%9F%A4%97-Hugging%20Face-orange?style=for-the-badge">
  </a>
  <a href="https://github.com/p-e-w/heretic">
    <img src="https://img.shields.io/badge/GitHub-Heretic-181717?style=for-the-badge&logo=github">
  </a>
  <a href="https://discord.gg/gdXc48gSyT">
    <img src="https://img.shields.io/badge/Discord-Join-5865F2?style=for-the-badge&logo=discord&logoColor=white">
  </a>
</p>

<div align="center"><img src="assets/Heretic-Grimoire-Logo.png" alt="Heretic Grimoire Logo" width="25%" /></div>

Heretic Grimoire is an archiving system for [Heretic](https://github.com/p-e-w/heretic)-generated model reproducibility metadata. It collects, indexes, and lets you browse `reproduce.json` files f[...]

Each `reproduce.json` file is a tiny ~9 KB recipe that can reproduce an entire abliterated LLM **byte-for-byte**. The app provides a searchable table with filtering, CSV export, and an automatic t[...]

## Run Locally (Single Command)

### macOS / Linux

```bash
curl -sL https://github.com/instax-dutta/heretic-grimoire/raw/main/run.sh | bash
```

Or manually:

```bash
git clone https://github.com/instax-dutta/heretic-grimoire.git
cd heretic-grimoire
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

### Windows

```powershell
git clone https://github.com/instax-dutta/heretic-grimoire.git
cd heretic-grimoire
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:7860** in your browser.

## Why This Exists

Hugging Face no longer offers free Basic CPU Spaces. The original [Heretic Grimoire HF Space](https://huggingface.co/spaces/heretic-org/Heretic-Grimoire) (created before the policy change) still w[...]

This repo is a fully local, open-source version. It:

- Works entirely on your machine
- Auto-collects reproduce.json files twice daily
- Preserves archived records even if the original HF model is deleted
- Requires no HF account, no API keys, no cloud infrastructure

## Seed the Archive with Pre-Collected Data

The [heretic-org/Heretic-Grimoire-Storage](https://huggingface.co/heretic-org/Heretic-Grimoire-Storage) repository on Hugging Face holds a pre-collected archive of 135+ model reproduce.json files [...]

To download the pre-collected data bucket, use the Hugging Face CLI (note: Hugging Buckets don't use Git operations):

```bash
curl -LsSf https://hf.co/cli/install.sh | bash
hf sync hf://buckets/heretic-org/Heretic-Grimoire-Storage ./data
```

Then start the app. The app indexes all existing files in `data/huggingface.co/` on startup, so the pre-collected records will appear immediately.

To clone the app itself:

```bash
git clone <space/url/>
```

**Note:** The archive automatically scans Hugging Face for files — no manual submissions are needed.

## Features

- Browse all collected Heretic model reproducibility records
- Search by model name, base model, dataset, accelerator, etc.
- Filter by KL divergence and refusal count
- Sort by any column
- Download the full archive as CSV
- Auto-refreshes every 10 minutes
- Collector runs at 00:15 and 12:15 UTC daily
- Persistent local storage -- your archive survives restarts

## What Are reproduce.json Files?

In Heretic v1.3.0+, when a model is abliterated and uploaded to Hugging Face, the tool includes reproducibility metadata:

- `reproduce/requirements.txt` -- exact Python package versions
- `reproduce/config.toml` -- exact configuration including RNG seed
- `reproduce/checkpoint.jsonl` -- Optuna trial history
- `reproduce/SHA256SUMS` -- cryptographic weight hashes
- `reproduce/reproduce.json` -- all of the above in a single machine-readable ~9 KB file

To reproduce a model from a `reproduce.json`:

```bash
pip install -U heretic-llm
heretic --reproduce path/to/reproduce.json
```

## License

AGPL-3.0. See [LICENSE](LICENSE).

Based on the original [Heretic Grimoire](https://huggingface.co/spaces/heretic-org/Heretic-Grimoire) by Vinay Umrethe.
