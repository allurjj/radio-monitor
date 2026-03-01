@echo off
REM Radio Monitor Launcher
REM This sets up the environment before launching the EXE
REM Fixes the "Invalid access to memory location" DLL loading error

echo Starting Radio Monitor...
echo.

REM Get the directory where this batch file is located
set "APP_DIR=%~dp0"

REM Set temp directories to local folder (not C:\temp)
set "TEMP=%APP_DIR%temp"
set "TMP=%APP_DIR%temp"

REM Create temp directory if it doesn't exist
if not exist "%TEMP%" mkdir "%TEMP%"

REM Add the app directory to PATH
set "PATH=%APP_DIR%;%PATH%"

REM Launch the application
start "" "%APP_DIR%Radio Monitor.exe"

REM Wait a moment for the app to start
timeout /t 3 /nobreak >nul

REM Open browser to the web interface
start http://127.0.0.1:5000
