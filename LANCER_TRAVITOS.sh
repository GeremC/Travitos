#!/bin/sh
cd "$(dirname "$0")"
pip install -r requirements.txt 2>/dev/null
python gui.py
