# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026  Vinay Umrethe <umrethevinay@gmail.com>.

from __future__ import annotations

import csv
import html
import json
import math
import os
import re
import subprocess
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import gradio as gr
from dotenv import load_dotenv
from filelock import FileLock, Timeout
from gradio.utils import get_upload_folder
from huggingface_hub import HfApi
from huggingface_hub.utils import GatedRepoError

load_dotenv()


def get_icon(slug: str | None, local_path: Path | None = None) -> str:
    src = (
        f"/gradio_api/file={local_path.as_posix()}"
        if local_path is not None
        else f"https://cdn.simpleicons.org/{slug}/{SOCIAL_ICON_COLOR}"
    )
    return f'<img class="hx-icon" src="{src}" alt="" loading="lazy">'


APP_TITLE = "Heretic Grimoire"
CLI_TIMEOUT_SECONDS = 2 * 60 * 60
RUN_ON_STARTUP = True
AUTO_REFRESH_SECONDS = 600
SCHEDULE_HOURS_UTC = "0,12"
SCHEDULE_MINUTE_UTC = 15

REPO_SHA_RE = re.compile(r"^(?P<repo>.+)-(?P<sha>[0-9a-f]{7,40})\.json$", re.IGNORECASE)
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "assets" / "Heretic-Grimoire-Logo.png"

SOCIAL_ICON_COLOR = "f8fafc"

SOCIAL_LINKS = [
    {
        "label": "Homepage",
        "url": "https://heretic-project.org",
        "icon": get_icon(None, local_path=BASE_DIR / "assets" / "Heretic-Logo.png"),
    },
    {
        "label": "GitHub",
        "url": "https://github.com/p-e-w/heretic",
        "icon": get_icon("github"),
    },
    {
        "label": "Join Discord",
        "url": "https://discord.gg/gdXc48gSyT",
        "icon": get_icon("discord"),
    },
    {
        "label": "Matrix",
        "url": "https://matrix.to/#/#heretic:matrix.org",
        "icon": get_icon("matrix"),
    },
]

TABLE_HEADERS = [
    ("Heretic Model", "text"),
    ("Base Model", "text"),
    ("Created On", "date"),
    ("Version", "version"),
    ("KLD", "number"),
    ("Refusals", "number"),
    ("Base Refusals", "number"),
    ("Trials", "number"),
    ("Accelerator", "text"),
    ("JSON", "text"),
]

INDEX_CSV_FIELDS = [
    "index_last_updated",
    "index_count",
]

RECORD_CSV_FIELDS = [
    "source_repo",
    "source_repo_url",
    "reproduce_json_url",
    "source_commit_short",
    "base_model",
    "base_model_url",
    "base_model_commit",
    "timestamp",
    "reproduce_version",
    "heretic_version",
    "pytorch_version",
    "python_version",
    "os_platform",
    "accelerator",
    "kl_divergence",
    "refusals",
    "base_refusals",
    "n_bad_prompts",
    "direction_index",
    "row_normalization",
    "n_trials",
    "n_startup_trials",
    "seed",
    "good_prompts_dataset",
    "bad_prompts_dataset",
    "good_eval_dataset",
    "bad_eval_dataset",
    "local_path",
]

