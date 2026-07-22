#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/instax-dutta/heretic-grimoire.git"
DIR="heretic-grimoire"

if [ ! -d "$DIR" ]; then
    echo "==> Cloning Heretic Grimoire..."
    git clone --depth=1 "$REPO" "$DIR"
fi

cd "$DIR"

echo "==> Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "==> Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Starting Heretic Grimoire..."
echo "    Open http://127.0.0.1:7860 in your browser."
python app.py
