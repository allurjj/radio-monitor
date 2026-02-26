"""
PyInstaller Runtime Hook for Radio Monitor

This hook fixes DLL loading issues by ensuring temporary files
are extracted to the application directory instead of C:\temp.

The problem: PyInstaller defaults to C:\temp which:
- May not exist
- May have permission issues
- Triggers antivirus false positives
- Causes "Invalid access to memory location" errors

The solution: Override _MEIPASS to use local directory.
"""

import os
import sys

# Only run when frozen (in the EXE, not during dev)
if getattr(sys, 'frozen', False):

    # Get the executable directory
    if hasattr(sys, 'executable'):
        exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = os.path.dirname(sys.argv[0])

    # Override _MEIPASS to extract files next to the EXE
    # This prevents extraction to C:\temp
    if hasattr(sys, '_MEIPASS'):
        # Create _internal directory next to exe (PyInstaller's internal extraction dir)
        internal_dir = os.path.join(exe_dir, '_internal')

        # Create it if it doesn't exist
        try:
            os.makedirs(internal_dir, exist_ok=True)
        except Exception:
            pass  # If we can't create it, PyInstaller will use default location

        # Set _MEIPASS to our custom location
        sys._MEIPASS = internal_dir

    # Also override temp environment variables
    temp_dir = os.path.join(exe_dir, 'temp')
    try:
        os.makedirs(temp_dir, exist_ok=True)
        os.environ['TEMP'] = temp_dir
        os.environ['TMP'] = temp_dir
    except Exception:
        pass  # Fall back to system temp if we can't create local temp
