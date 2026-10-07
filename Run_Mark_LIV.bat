@echo off
setlocal
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo MARK LIV: virtual environment not found.
    echo Run: python -m venv venv
    echo Then run: venv\Scripts\python.exe setup.py
    pause
    exit /b 1
)
echo Starting MARK LIV...
"venv\Scripts\python.exe" main.py
if errorlevel 1 (
    echo.
    echo MARK LIV exited with an error. The details are above.
    pause
)