CUSTOM_CSS = """
:root {
  --hx-bg: #05070d;
  --hx-bg-2: #0b1020;
  --hx-line: rgba(148, 163, 184, 0.20);
  --hx-text: #f8fafc;
  --hx-muted: rgba(226, 232, 240, 0.72);
  --hx-faint: rgba(148, 163, 184, 0.68);
  --hx-gold: #f59e0b;
  --hx-orange-2: #fb923c;
  --hx-green: #22c55e;
  --hx-red: #ef4444;
  --hx-font: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --hx-mono: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
}

html, body, .gradio-container {
  min-height: 100%;
  background:
    radial-gradient(circle at 50% 0%, rgba(245, 158, 11, 0.18), transparent 34rem),
    radial-gradient(circle at 90% 10%, rgba(249, 115, 22, 0.12), transparent 28rem),
    linear-gradient(135deg, var(--hx-bg), var(--hx-bg-2) 54%, #09090b);
  color: var(--hx-text);
  font-family: var(--hx-font) !important;
}

.gradio-container,
.gradio-container .contain,
.gradio-container .wrap,
.gradio-container .main,
.gradio-container main,
.gradio-container .block {
  max-width: none !important;
  width: 100% !important;
  padding: 0 !important;
  margin: 0 !important;
  background: transparent !important;
  border: 0 !important;
  box-shadow: none !important;
  overflow: visible !important;
}

#app-shell-top {
  position: relative !important;
  z-index: 10 !important;
  overflow: visible !important;
}

.hx-app, .hx-hero {
  overflow: visible !important;
}

#bridge-search,
#bridge-max-kl,
#bridge-max-refusals,
#bridge-refresh,
#bridge-download,
#bridge-download-file {
  position: fixed !important;
  left: -10000px !important;
  top: auto !important;
  width: 1px !important;
  height: 1px !important;
  overflow: hidden !important;
  opacity: 0 !important;
  z-index: -1 !important;
  pointer-events: none !important;
}

#app-shell-top, #app-shell-top > div, #app-metrics, #app-metrics > div, #app-toolbar, #app-toolbar > div, #app-table, #app-table > div, #app-log, #app-log > div { width: 100% !important; max-width: none !important; margin: 0 !important; padding: 0 !important; }

a, a:visited,
.hx-table a, .hx-table a:visited,
.hx-project-link, .hx-project-link:visited,
.hx-sort {
  color: var(--hx-orange-2) !important;
}

a:hover, .hx-table a:hover, .hx-project-link:hover {
  color: var(--hx-gold) !important;
}

.hx-app {
  box-sizing: border-box;
  width: 100%;
  margin: 0;
  padding: clamp(.8rem, 2vw, 2rem) 0 0;
}

.hx-hero {
  width: 100%;
  box-sizing: border-box;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  align-items: center;
  gap: clamp(.9rem, 3vw, 2.6rem);
  text-align: center;
  padding: clamp(.8rem, 2.8vw, 2.4rem) clamp(.6rem, 2vw, 1.2rem) clamp(5.5rem, 10vw, 7rem);
}

.hx-brand,
.hx-projects { flex: 1 1 18rem; min-width: 0; }

.hx-logo-wrap { flex: 0 0 auto; }

.hx-brand {
  display: grid;
  justify-items: center;
  container-type: inline-size;
  width: 100%;
  max-width: 100%;
}
.hx-ascii {
  margin: 0;
  max-width: 100%;
  overflow: visible;
  color: var(--hx-gold);
  font-family: var(--hx-mono) !important;
  font-size: clamp(0.5rem, 5.8vw, 3.2rem);
  font-size: clamp(0.5rem, 6.2cqw, 3.2rem);
  font-weight: 900;
  line-height: 1;
  white-space: pre;
  letter-spacing: -0.08em;
  text-shadow:
    0 0 4px rgba(255, 247, 237, 0.20),
    0 0 8px rgba(245, 158, 11, 0.45),
    0 0 16px rgba(249, 115, 22, 0.25);
  filter: drop-shadow(0 0 6px rgba(249, 115, 22, 0.20));
}

.hx-title-copy {
  max-width: 50rem;
  margin: 1rem auto 0;
  color: var(--hx-muted);
  font-size: clamp(.95rem, 1.5vw, 1.22rem);
  line-height: 1.58;
}

.hx-kicker {
  width: 100%;
  margin: 0;
  color: var(--hx-faint);
  font-size: .76rem;
  font-weight: 850;
  letter-spacing: .15em;
  text-align: center;
  text-transform: uppercase;
}

.hx-projects {
  display: flex;
  flex-wrap: wrap;
  align-content: center;
  align-items: center;
  justify-content: center;
  gap: .55rem .6rem;
}

.hx-project-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: .55rem;
  min-height: 2.6rem;
  max-width: 22rem;
  padding: .7rem .95rem;
  border: 1px solid rgba(148, 163, 184, .28);
  border-radius: 999px;
  background: rgba(2, 6, 23, .28);
  text-decoration: none !important;
  font-weight: 850;
  box-shadow: 0 10px 26px rgba(0,0,0,.18), 0 0 26px rgba(249,115,22,.10);
  transition: transform .16s ease, border-color .16s ease, box-shadow .16s ease;
  white-space: nowrap;
}
.hx-project-link:hover { transform: translateY(-1px); border-color: rgba(245,158,11,.70); box-shadow: 0 16px 34px rgba(0,0,0,.26), 0 0 34px rgba(249,115,22,.18); text-decoration: none !important; }
.hx-icon { width: 1.08rem; height: 1.08rem; fill: currentColor; flex: 0 0 auto; }

.hx-logo-wrap {
  display: grid;
  place-items: center;
  width: clamp(14rem, 26vw, 24rem);
  aspect-ratio: 1 / 1;
  filter: drop-shadow(0 0 28px rgba(251, 146, 60, 0.62)) drop-shadow(0 0 78px rgba(249, 115, 22, 0.32));
  will-change: filter;
  transform: translate3d(0, 0, 0);
  overflow: visible !important;
}
.hx-logo {
  width: 100%;
  height: 100%;
  object-fit: contain;
}


.hx-toolbar {
  display: grid;
  grid-template-columns: minmax(min(100%, 22rem), 1fr) repeat(2, minmax(min(100%, 9rem), .22fr)) auto;
  gap: .7rem;
  align-items: end;
  padding: clamp(1rem, 2vw, 1.45rem) clamp(.35rem, 1vw, .9rem) .9rem;
  border-bottom: 1px solid var(--hx-line);
  background: rgba(2, 6, 23, .25);
}

.hx-field { display: grid; gap: .34rem; min-width: 0; }
.hx-field span { color: var(--hx-orange-2); font-size: .72rem; font-weight: 850; letter-spacing: .08em; text-transform: uppercase; }
.hx-input {
  width: 100%;
  min-height: 2.78rem;
  box-sizing: border-box;
  border: 1px solid rgba(148, 163, 184, .24);
  border-radius: 999px;
  padding: .72rem .92rem;
  color: var(--hx-text);
  background: rgba(2, 6, 23, .50);
  outline: none;
  font: 750 .94rem/1.2 var(--hx-font);
  transition: border-color .16s ease, box-shadow .16s ease, background .16s ease;
}
.hx-input::placeholder { color: rgba(148,163,184,.56); }
.hx-input:focus { border-color: rgba(249,115,22,.66); box-shadow: 0 0 0 4px rgba(249,115,22,.14); background: rgba(2, 6, 23, .72); }

.hx-actions { display: flex; flex-wrap: wrap; gap: .55rem; justify-content: flex-end; align-items: stretch; }
.hx-btn {
  appearance: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  min-height: 2.78rem;
  height: 2.78rem;
  border: 1px solid rgba(148, 163, 184, .28);
  border-radius: 999px;
  padding: .74rem 1rem;
  color: var(--hx-text) !important;
  background: rgba(15, 23, 42, .72);
  cursor: pointer;
  font: 850 .9rem/1 var(--hx-font);
  box-shadow: 0 12px 28px rgba(0,0,0,.22);
  transition: transform .16s ease, border-color .16s ease, background .16s ease, box-shadow .16s ease;
}
.hx-btn:hover { transform: translateY(-1px); border-color: rgba(245,158,11,.74); background: rgba(249,115,22,.12); box-shadow: 0 16px 34px rgba(0,0,0,.30), 0 0 24px rgba(249,115,22,.14); }

.hx-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: .7rem;
  padding: clamp(1rem, 2vw, 1.45rem) clamp(.35rem, 1vw, .9rem) .9rem;
}
.hx-card {
  flex: 1 1 12rem;
  padding: .95rem;
  border: 1px solid rgba(148,163,184,.20);
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(148,163,184,.09), rgba(148,163,184,.04));
}
.hx-card-label { color: var(--hx-orange-2); font-size: .72rem; font-weight: 850; letter-spacing: .08em; text-transform: uppercase; }
.hx-card-value { margin-top: .22rem; color: var(--hx-text); font-size: clamp(1.3rem, 2.4vw, 2rem); font-weight: 950; font-variant-numeric: tabular-nums; }
.hx-status-ok { color: var(--hx-green); font-weight: 950; }
.hx-status-bad { color: var(--hx-red); font-weight: 950; }
.hx-status-running { color: var(--hx-orange-2); font-weight: 950; }

.hx-storage {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: stretch;
  gap: .7rem;
  padding: clamp(.8rem, 1.8vw, 1.2rem) clamp(.35rem, 1vw, .9rem);
}
.hx-storage-card {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: .3rem;
  padding: .95rem 1.1rem;
  border: 1px solid rgba(148,163,184,.20);
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(245,158,11,.08), rgba(148,163,184,.03));
}
.hx-storage-label { color: var(--hx-orange-2); font-size: .72rem; font-weight: 850; letter-spacing: .08em; text-transform: uppercase; }
.hx-storage-value { color: var(--hx-text); font-size: clamp(1.15rem, 2vw, 1.6rem); font-weight: 950; font-variant-numeric: tabular-nums; }
.hx-storage-mid {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: .3rem .45rem;
  padding: .6rem .8rem;
  text-align: center;
}
.hx-storage-ratio { color: var(--hx-gold); font-size: clamp(.95rem, 1.5vw, 1.2rem); font-weight: 950; font-variant-numeric: tabular-nums; }
.hx-storage-mid-label {
  display: inline-flex;
  align-items: center;
  gap: .35rem;
  color: var(--hx-faint);
  font-size: .68rem;
  font-weight: 800;
  letter-spacing: .06em;
  text-transform: uppercase;
}
.hx-tip {
  position: relative;
  display: inline-flex;
  align-items: center;
  color: var(--hx-faint);
  cursor: help;
}
.hx-tip:hover, .hx-tip:focus { color: var(--hx-gold); }
.hx-tip::after {
  content: attr(data-tip);
  display: none;
  position: absolute;
  left: 50%;
  bottom: calc(100% + .5rem);
  transform: translateX(-50%);
  width: max-content;
  max-width: 18rem;
  padding: .55rem .7rem;
  border-radius: 10px;
  background: #0f172a;
  border: 1px solid rgba(245,158,11,.35);
  color: var(--hx-muted);
  font-size: .76rem;
  font-weight: 600;
  line-height: 1.4;
  text-transform: none;
  letter-spacing: normal;
  pointer-events: none;
  z-index: 20;
  box-shadow: 0 12px 28px rgba(0,0,0,.35);
}
.hx-tip:hover::after, .hx-tip:focus::after { display: block; }

@media (max-width: 600px) {
  .hx-storage {
    grid-template-columns: 1fr;
  }

  .hx-tip::after {
    left: auto;
    right: 0;
    transform: none;
    width: calc(100vw - 2rem);
    max-width: 16rem;
    white-space: normal;
  }
}

.hx-table-wrap {
  width: 100% !important;
  max-height: 650px !important;
  overflow: auto !important;
  display: block !important;
  scrollbar-width: thin;
  scrollbar-color: rgba(249, 115, 22, 0.42) rgba(15, 23, 42, 0.24);
  -webkit-overflow-scrolling: touch;
}
.hx-table { width: 100%; min-width: max(100%, 900px); border-collapse: separate; border-spacing: 0; color: var(--hx-text); font-size: clamp(.82rem, .9vw, .92rem); line-height: 1.36; border: none !important; }
.hx-table th { position: sticky; top: 0; z-index: 5; padding: .72rem .62rem; text-align: left; border: none !important; border-bottom: 1px solid rgba(249,115,22,.40) !important; background: #0f172a !important; box-shadow: 0 10px 20px rgba(0,0,0,.18); }
.hx-table td { padding: .64rem .62rem; vertical-align: top; border: none !important; border-bottom: 1px solid rgba(148,163,184,.06) !important; text-align: left !important; text-indent: 0 !important; }
.hx-table tbody tr:hover td { background: rgba(249,115,22,.06); }
.hx-sort { all: unset; cursor: pointer; display: inline-flex; align-items: center; gap: .4rem; font-weight: 900; white-space: nowrap; transition: color .2s ease; }
.hx-sort:hover { color: var(--hx-gold); }
.hx-sort::after { content: ""; display: inline-block; width: .8rem; height: .8rem; opacity: 0.6; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M5 6.5L8 3.5L11 6.5M5 9.5L8 12.5L11 9.5'/%3E%3C/svg%3E"); background-size: contain; background-repeat: no-repeat; background-position: center; transition: all .2s ease; }
.hx-sort:hover::after { opacity: 1; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='none' stroke='%23f59e0b' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M5 6.5L8 3.5L11 6.5M5 9.5L8 12.5L11 9.5'/%3E%3C/svg%3E"); }
.hx-sort[data-sort-dir="asc"]::after { opacity: 1; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='none' stroke='%23f59e0b' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 10l4-4 4 4'/%3E%3C/svg%3E"); }
.hx-sort[data-sort-dir="desc"]::after { opacity: 1; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='none' stroke='%23f59e0b' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 6l4 4 4-4'/%3E%3C/svg%3E"); }
.hx-table a { text-decoration: none !important; font-weight: 850; padding: 0 !important; margin: 0 !important; display: inline !important; word-break: break-all !important; }
.hx-table a:hover { text-decoration: underline !important; }
.hx-num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.hx-center, .hx-table th.hx-center { text-align: center; }
.hx-center .hx-num { text-align: center; }
.hx-center .hx-sort { justify-content: center; }
.hx-mono { font-family: var(--hx-mono) !important; font-size: .84rem; }
.hx-empty { margin: .85rem clamp(.35rem, 1vw, .9rem); padding: 1rem; border: 1px dashed rgba(249,115,22,.35); border-radius: 16px; color: var(--hx-muted); background: rgba(2, 6, 23, .22); }

.hx-log { margin: .85rem clamp(.35rem, 1vw, .9rem) .9rem; border: 1px solid rgba(148,163,184,.20); border-radius: 16px; background: rgba(2,6,23,.50); overflow: hidden; }
.hx-log-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: .55rem 1rem;
  padding: .82rem .95rem;
  border-bottom: 1px solid rgba(148,163,184,.15);
}
.hx-log-title { color: var(--hx-orange-2); font-size: .8rem; font-weight: 700; letter-spacing: .11em; text-transform: uppercase; }
.hx-log-status { color: var(--hx-muted); font-size: .86rem; font-weight: 400; line-height: 1.35; }
.hx-log-status .hx-status-ok, .hx-log-status .hx-status-bad, .hx-log-status .hx-status-running { font-weight: 400; }
.hx-log pre { min-height: 10rem; max-height: 17rem; overflow: auto; margin: 0; padding: .95rem; color: rgba(226,232,240,.86); font: 400 .84rem/1.55 var(--hx-mono); white-space: pre-wrap; }

@media (max-width: 760px) {
  .hx-toolbar { grid-template-columns: 1fr; }
  .hx-actions { justify-content: stretch; }
  .hx-btn { flex: 1 1 9rem; }
  .hx-project-link { max-width: 100%; }
  .hx-logo-wrap { width: clamp(12rem, 70vw, 20rem); }
}
"""

