"""
PyInstaller Runtime Hook for Radio Monitor

This hook fixes DLL loading issues by ensuring temporary files
are extracted to the application directory instead of C:\temp.

The problem: PyInstaller defaults to C:\temp which:
- May not exist
- May have permission issues
- Triggers antivirus false positives
- Causes "Invalid access to memory location" errors

The solution: Redirect temp paths to the exe directory.
"""

import os
import sys
import tempfile

# Only run when frozen (in the EXE, not during dev)
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):

    # Get the executable directory
    if hasattr(sys, 'executable'):
        exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = os.path.dirname(sys.argv[0])

    # Create a temp subdirectory in the exe folder
    temp_dir = os.path.join(exe_dir, 'temp')

    # Create it if it doesn't exist
    try:
        os.makedirs(temp_dir, exist_ok=True)
    except Exception:
        # If we can't create it, fall back to system temp
        temp_dir = tempfile.gettempdir()

    # Override temp environment variables
    # This makes Python and PyInstaller use our temp directory
    os.environ['TEMP'] = temp_dir
    os.environ['TMP'] = temp_dir

    # Also override Python's tempfile module
    tempfile.tempdir = temp_dir
