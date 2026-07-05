#!/bin/sh
cd "$(dirname "$0")"
git pull 2>/dev/null || true
pip install -r requirements.txt 2>/dev/null
python gui.py
