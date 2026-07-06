#!/bin/sh
cd "$(dirname "$0")"
git pull 2>/dev/null || true
pip install -r requirements.txt 2>/dev/null
python -m playwright install chromium 2>/dev/null || true
python gui.py