TABLE_SORT_JS = r"""
(() => {
  const getInput = (id) => document.querySelector(`#${id} textarea, #${id} input`);

  const setBridgeValue = (id, value) => {
    const input = getInput(id);
    if (!input) return false;
    const nativeSetter = Object.getOwnPropertyDescriptor(
      Object.getPrototypeOf(input),
      "value"
    )?.set;
    if (nativeSetter) nativeSetter.call(input, value);
    else input.value = value;
    input.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: null }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  };

  const clickBridge = (id) => {
    const button = document.querySelector(`#${id} button, #${id} a, #${id}`);
    if (button) button.click();
  };

  const debounce = (fn, wait = 180) => {
    let handle = null;
    return (...args) => {
      window.clearTimeout(handle);
      handle = window.setTimeout(() => fn(...args), wait);
    };
  };

  window.sortHereticTable = function sortHereticTable(columnIndex, type, button) {
    const table = button.closest("table");
    const tbody = table?.querySelector("tbody");
    if (!table || !tbody) return;
    const rows = Array.from(tbody.querySelectorAll("tr"));
    const nextDir = button.dataset.sortDir === "asc" ? "desc" : "asc";
    table.querySelectorAll(".hx-sort").forEach((item) => { item.dataset.sortDir = ""; });
    button.dataset.sortDir = nextDir;

    const parseValue = (row) => {
      const cell = row.children[columnIndex];
      const text = (cell?.innerText || "").trim();
      const sortValue = cell?.dataset?.sortValue;
      if (type === "number") {
        const source = sortValue || text;
        const match = source.match(/-?\d+(?:\.\d+)?/);
        return match ? Number(match[0]) : Number.POSITIVE_INFINITY;
      }
      if (type === "date") {
        const timestamp = Number(sortValue || 0);
        return Number.isFinite(timestamp) ? timestamp : 0;
      }
      if (type === "version") {
        if (!text || text === "\u2014") return [Number.NEGATIVE_INFINITY];
        return text.split(".").map((part) => Number(part.match(/^\d+/)?.[0] || 0));
      }
      return text.toLowerCase();
    };

    const compareValues = (left, right) => {
      if (Array.isArray(left) && Array.isArray(right)) {
        const length = Math.max(left.length, right.length);
        for (let index = 0; index < length; index += 1) {
          const leftPart = left[index] ?? 0;
          const rightPart = right[index] ?? 0;
          if (leftPart < rightPart) return -1;
          if (leftPart > rightPart) return 1;
        }
        return 0;
      }
      if (left < right) return -1;
      if (left > right) return 1;
      return 0;
    };

    rows.sort((left, right) => {
      const order = compareValues(parseValue(left), parseValue(right));
      return nextDir === "asc" ? order : -order;
    });
    rows.forEach((row) => tbody.appendChild(row));
  };

  const pushAllBridgeValues = () => {
    document.querySelectorAll("[data-bridge-input]").forEach((input) => {
      setBridgeValue(input.dataset.bridgeInput, input.value || "");
    });
  };

  const syncBridgeValues = debounce(pushAllBridgeValues, 200);

  const visibleInput = (id) => document.querySelector(`[data-bridge-input="${id}"]`);

  const sanitizeNumericInput = (input, allowDecimal) => {
    const original = input.value;
    const pattern = allowDecimal ? /[^0-9.]/g : /[^0-9]/g;
    let next = original.replace(pattern, "");
    if (allowDecimal) {
      const firstDot = next.indexOf(".");
      if (firstDot !== -1) {
        next = next.slice(0, firstDot + 1) + next.slice(firstDot + 1).split(".").join("");
      }
    }
    if (next === original) return;
    const caret = Math.max(0, (input.selectionStart ?? next.length) - (original.length - next.length));
    input.value = next;
    input.setSelectionRange(caret, caret);
  };

  const parseLimit = (value) => {
    if (!value) return null;
    const number = Number(value);
    return Number.isNaN(number) ? null : number;
  };

  const findMetricValue = (label) => {
    const card = Array.from(document.querySelectorAll(".hx-card")).find(
      (item) => item.querySelector(".hx-card-label")?.textContent.trim() === label
    );
    return card?.querySelector(".hx-card-value") || null;
  };

  const applyTableFilters = () => {
    const tableWrap = document.getElementById("app-table");
    const tbody = tableWrap?.querySelector(".hx-table tbody");
    if (!tableWrap || !tbody) return;

    const search = (visibleInput("bridge-search")?.value || "").trim().toLowerCase();
    const maxKl = parseLimit(visibleInput("bridge-max-kl")?.value);
    const maxRefusals = parseLimit(visibleInput("bridge-max-refusals")?.value);

    let visible = 0;
    tbody.querySelectorAll("tr").forEach((row) => {
      let show = true;
      if (search && !(row.dataset.search || "").includes(search)) show = false;
      if (show && maxKl !== null) {
        show = row.dataset.kl !== undefined && Number(row.dataset.kl) <= maxKl;
      }
      if (show && maxRefusals !== null) {
        show = row.dataset.refusals !== undefined && Number(row.dataset.refusals) <= maxRefusals;
      }
      row.style.display = show ? "" : "none";
      if (show) visible += 1;
    });

    const emptyMessage = tableWrap.querySelector("[data-filter-empty]");
    if (emptyMessage) emptyMessage.hidden = visible !== 0;

    const visibleValue = findMetricValue("Visible after filters");
    if (visibleValue) {
      const text = visible.toLocaleString();
      if (visibleValue.textContent !== text) visibleValue.textContent = text;
    }
  };

  const resetSortIndicators = () => {
    document.querySelectorAll(".hx-sort").forEach((button) => {
      button.removeAttribute("data-sort-dir");
    });
    const tbody = document.querySelector("#app-table .hx-table tbody");
    if (!tbody) return;
    const rows = Array.from(tbody.querySelectorAll("tr"));
    rows.sort((a, b) => Number(a.dataset.rowIndex) - Number(b.dataset.rowIndex));
    rows.forEach((row) => tbody.appendChild(row));
  };

  const observeTable = () => {
    const tableWrap = document.getElementById("app-table");
    if (!tableWrap || tableWrap.dataset.filterObserverBound === "true") return;
    tableWrap.dataset.filterObserverBound = "true";
    new MutationObserver(applyTableFilters).observe(tableWrap, {
      childList: true,
      subtree: true,
    });
  };

  const syncCustomInputs = () => {
    document.querySelectorAll("[data-bridge-input]").forEach((input) => {
      if (input.dataset.bound === "true") return;
      input.dataset.bound = "true";
      const onInput = () => {
        if (input.dataset.bridgeInput === "bridge-max-kl") sanitizeNumericInput(input, true);
        if (input.dataset.bridgeInput === "bridge-max-refusals") sanitizeNumericInput(input, false);
        applyTableFilters();
        syncBridgeValues();
      };
      input.addEventListener("input", onInput);
      input.addEventListener("change", onInput);
      input.addEventListener("keydown", (event) => {
        if (event.key === "Enter") event.preventDefault();
      });
    });

    document.querySelectorAll("[data-bridge-click]").forEach((button) => {
      if (button.dataset.bound === "true") return;
      button.dataset.bound = "true";
      button.addEventListener("click", () => {
        if (button.dataset.bridgeClick === "bridge-refresh") resetSortIndicators();
        pushAllBridgeValues();
        clickBridge(button.dataset.bridgeClick);
      });
    });

    observeTable();
  };

  syncCustomInputs();
  applyTableFilters();
  new MutationObserver(syncCustomInputs).observe(document.documentElement, {
    childList: true,
    subtree: true,
  });
})();
"""


