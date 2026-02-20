@echo off
REM Radio Monitor 1.0 - Start GUI
REM Quick launcher for the web interface

echo Starting Radio Monitor 1.0 GUI...
echo.
echo GUI will be available at: http://127.0.0.1:5000
echo.
echo Press Ctrl+C to stop the server
echo.

python -m radio_monitor.cli --gui

pause
