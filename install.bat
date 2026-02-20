@echo off
REM Radio Monitor 1.0 - Windows Installation Script
REM Usage: install.bat

echo ==========================================
echo Radio Monitor 1.0 - Installation
echo ==========================================
echo.

REM Check Python version
echo Checking Python version...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Python not found
    echo Please install Python 3.10 or higher from https://www.python.org/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Found Python %PYTHON_VERSION%
echo ✓ Python installed
echo.

REM Create directory structure
echo Creating directory structure...
if not exist backups mkdir backups
if not exist logs mkdir logs
if not exist templates mkdir templates
echo ✓ Directories created
echo.

REM Install dependencies
echo Installing Python dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ Error: Failed to install dependencies
    pause
    exit /b 1
)
echo ✓ Dependencies installed
echo.

REM Create settings file from template if it doesn't exist
if not exist radio_monitor_settings.json (
    echo Creating settings file from template...
    copy radio_monitor_settings.json.template radio_monitor_settings.json >nul
    echo ✓ Settings file created: radio_monitor_settings.json
    echo ⚠️  Please edit radio_monitor_settings.json with your configuration
) else (
    echo ⚠️  Settings file already exists, skipping...
)
echo.

echo ==========================================
echo Installation complete!
echo ==========================================
echo.
echo Next steps:
echo 1. Edit radio_monitor_settings.json with your configuration
echo 2. Run: python radio_monitor.py --test
echo 3. Start monitoring: python radio_monitor.py
echo.
pause
