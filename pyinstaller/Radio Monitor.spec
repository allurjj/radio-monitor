# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\allurjj\\Documents\\Radio_Monitor\\pyinstaller\\radio_monitor_exe.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\allurjj\\Documents\\Radio_Monitor\\templates', 'templates'), ('C:\\Users\\allurjj\\Documents\\Radio_Monitor\\radio_monitor', 'radio_monitor'), ('C:\\Users\\allurjj\\Documents\\Radio_Monitor\\prompts', 'prompts'), ('C:\\Users\\allurjj\\Documents\\Radio_Monitor\\static', 'static'), ('C:\\Users\\allurjj\\Documents\\Radio_Monitor\\radio_monitor_settings.json.template', '.'), ('C:\\Users\\allurjj\\Documents\\Radio_Monitor\\pyinstaller\\README.txt', '.'), ('C:\\Users\\allurjj\\Documents\\Radio_Monitor\\VERSION.py', '.')],
    hiddenimports=['sqlite3', 'flask', 'flask_httpauth', 'bcrypt', '_bcrypt', 'werkzeug', 'jinja2', 'markupsafe', 'itsdangerous', 'click', 'apscheduler', 'apscheduler.schedulers.background', 'apscheduler.triggers.cron', 'bs4', 'plexapi', 'plexapi.server', 'plexapi.base', 'pkg_resources', 'requests', 'urllib3', 'musicbrainzngs', 'rapidfuzz', 'rapidfuzz.fuzz', 'rapidfuzz.process', 'rapidfuzz.utils', 'jinja2', 'markupsafe', 'itsdangerous', 'click', 'apscheduler', 'apscheduler.schedulers.background', 'apscheduler.triggers.cron', 'bs4', 'plexapi', 'plexapi.server', 'plexapi.base', 'pkg_resources', 'requests', 'urllib3'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['C:\\Users\\allurjj\\Documents\\Radio_Monitor\\pyinstaller\\pyi_rth_radio_monitor.py'],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'pytest', 'unittest', 'tkinter', 'IPython', 'pygments', 'PIL', 'PIL.Image', 'lxml', 'lxml._elementpath', 'pydoc'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Radio Monitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\allurjj\\Documents\\Radio_Monitor\\static\\favicon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=False,
    upx_exclude=[],
    name='Radio Monitor',
)
