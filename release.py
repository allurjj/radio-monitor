#!/usr/bin/env python3
"""
Automated Release Script for Radio Monitor

This script automates the entire release process:
1. Bumps version
2. Commits changes
3. Creates git tag
4. Builds EXE locally (using existing build.py)
5. Creates release ZIP
6. Uploads to GitHub Releases

Prerequisites:
- GitHub CLI (gh) installed and authenticated

Usage:
    python release.py [version]

Example:
    python release.py 1.1.11
"""

import os
import sys
import subprocess
import shutil
import zipfile
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

def run_command(cmd, check=True, capture_output=False, cwd=None):
    """Run a shell command and return the result."""
    print(f"  $ {cmd}")
    if capture_output:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            check=check,
            cwd=cwd
        )
        return result.stdout.strip()
    else:
        subprocess.run(cmd, shell=True, check=check, cwd=cwd)
    return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python release.py <version>")
        print("Example: python release.py 1.1.11")
        sys.exit(1)

    new_version = sys.argv[1]

    print("=" * 70)
    print(f"Radio Monitor - Release v{new_version}")
    print("=" * 70)
    print()

    # Step 1: Update version in __init__.py
    print("Step 1: Updating version...")
    init_file = os.path.join(PROJECT_ROOT, 'radio_monitor', '__init__.py')
    with open(init_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Find and replace the version line
    for i, line in enumerate(lines):
        if line.startswith('__version__ ='):
            lines[i] = f'__version__ = "{new_version}"\n'
            break

    with open(init_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print(f"  Updated __version__ to {new_version}")
    print()

    # Step 2: Commit version change
    print("Step 2: Committing version change...")
    run_command('git add radio_monitor/__init__.py')
    run_command(f'git commit -m "chore: Bump version to {new_version}"')
    print()

    # Step 3: Create git tag
    print("Step 3: Creating git tag...")
    tag_name = f"v{new_version}"
    run_command(f'git tag -a {tag_name} -m "Release {tag_name}"')
    print()

    # Step 4: Push to GitHub
    print("Step 4: Pushing to GitHub...")
    run_command('git push origin main')
    run_command(f'git push origin {tag_name}')
    print()

    # Step 5: Build EXE locally
    print("Step 5: Building Windows EXE...")
    print("  This will take several minutes...")
    build_dir = os.path.join(PROJECT_ROOT, 'pyinstaller')

    # Clean previous builds
    for dir_name in ['build', 'dist/pyinstaller']:
        dir_path = os.path.join(PROJECT_ROOT, dir_name)
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)

    # Run build.py
    run_command('python build.py', cwd=build_dir)
    print()

    # Step 6: Create release ZIP
    print("Step 6: Creating release ZIP...")
    exe_dir = os.path.join(PROJECT_ROOT, 'dist', 'pyinstaller', 'Radio Monitor')
    zip_filename = f"Radio-Monitor-v{new_version}.zip"
    zip_path = os.path.join(PROJECT_ROOT, 'dist', 'pyinstaller', zip_filename)

    if os.path.exists(zip_path):
        os.remove(zip_path)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(exe_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, exe_dir)
                zipf.write(file_path, arcname)

    zip_size = os.path.getsize(zip_path)
    print(f"  Created: {zip_filename} ({zip_size:,} bytes)")
    print()

    # Step 7: Upload to GitHub Releases
    print("Step 7: Uploading to GitHub Releases...")
    notes = f"""Release v{new_version}

Built locally on Windows 10 for maximum compatibility.

## Changes
See CHANGELOG.md for details.

## Installation
1. Download the ZIP file
2. Extract to a folder
3. Double-click: Radio Monitor.exe
"""

    # Check if gh CLI is available
    try:
        # Try full path to gh.exe (common Windows installation location)
        gh_path = r'C:\Program Files\GitHub CLI\gh.exe'
        if not os.path.exists(gh_path):
            # Fallback to PATH
            gh_path = 'gh'

        # Verify gh works
        subprocess.run([gh_path, '--version'], capture_output=True, check=True)

        # Use gh to create release
        release_cmd = [
            gh_path, 'release', 'create', tag_name,
            zip_path,
            '--title', tag_name,
            '--notes', notes
        ]
        subprocess.run(release_cmd, check=True)
        print()
        print(f"Release URL: https://github.com/allurjj/radio-monitor/releases/tag/{tag_name}")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print()
        print(f"  [WARNING] GitHub CLI not found or error: {e}")
        print("  Manual upload required.")
        print()
        print("  To upload manually:")
        print(f"  1. Go to: https://github.com/allurjj/radio-monitor/releases/new")
        print(f"  2. Tag: {tag_name}")
        print(f"  3. Upload: {zip_path}")
        print(f"  4. Notes:")
        print("  " + "\n  ".join(notes.split('\n')))
        print()

    print()

    print("=" * 70)
    print(f"[OK] Release {tag_name} Complete!")
    print("=" * 70)
    print()

if __name__ == '__main__':
    main()