@dataclass(frozen=True)
class AppPaths:
    data_root: Path
    data_dir: Path
    index_file: Path
    status_file: Path
    log_file: Path
    lock_file: Path
    size_file: Path

    @classmethod
    def from_env(cls) -> AppPaths:
        default_root = (
            Path("/data/heretic-reproducibles")
            if Path("/data").exists()
            else Path("data")
        )
        data_root = (
            Path(os.getenv("DATA_ROOT", str(default_root))).expanduser().resolve()
        )
        data_dir = (
            Path(os.getenv("DATA_DIR", str(data_root / "data"))).expanduser().resolve()
        )
        return cls(
            data_root=data_root,
            data_dir=data_dir,
            index_file=Path(os.getenv("INDEX_FILE", str(data_root / "index.json")))
            .expanduser()
            .resolve(),
            status_file=Path(os.getenv("STATUS_FILE", str(data_root / "status.json")))
            .expanduser()
            .resolve(),
            log_file=Path(os.getenv("LOG_FILE", str(data_root / "collector.log")))
            .expanduser()
            .resolve(),
            lock_file=Path(os.getenv("LOCK_FILE", str(data_root / ".collector.lock")))
            .expanduser()
            .resolve(),
            size_file=Path(os.getenv("SIZE_FILE", str(data_root / "size.json")))
            .expanduser()
            .resolve(),
        )

    def ensure(self) -> None:
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        for path in [
            self.index_file,
            self.status_file,
            self.log_file,
            self.lock_file,
            self.size_file,
        ]:
            path.parent.mkdir(parents=True, exist_ok=True)


PATHS = AppPaths.from_env()
PATHS.ensure()


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso_now() -> str:
    return utc_now().replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return default


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def clean_log_text(value: Any) -> str:
    text = ANSI_RE.sub("", str(value)).replace("\r", "")
    text = text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
    return " ".join(line.strip() for line in text.splitlines() if line.strip())


