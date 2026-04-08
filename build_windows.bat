@echo off
REM ============================================
REM  Hayseys Astrostacker - Windows Build Script
REM  Run this from the astrostacker project folder
REM  in PowerShell or Command Prompt.
REM ============================================

echo === Hayseys Astrostacker Windows Build ===
echo.

REM Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.9+ and add to PATH.
    pause
    exit /b 1
)

echo [1/4] Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install pyinstaller

echo.
echo [2/4] Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo [3/4] Building application...
python -m PyInstaller astrostacker.spec --clean

echo.
if exist "dist\Hayseys Astrostacker\Hayseys Astrostacker.exe" (
    echo === Build Complete ===
    echo.
    echo Output: dist\Hayseys Astrostacker\Hayseys Astrostacker.exe
    echo.
    echo To run:  "dist\Hayseys Astrostacker\Hayseys Astrostacker.exe"
    echo To distribute: zip the "dist\Hayseys Astrostacker" folder
) else (
    echo === Build may have failed - check output above ===
)

echo.
pause
