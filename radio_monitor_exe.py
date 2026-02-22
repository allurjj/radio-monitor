#!/usr/bin/env python3
"""
Radio Monitor - Windows EXE Entry Point

This wrapper script ensures:
1. Correct working directory (database created in exe's folder, not temp)
2. Default GUI mode when no arguments provided
"""

import sys
import os

# Fix 3: Set working directory to exe location
# This ensures the database is created in the exe's folder, not in temp
if getattr(sys, 'frozen', False):
    exe_dir = os.path.dirname(sys.executable)
    if exe_dir:
        os.chdir(exe_dir)

# Fix 1: Default to GUI mode
# When user double-clicks the exe, no arguments are provided
# In this case, automatically add --gui flag to launch the web interface
if len(sys.argv) == 1:
    sys.argv.insert(1, '--gui')

# Import and run the main CLI
from radio_monitor.cli import main
sys.exit(main())
