@echo off
REM ============================================================
REM  Barcode Generator Pro v2.0.0 - Windows Build Script
REM  Run this on a Windows PC to produce the .exe installer.
REM ============================================================
setlocal

echo.
echo === [1/5] Checking Python ===
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.10+ from https://python.org
    pause
    exit /b 1
)
python --version

echo.
echo === [2/5] Installing dependencies ===
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)

echo.
echo === [3/5] Building EXE with PyInstaller ===
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist BarcodeGenerator.spec del BarcodeGenerator.spec

pyinstaller --noconfirm ^
    --onefile ^
    --windowed ^
    --name "BarcodeGeneratorPro" ^
    --icon "assets/icon.ico" ^
    --add-data "assets;assets" ^
    --collect-all PyQt5 ^
    --collect-all barcode ^
    --hidden-import PyQt5.QtPrintSupport ^
    --hidden-import PyQt5.QtSvg ^
    --hidden-import PyQt5.QtWidgets ^
    --hidden-import PyQt5.QtGui ^
    --hidden-import PyQt5.QtCore ^
    --hidden-import barcode ^
    --hidden-import barcode.ean ^
    --hidden-import barcode.writer ^
    main.py

if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo === [4/5] Locating Inno Setup ===
set "ISCC="
where iscc >nul 2>&1 && set "ISCC=iscc"
if not defined ISCC if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"

if not defined ISCC (
    echo WARNING: Inno Setup not found. Skipping installer build.
    echo EXE is in: dist\BarcodeGeneratorPro.exe
    echo To create the installer, install Inno Setup 6 from https://jrsoftware.org/isdl.php
    pause
    exit /b 0
)

echo Using Inno Setup: %ISCC%
echo.
echo === [5/5] Building installer ===
"%ISCC%" installer.iss
if errorlevel 1 (
    echo ERROR: Inno Setup compilation failed.
    pause
    exit /b 1
)

echo.
echo === BUILD COMPLETE ===
echo Installer location: dist\BarcodeGeneratorPro_Setup.exe
echo.
pause
