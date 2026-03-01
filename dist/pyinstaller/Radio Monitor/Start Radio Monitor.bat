@echo off
REM Radio Monitor Launcher
REM This starts the application in the background (no console window)
start "" /B "Radio Monitor.exe"
REM Opens browser to the web interface
timeout /t 2 /nobreak >nul
start http://127.0.0.1:5000