def append_log(message: str, **fields: Any) -> None:
    PATHS.ensure()
    suffix = ""
    if fields:
        compact = json.dumps(
            fields, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        suffix = " " + compact
    line = f"[{iso_now()}] {clean_log_text(message)}{suffix}\n"
    with PATHS.log_file.open("a", encoding="utf-8", errors="replace") as handle:
        handle.write(line)


def clear_log_file() -> None:
    PATHS.ensure()
    PATHS.log_file.write_text("", encoding="utf-8")


def read_log_tail(max_lines: int = 100) -> str:
    try:
        lines = PATHS.log_file.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()
        return "\n".join(lines[-max_lines:])
    except FileNotFoundError:
        return ""
    except OSError as exc:
        return f"Could not read log: {exc}"


def load_status() -> dict[str, Any]:
    base = {
        "state": "idle",
        "last_started_at": None,
        "last_finished_at": None,
        "last_ok": None,
        "last_error": None,
        "last_summary": {},
    }
    loaded = read_json(PATHS.status_file, {})
    if isinstance(loaded, dict):
        base.update(loaded)
    return base


def set_status(**updates: Any) -> dict[str, Any]:
    current = load_status()
    current.update(updates)
    write_json_atomic(PATHS.status_file, current)
    return current


def get_nested(data: Any, *keys: str, default: Any = None) -> Any:
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def round_float(value: Any, digits: int = 6) -> Any:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return round(float(value), digits)
    return value


_BYTE_UNITS = ("B", "KB", "MB", "GB", "TB", "PB")
_GB = 1024**3
_TB = 1024**4
_COMPACT = ((1_000_000_000, "Billion"), (1_000_000, "Million"), (1_000, "Thousand"))


def human_size(num_bytes: int) -> str:
    if num_bytes <= 0:
        return "0 B"
    v, i = float(num_bytes), 0
    while v >= 1024 and i < len(_BYTE_UNITS) - 1:
        v /= 1024
        i += 1
    return f"{v:,.2f} {_BYTE_UNITS[i]}"


def format_tb_with_gb(num_bytes: int) -> str:
    return f"{num_bytes / _TB:,.2f} TB ({num_bytes / _GB:,.2f} GB)"


def format_efficiency(numerator: int, denominator: int) -> str:
    if not denominator:
        return "\u2014"
    ratio = numerator / denominator
    for threshold, label in _COMPACT:
        if ratio >= threshold:
            return f"{ratio / threshold:,.2f} {label}"
    return f"{ratio:,.2f}"


def _size_key(repo_id: str, commit: str | None) -> str:
    return f"{repo_id}@{commit}" if commit else repo_id


def _fetch_root_bytes(api: HfApi, repo_id: str, commit: str | None) -> dict[str, Any]:
    try:
        items = api.list_repo_tree(
            repo_id=repo_id,
            revision=commit,
            recursive=False,
            repo_type="model",
        )
        return {
            "bytes": sum(
                item.size
                for item in items
                if hasattr(item, "size") and item.size is not None
            ),
            "status": "ok",
        }
    except GatedRepoError:
        return {"bytes": 0, "status": "gated"}
    except Exception:
        return {"bytes": 0, "status": "error"}


def update_size_cache(records: list[dict[str, Any]]) -> None:
    cache: dict[str, Any] = read_json(PATHS.size_file, {})
    if not isinstance(cache, dict):
        cache = {}
    to_fetch = {
        _size_key(r["base_model"], r.get("base_model_commit")): (
            r["base_model"],
            r.get("base_model_commit"),
        )
        for r in records
        if r.get("base_model")
        and cache.get(_size_key(r["base_model"], r.get("base_model_commit")), {}).get(
            "status"
        )
        != "ok"
    }
    if not to_fetch:
        return
    api = HfApi()
    for key, (repo_id, commit) in to_fetch.items():
        cache[key] = _fetch_root_bytes(api, repo_id, commit)
    write_json_atomic(PATHS.size_file, cache)
    append_log("size cache updated", fetched=len(to_fetch))


def total_base_bytes(records: list[dict[str, Any]]) -> int:
    cache: dict[str, Any] = read_json(PATHS.size_file, {})
    if not isinstance(cache, dict):
        return 0
    total = 0
    for r in records:
        if not r.get("base_model"):
            continue
        entry = cache.get(_size_key(r["base_model"], r.get("base_model_commit")))
        if isinstance(entry, dict) and isinstance(entry.get("bytes"), (int, float)):
            total += entry["bytes"]
    return total


def reproduce_bytes_total() -> int:
    return sum(p.stat().st_size for p in iter_data_json_files(PATHS.data_dir))


def format_accelerator(data: dict[str, Any]) -> str | None:
    accelerators = get_nested(data, "system", "accelerators", default={})
    if not isinstance(accelerators, dict):
        return None
    acc_type = accelerators.get("type")
    devices = accelerators.get("devices")
    if isinstance(devices, list) and devices:
        device_counts: dict[str, int] = {}
        device_order: list[str] = []
        for item in devices:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or "unknown"
            vram = item.get("vram_gb")
            dev_str = (
                f"{name} ({float(vram):.1f} GB)"
                if isinstance(vram, (int, float))
                else str(name)
            )
            if dev_str not in device_counts:
                device_counts[dev_str] = 0
                device_order.append(dev_str)
            device_counts[dev_str] += 1

        formatted_devices: list[str] = []
        for dev_str in device_order:
            count = device_counts[dev_str]
            if count > 1:
                formatted_devices.append(f"{count} x {dev_str}")
            else:
                formatted_devices.append(dev_str)

        if formatted_devices:
            return f"{acc_type or 'accelerator'}: " + ", ".join(formatted_devices)
    return str(acc_type) if acc_type else None


def iter_data_json_files(data_dir: Path) -> Iterable[Path]:
    official_root = data_dir / "huggingface.co"
    if not official_root.exists():
        return []
    return sorted(path for path in official_root.glob("*/*.json") if path.is_file())


def count_data_json_files(data_dir: Path) -> int:
    return sum(1 for _ in iter_data_json_files(data_dir))


def newest_data_mtime(data_dir: Path) -> float:
    mtimes = [path.stat().st_mtime for path in iter_data_json_files(data_dir)]
    return max(mtimes) if mtimes else 0.0


def infer_repo_and_commit(
    data_file: Path, data_dir: Path
) -> tuple[str | None, str | None, str]:
    local_path = data_file.as_posix()
    try:
        rel = data_file.relative_to(data_dir / "huggingface.co")
        if len(rel.parts) != 2:
            return None, None, local_path
        owner = rel.parts[0]
        filename = rel.parts[1]
        match = REPO_SHA_RE.match(filename)
        if not match:
            return f"{owner}/{data_file.stem}", None, local_path
        return f"{owner}/{match.group('repo')}", match.group("sha"), local_path
    except ValueError:
        return None, None, local_path


def normalize_record(data_file: Path, data_dir: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(data_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    repo_id, repo_commit_short, local_path = infer_repo_and_commit(data_file, data_dir)
    settings = (
        payload.get("settings") if isinstance(payload.get("settings"), dict) else {}
    )
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    params = (
        payload.get("parameters") if isinstance(payload.get("parameters"), dict) else {}
    )

    base_model = (
        settings.get("model") or payload.get("base_model") or payload.get("model")
    )
    source_url = f"https://huggingface.co/{repo_id}" if repo_id else None
    json_url = (
        f"{source_url}/blob/main/reproduce/reproduce.json" if source_url else None
    )
    base_model_url = (
        f"https://huggingface.co/{base_model}"
        if isinstance(base_model, str) and "/" in base_model
        else None
    )
    refusals = metrics.get("refusals")
    n_bad = metrics.get("n_bad_prompts")

    return {
        "source_repo": repo_id,
        "source_repo_url": source_url,
        "reproduce_json_url": json_url,
        "source_commit_short": repo_commit_short,
        "base_model": base_model,
        "base_model_url": base_model_url,
        "base_model_commit": settings.get("model_commit")
        or payload.get("base_model_commit"),
        "timestamp": payload.get("timestamp") or payload.get("created_at"),
        "reproduce_version": payload.get("version"),
        "heretic_version": get_nested(payload, "environment", "heretic", "version")
        or payload.get("heretic_version"),
        "pytorch_version": get_nested(payload, "environment", "pytorch_version"),
        "python_version": get_nested(payload, "system", "python", "version"),
        "os_platform": get_nested(payload, "system", "os", "platform"),
        "accelerator": format_accelerator(payload),
        "kl_divergence": round_float(metrics.get("kl_divergence") or metrics.get("kl")),
        "refusals": refusals,
        "base_refusals": metrics.get("base_refusals"),
        "n_bad_prompts": n_bad,
        "direction_index": round_float(params.get("direction_index")),
        "row_normalization": settings.get("row_normalization"),
        "n_trials": settings.get("n_trials"),
        "n_startup_trials": settings.get("n_startup_trials"),
        "seed": settings.get("seed"),
        "good_prompts_dataset": get_nested(settings, "good_prompts", "dataset"),
        "bad_prompts_dataset": get_nested(settings, "bad_prompts", "dataset"),
        "good_eval_dataset": get_nested(settings, "good_evaluation_prompts", "dataset"),
        "bad_eval_dataset": get_nested(settings, "bad_evaluation_prompts", "dataset"),
        "local_path": local_path,
    }


def build_index() -> dict[str, Any]:
    PATHS.ensure()
    scanned_records: list[dict[str, Any]] = []
    for data_file in iter_data_json_files(PATHS.data_dir):
        record = normalize_record(data_file, PATHS.data_dir)
        if record is not None:
            scanned_records.append(record)

    scanned_records.sort(
        key=lambda item: str(item.get("timestamp") or ""),
        reverse=True,
    )

    payload = {
        "last_updated": iso_now(),
        "count": len(scanned_records),
        "records": scanned_records,
    }
    write_json_atomic(PATHS.index_file, payload)
    append_log(
        "index rebuilt",
        scanned=len(scanned_records),
    )
    return payload


def index_is_stale(index: dict[str, Any]) -> bool:
    if not PATHS.index_file.exists():
        return True
    data_count = count_data_json_files(PATHS.data_dir)
    if not isinstance(index.get("records"), list):
        return True
    if index.get("count", 0) != data_count:
        return True
    return newest_data_mtime(PATHS.data_dir) > PATHS.index_file.stat().st_mtime


def load_index() -> dict[str, Any]:
    index = read_json(PATHS.index_file, {})
    if load_status().get("state") == "running":
        return index
    if not isinstance(index, dict) or index_is_stale(index):
        return build_index()
    return index


def parse_cli_summary(output: str) -> dict[str, int | None]:
    summary: dict[str, int | None] = {
        "found": None,
        "downloaded": None,
        "already_stored": None,
    }
    patterns = {
        "found": r"Found:\s*(\d+)",
        "downloaded": r"Downloaded:\s*(\d+)",
        "already_stored": r"Already stored:\s*(\d+)",
    }
    cleaned = clean_log_text(output)
    for key, pattern in patterns.items():
        match = re.search(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            summary[key] = int(match.group(1))
    return summary


def run_heretic_collect() -> dict[str, Any]:
    cmd = [
        os.getenv("HERETIC_BIN", "heretic"),
        "--collect-reproducibles",
        str(PATHS.data_dir),
    ]
    started = time.perf_counter()
    env = {
        **os.environ,
        "PYTHONUNBUFFERED": "1",
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "NO_COLOR": "1",
        "TERM": "dumb",
    }
    completed = subprocess.run(
        cmd,
        cwd=str(PATHS.data_root),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=CLI_TIMEOUT_SECONDS,
        env=env,
        check=False,
    )
    elapsed = round(time.perf_counter() - started, 3)
    output = completed.stdout or ""
    if completed.returncode != 0:
        tail = re.sub(r"[╭╮╰╯│─━═┌┐└┘├┤┬┴┼]+", " ", clean_log_text(output))
        tail = re.sub(r"\s+", " ", tail).strip()[-900:]
        append_log("cli collection failed", code=completed.returncode, output_tail=tail)
        raise RuntimeError(f"Heretic CLI failed with exit code {completed.returncode}")
    summary = parse_cli_summary(output)
    return {"method": "heretic_cli", "elapsed_seconds": elapsed, **summary}


def collect_and_index() -> dict[str, Any]:
    PATHS.ensure()
    lock = FileLock(str(PATHS.lock_file), timeout=2)
    try:
        with lock:
            clear_log_file()
            set_status(
                state="running",
                last_started_at=iso_now(),
                last_finished_at=None,
                last_ok=None,
                last_error=None,
            )
            append_log("collection started")
            try:
                result = run_heretic_collect()
                index = build_index()
                update_size_cache(records_from_index(index))
                summary = {
                    **result,
                    "index_last_updated": index.get("last_updated"),
                }
                set_status(
                    state="idle",
                    last_finished_at=iso_now(),
                    last_ok=True,
                    last_summary=summary,
                    last_error=None,
                )
                append_log(
                    "collection completed",
                    already_stored=result.get("already_stored"),
                    downloaded=result.get("downloaded"),
                    found=result.get("found"),
                    seconds=result.get("elapsed_seconds"),
                )
                return summary
            except Exception as exc:
                error = clean_log_text(exc)
                set_status(
                    state="idle",
                    last_finished_at=iso_now(),
                    last_ok=False,
                    last_error=error,
                )
                append_log("collection failed", error=error)
                raise
    except Timeout:
        append_log("collection skipped; another run is active")
        return {
            "method": "locked",
            "message": "Another collection is already running.",
            "status": load_status(),
        }


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def datetime_sort_value(value: str | None) -> str:
    dt = parse_iso_datetime(value)
    return str(dt.timestamp()) if dt else "0"


def to_display_time(value: str | None) -> str:
    dt = parse_iso_datetime(value)
    if dt is None:
        return "\u2014" if not value else str(value)
    return dt.strftime("%Y-%m-%d %I:%M %p")


def html_text(value: Any) -> str:
    if value is None or value == "":
        return "\u2014"
    return html.escape(str(value), quote=True)


def html_link(label: Any, url: Any) -> str:
    if label is None or label == "":
        return "\u2014"
    safe_label = html.escape(str(label), quote=True)
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        safe_url = html.escape(url, quote=True)
        return f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer">{safe_label}</a>'
    return safe_label


def format_number(value: Any, digits: int | None = None) -> str:
    if value is None or value == "":
        return "\u2014"
    if isinstance(value, bool):
        return str(value)
    try:
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return "\u2014"
        if digits is not None:
            return f"{number:.{digits}f}".rstrip("0").rstrip(".")
        if number.is_integer():
            return str(int(number))
        return f"{number:.6f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError, OverflowError):
        return html_text(value)


def parse_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return None
        return number
    except (TypeError, ValueError, OverflowError):
        return None


def records_from_index(index: dict[str, Any]) -> list[dict[str, Any]]:
    records = index.get("records", [])
    return records if isinstance(records, list) else []


def format_csv_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def write_archive_csv() -> str:
    index = load_index()
    records = records_from_index(index)
    extra_fields = sorted(
        {key for record in records for key in record if key not in RECORD_CSV_FIELDS}
    )
    fieldnames = [
        *INDEX_CSV_FIELDS,
        *RECORD_CSV_FIELDS,
        *extra_fields,
        "record_json",
    ]
    metadata = {
        "index_last_updated": index.get("last_updated"),
        "index_count": index.get("count"),
    }
    rows = records or [{}]
    timestamp = utc_now().strftime("%Y%m%d_%H%M%S")
    csv_path = (
        Path(get_upload_folder()) / f"heretic_reproducibles_archive_{timestamp}.csv"
    )
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = csv_path.with_suffix(csv_path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for record in rows:
            record = record if isinstance(record, dict) else {}
            row = {key: format_csv_cell(value) for key, value in metadata.items()}
            row.update(
                {key: format_csv_cell(record.get(key)) for key in RECORD_CSV_FIELDS}
            )
            row.update({key: format_csv_cell(record.get(key)) for key in extra_fields})
            row["record_json"] = format_csv_cell(record)
            writer.writerow(row)
    tmp.replace(csv_path)
    append_log("archive csv written", path=str(csv_path), records=len(records))
    return str(csv_path)


def prepare_archive_csv_download() -> dict[str, Any]:
    path = write_archive_csv()
    return gr.update(value=path, visible=True)


def format_ratio(numerator: Any, denominator: Any) -> str:
    if numerator is None or numerator == "":
        return "\u2014"
    if denominator is None or denominator == "":
        return format_number(numerator)
    return f"{format_number(numerator)}/{format_number(denominator)}"


def sort_records_by_timestamp(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        records, key=lambda item: str(item.get("timestamp") or ""), reverse=True
    )


SEARCH_FIELDS = [
    "source_repo",
    "base_model",
    "heretic_version",
    "accelerator",
    "row_normalization",
    "good_prompts_dataset",
    "bad_prompts_dataset",
    "good_eval_dataset",
    "bad_eval_dataset",
    "pytorch_version",
    "python_version",
    "os_platform",
]


def record_search_text(record: dict[str, Any]) -> str:
    return " ".join(str(record.get(key, "")) for key in SEARCH_FIELDS).lower()


def filter_records(
    records: list[dict[str, Any]],
    search: str,
    max_kl: Any,
    max_refusals: Any,
) -> list[dict[str, Any]]:
    query = (search or "").strip().lower()
    kl_limit = parse_optional_float(max_kl)
    refusal_limit = parse_optional_float(max_refusals)
    filtered = records

    if query:
        filtered = [
            record for record in filtered if query in record_search_text(record)
        ]

    if kl_limit is not None:
        filtered = [
            record
            for record in filtered
            if (kl_val := parse_optional_float(record.get("kl_divergence"))) is not None
            and kl_val <= kl_limit
        ]

    if refusal_limit is not None:
        filtered = [
            record
            for record in filtered
            if (ref_val := parse_optional_float(record.get("refusals"))) is not None
            and ref_val <= refusal_limit
        ]

    return sort_records_by_timestamp(filtered)


def render_records_table_html(records: list[dict[str, Any]]) -> str:
    if not records:
        return '<div class="hx-empty">No records visible. Clear filters or press <b>Refresh</b>.</div>'

    center_columns = {3, 4, 5, 6, 7}
    head_parts: list[str] = []
    for index, (column, sort_type) in enumerate(TABLE_HEADERS):
        class_attr = ' class="hx-center"' if index in center_columns else ""
        head_parts.append(
            f"<th{class_attr}>"
            f'<button class="hx-sort" type="button" onclick="sortHereticTable({index}, \'{html.escape(sort_type)}\', this)">'
            f"{html.escape(column)}</button>"
            "</th>"
        )
    head = "".join(head_parts)

    body_rows: list[str] = []
    for record in records:
        n_bad = record.get("n_bad_prompts")
        created_sort = html.escape(
            datetime_sort_value(record.get("timestamp")), quote=True
        )
        kl_value = parse_optional_float(record.get("kl_divergence"))
        refusals_value = parse_optional_float(record.get("refusals"))
        row_index = len(body_rows)
        row_attrs = f' data-row-index="{row_index}" data-search="{html.escape(record_search_text(record), quote=True)}"'
        if kl_value is not None:
            row_attrs += f' data-kl="{kl_value}"'
        if refusals_value is not None:
            row_attrs += f' data-refusals="{refusals_value}"'
        row_cells = [
            (html_link(record.get("source_repo"), record.get("source_repo_url")), ""),
            (html_link(record.get("base_model"), record.get("base_model_url")), ""),
            (
                html_text(to_display_time(record.get("timestamp"))),
                f' data-sort-value="{created_sort}"',
            ),
            (html_text(record.get("heretic_version")), ' class="hx-center"'),
            (
                f'<div class="hx-num">{format_number(record.get("kl_divergence"), 6)}</div>',
                ' class="hx-center"',
            ),
            (
                f'<div class="hx-num">{format_ratio(record.get("refusals"), n_bad)}</div>',
                ' class="hx-center"',
            ),
            (
                f'<div class="hx-num">{format_ratio(record.get("base_refusals"), n_bad)}</div>',
                ' class="hx-center"',
            ),
            (
                f'<div class="hx-num">{format_number(record.get("n_trials"))}</div>',
                ' class="hx-center"',
            ),
            (f'<div class="hx-mono">{html_text(record.get("accelerator"))}</div>', ""),
            (html_link("open", record.get("reproduce_json_url")), ""),
        ]
        body_rows.append(
            f"<tr{row_attrs}>"
            + "".join(f"<td{attrs}>{cell}</td>" for cell, attrs in row_cells)
            + "</tr>"
        )
    return (
        '<div class="hx-table-wrap">'
        '<table class="hx-table">'
        f"<thead><tr>{head}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table></div>"
        '<div class="hx-empty" data-filter-empty hidden>No records match the current filters.</div>'
    )


def render_collector_status_html(
    index: dict[str, Any], records: list[dict[str, Any]]
) -> str:
    st = load_status()
    last_ok = st.get("last_ok")
    if st.get("state") == "running":
        status_html = '<span class="hx-status-running">running</span>'
    elif last_ok is True:
        status_html = '<span class="hx-status-ok">ok</span>'
    elif last_ok is False:
        status_html = '<span class="hx-status-bad">failed</span>'
    else:
        status_html = "idle"

    unique_repos = len({r.get("source_repo") for r in records if r.get("source_repo")})
    last_updated = to_display_time(
        st.get("last_finished_at")
        or st.get("last_started_at")
        or index.get("last_updated")
    )
    return (
        f"Collector status: {status_html} · Unique repositories: {unique_repos:,} · "
        f"Last updated: {last_updated}"
    )


def render_metric_cards_html(
    records: list[dict[str, Any]],
    filtered_count: int | None = None,
) -> str:
    visible = filtered_count if filtered_count is not None else len(records)
    unique_base = len({r.get("base_model") for r in records if r.get("base_model")})
    cards = [
        ("Indexed records", f"{len(records):,}"),
        ("Visible after filters", f"{visible:,}"),
        ("Unique base models", f"{unique_base:,}"),
    ]
    card_html = "".join(
        f'<article class="hx-card"><div class="hx-card-label">{html.escape(label)}</div><div class="hx-card-value">{html.escape(value)}</div></article>'
        for label, value in cards
    )
    return (
        f'<section class="hx-metrics" aria-label="Index metrics">{card_html}</section>'
    )


def render_header_html() -> str:
    logo_src = html.escape(
        os.getenv("LOGO_SRC", f"/gradio_api/file={LOGO_PATH.as_posix()}"), quote=True
    )
    logo_html = (
        f'<div class="hx-logo-wrap"><img class="hx-logo" src="{logo_src}" alt="Heretic logo"></div>'
        if LOGO_PATH.exists()
        else '<div class="hx-logo-wrap" aria-hidden="true"></div>'
    )

    links_str = "\n    ".join(
        f'<a class="hx-project-link" href="{html.escape(link["url"], quote=True)}" target="_blank" rel="noopener noreferrer" aria-label="{html.escape(link["label"], quote=True)}">'
        f"{link['icon']}{html.escape(link['label'], quote=True)}</a>"
        for link in SOCIAL_LINKS
    )

    return f"""
<header class="hx-hero">
  <div class="hx-brand">
    <pre class="hx-ascii">\u2588\u2591\u2588\u2591\u2588\u2580\u2580\u2580\u2588\u2580\u2584\u2580\u2588\u2580\u2580\u2580\u2580\u2580\u2588\u2580\u2580\u2588\u2591\u2580\u2580
\u2588\u2580\u2588\u2591\u2588\u2580\u2580\u2580\u2588\u2580\u2584\u2580\u2588\u2580\u2580\u2591\u2591\u2588\u2591\u2591\u2588\u2591\u2591
\u2580\u2591\u2580\u2580\u2580\u2581\u2580\u2580\u2580\u2580\u2580\u2580\u2580\u2581\u2580\u2580\u2580\u2580\u2591\u2580\u2580\u2580\u2580\u2581</pre>
    <p class="hx-title-copy">Search, filter, collect, and download reproducibility records from public Heretic model archives.<br>Updates twice daily.</p>
  </div>
  <nav class="hx-projects" aria-label="Project links">
    <p class="hx-kicker">Project</p>
    {links_str}
  </nav>
  {logo_html}
</header>
"""


def render_toolbar_html(search: str, max_kl: Any, max_refusals: Any) -> str:
    search_value = html.escape(str(search or ""), quote=True)
    max_kl_value = html.escape(str(max_kl or ""), quote=True)
    max_refusals_value = html.escape(str(max_refusals or ""), quote=True)
    return f'''
<section class="hx-toolbar" aria-label="Filtering controls">
  <label class="hx-field"><span>Search</span><input class="hx-input" data-bridge-input="bridge-search" value="{search_value}" placeholder="repo, base model, dataset, accelerator\u2026" autocomplete="off"></label>
  <label class="hx-field"><span>Max KL</span><input class="hx-input" data-bridge-input="bridge-max-kl" value="{max_kl_value}" placeholder="blank = any" inputmode="decimal"></label>
  <label class="hx-field"><span>Max refusals</span><input class="hx-input" data-bridge-input="bridge-max-refusals" value="{max_refusals_value}" placeholder="blank = any" inputmode="numeric"></label>
  <div class="hx-actions">
    <button class="hx-btn" type="button" data-bridge-click="bridge-refresh">Refresh</button>
    <button class="hx-btn" type="button" data-bridge-click="bridge-download">Download CSV</button>
  </div>
</section>
'''


def render_log_html(status_html: str) -> str:
    log_text = html.escape(
        read_log_tail() or "No collector log entries yet.", quote=False
    )
    return f"""
<section class="hx-log" aria-label="Collector log">
  <div class="hx-log-head"><span class="hx-log-title">Collector log</span><span class="hx-log-status">{status_html}</span></div>
  <pre>{log_text}</pre>
</section>
"""


def render_storage_summary_html(records: list[dict[str, Any]]) -> str:
    base_b = total_base_bytes(records)
    repro_b = reproduce_bytes_total()
    tip = f"We have stored {len(records):,} models totalling {base_b / _GB:,.2f} GB and with our reproducibility system stored at just {human_size(repro_b)}."

    return f"""
<section class="hx-storage" aria-label="Storage efficiency">
  <article class="hx-storage-card">
    <div class="hx-storage-label">Base models data storage</div>
    <div class="hx-storage-value">{html.escape(format_tb_with_gb(base_b))}</div>
  </article>
  <div class="hx-storage-mid">
    <span class="hx-storage-ratio">{html.escape(format_efficiency(base_b, repro_b))}</span>
    <span class="hx-storage-mid-label">x efficient<span class="hx-tip" tabindex="0" data-tip="{html.escape(tip, quote=True)}"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg></span></span>
  </div>
  <article class="hx-storage-card">
    <div class="hx-storage-label">Reproducibles data storage</div>
    <div class="hx-storage-value">{html.escape(human_size(repro_b))}</div>
  </article>
</section>
"""


def refresh_view(
    search: str, max_kl: Any, max_refusals: Any
) -> tuple[str, str, str, str]:
    index = load_index()
    records = records_from_index(index)
    filtered = filter_records(records, search, max_kl, max_refusals)
    return (
        render_metric_cards_html(records, len(filtered)),
        render_records_table_html(sort_records_by_timestamp(records)),
        render_storage_summary_html(records),
        render_log_html(render_collector_status_html(index, records)),
    )


def refresh_log_only() -> str:
    index = read_json(PATHS.index_file, {})
    records = records_from_index(index)
    return render_log_html(render_collector_status_html(index, records))


def run_scheduled_collection() -> None:
    try:
        collect_and_index()
    except Exception as exc:
        append_log("scheduled collection failed", error=clean_log_text(exc))


def scheduled_hours() -> set[int]:
    hours: set[int] = set()
    for chunk in SCHEDULE_HOURS_UTC.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            hour = int(chunk)
        except ValueError:
            continue
        if 0 <= hour <= 23:
            hours.add(hour)
    return hours or {0, 12}


def run_scheduler_loop() -> None:
    hours = scheduled_hours()
    seen_slots: set[str] = set()
    while True:
        now = datetime.now(UTC)
        slot = now.strftime("%Y-%m-%dT%H:%M")
        if (
            now.hour in hours
            and now.minute == SCHEDULE_MINUTE_UTC
            and slot not in seen_slots
        ):
            seen_slots.add(slot)
            run_scheduled_collection()
        if len(seen_slots) > 16:
            seen_slots = set(sorted(seen_slots)[-8:])
        time.sleep(20)


def start_scheduler() -> None:
    thread = threading.Thread(
        target=run_scheduler_loop, name="twice-daily-heretic-cli", daemon=True
    )
    thread.start()


def start_initial_collection_if_enabled() -> None:
    if RUN_ON_STARTUP:
        thread = threading.Thread(
            target=run_scheduled_collection, name="startup-heretic-cli", daemon=True
        )
        thread.start()


def build_gradio_app() -> gr.Blocks:
    index = load_index()
    records = records_from_index(index)
    filtered = filter_records(records, "", "", "")
    with gr.Blocks(
        title=APP_TITLE,
        fill_width=True,
        delete_cache=(3600, 3600),
    ) as demo:
        gr.HTML(
            value='<div class="hx-app">' + render_header_html() + "</div>",
            elem_id="app-shell-top",
            container=False,
            padding=False,
        )
        metrics_html = gr.HTML(
            value=render_metric_cards_html(records, len(filtered)),
            elem_id="app-metrics",
            container=False,
            padding=False,
        )
        gr.HTML(
            value=render_toolbar_html("", "", ""),
            elem_id="app-toolbar",
            container=False,
            padding=False,
        )
        table_html = gr.HTML(
            value=render_records_table_html(sort_records_by_timestamp(records)),
            elem_id="app-table",
            container=False,
            padding=False,
        )
        storage_html = gr.HTML(
            value=render_storage_summary_html(records),
            elem_id="app-storage",
            container=False,
            padding=False,
        )
        log_html = gr.HTML(
            value=render_log_html(render_collector_status_html(index, records)),
            elem_id="app-log",
            container=False,
            padding=False,
        )
        search = gr.Textbox(
            value="", show_label=False, container=False, elem_id="bridge-search"
        )
        max_kl = gr.Textbox(
            value="", show_label=False, container=False, elem_id="bridge-max-kl"
        )
        max_refusals = gr.Textbox(
            value="", show_label=False, container=False, elem_id="bridge-max-refusals"
        )
        refresh_btn = gr.Button("Refresh", elem_id="bridge-refresh")
        download_btn = gr.Button("Download CSV", elem_id="bridge-download")
        download_file = gr.File(
            value=None,
            visible=False,
            elem_id="bridge-download-file",
            container=False,
        )

        inputs = [search, max_kl, max_refusals]
        outputs = [metrics_html, table_html, storage_html, log_html]

        demo.load(
            refresh_view,
            inputs=inputs,
            outputs=outputs,
            show_progress="hidden",
            queue=False,
        )
        refresh_btn.click(
            refresh_view,
            inputs=inputs,
            outputs=outputs,
            show_progress="hidden",
            queue=False,
        )
        download_btn.click(
            prepare_archive_csv_download,
            outputs=[download_file],
            show_progress="hidden",
            queue=False,
        )
        download_file.change(
            fn=None,
            inputs=[download_file],
            outputs=[],
            js="(file) => { if (file && file.url) { const a = document.createElement('a'); a.href = file.url; a.download = file.orig_name || 'heretic_reproducibles_archive.csv'; document.body.appendChild(a); a.click(); a.remove(); } }",
            queue=False,
        )

        timer = gr.Timer(value=AUTO_REFRESH_SECONDS, active=True)
        timer.tick(
            refresh_view,
            inputs=inputs,
            outputs=outputs,
            show_progress="hidden",
            queue=False,
        )
        log_timer = gr.Timer(value=5, active=True)
        log_timer.tick(
            refresh_log_only,
            outputs=[log_html],
            show_progress="hidden",
            queue=False,
        )
    return demo


start_scheduler()
start_initial_collection_if_enabled()

demo = build_gradio_app()

if __name__ == "__main__":
    demo.queue(default_concurrency_limit=1).launch(
        theme=gr.themes.Base(),
        css=CUSTOM_CSS,
        js=TABLE_SORT_JS,
        allowed_paths=[str(BASE_DIR / "assets")],
        ssr_mode=False,
    )
