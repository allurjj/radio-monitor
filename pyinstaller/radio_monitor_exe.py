#!/usr/bin/env python3
"""
Radio Monitor - Windows EXE Entry Point

This wrapper script ensures:
1. Correct working directory (database created in exe's folder, not temp)
2. Default GUI mode when no arguments provided
3. Proper temp directory (avoids C:\temp permission issues)
"""

import sys
import os
import tempfile

# Fix temp directory BEFORE anything else
if getattr(sys, 'frozen', False):
    # Get the executable directory
    exe_dir = os.path.dirname(sys.executable)
    if exe_dir:
        # Set working directory to exe location
        os.chdir(exe_dir)

        # Create a local temp directory
        local_temp = os.path.join(exe_dir, 'temp')
        try:
            os.makedirs(local_temp, exist_ok=True)
            # Override temp environment variables
            os.environ['TEMP'] = local_temp
            os.environ['TMP'] = local_temp
            tempfile.tempdir = local_temp
        except Exception:
            pass  # Fall back to system temp if we can't create local temp

# Default to GUI mode when no arguments provided
# When user double-clicks the exe, no arguments are provided
# In this case, automatically add --gui flag to launch the web interface
if len(sys.argv) == 1:
    sys.argv.insert(1, '--gui')

# Import and run the main CLI
from radio_monitor.cli import main
sys.exit(main())
