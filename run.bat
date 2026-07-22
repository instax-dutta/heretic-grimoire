@echo off
setlocal enabledelayedexpansion

set "REPO=https://github.com/instax-dutta/heretic-grimoire.git"
set "DIR=heretic-grimoire"

if not exist "%DIR%" (
    echo ==^> Cloning Heretic Grimoire...
    git clone --depth=1 "%REPO%" "%DIR%"
)

cd "%DIR%"

echo ==^> Creating virtual environment...
python -m venv venv
call venv\Scripts\activate.bat

echo ==^> Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt

echo ==^> Starting Heretic Grimoire...
echo     Open http://127.0.0.1:7860 in your browser.
python app.py

pause
