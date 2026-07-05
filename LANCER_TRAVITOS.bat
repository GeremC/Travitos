@echo off
cd /d "%~dp0"
git pull 2>nul
pip install -r requirements.txt >nul 2>&1
python gui.py
