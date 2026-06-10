"""
Service Installation module for Radio Monitor 1.0

This module handles cross-platform service installation:
- Linux systemd installer
- Windows Service installer (using pywin32)
- Platform detection
- --install and --uninstall CLI commands
- Auto-start on boot

Key Features:
- Automatic platform detection
- Service installation and removal
- Auto-restart on failure
- Graceful uninstallation
"""

import os
import sys
import platform
import subprocess
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def get_platform():
    """Detect current platform

    Returns:
        'linux', 'windows', or 'unknown'
    """
    system = platform.system()
    if system == 'Linux':
        return 'linux'
    elif system == 'Windows':
        return 'windows'
    else:
        return 'unknown'


def get_python_executable():
    """Get path to Python executable

    Returns:
        Path to Python interpreter
    """
    return sys.executable


def get_script_path():
    """Get path to the main script

    Returns:
        Path to radio_monitor main script
    """
    # Get the directory where this module is located
    module_dir = Path(__file__).parent

    # The main script should be in the parent directory
    script_path = module_dir.parent / 'radio_monitor.py'

    if script_path.exists():
        return str(script_path)
    else:
        # Fallback to current working directory
        return os.path.join(os.getcwd(), 'radio_monitor.py')


def install_service(settings_file='radio_monitor_settings.json'):
    """Install as system service (platform detection)

    Args:
        settings_file: Path to settings file

    Returns:
        (success, message) tuple
    """
    plat = get_platform()

    if plat == 'linux':
        return install_systemd_service(settings_file)
    elif plat == 'windows':
        return install_windows_service(settings_file)
    else:
        return False, f"Unsupported platform: {plat}"


def uninstall_service():
    """Uninstall system service (platform detection)

    Returns:
        (success, message) tuple
    """
    plat = get_platform()

    if plat == 'linux':
        return uninstall_systemd_service()
    elif plat == 'windows':
        return uninstall_windows_service()
    else:
        return False, f"Unsupported platform: {plat}"


def install_systemd_service(settings_file='radio_monitor_settings.json'):
    """Install as systemd service on Linux

    Creates /etc/systemd/system/radio-monitor.service and enables it.

    Args:
        settings_file: Path to settings file

    Returns:
        (success, message) tuple
    """
    # Check if running as root
    if os.geteuid() != 0:
        return False, "Must run as root (use sudo)"

    # Get paths
    python = get_python_executable()
    script = get_script_path()
    cwd = os.path.dirname(script)

    # Get current user (if running with sudo)
    user = os.environ.get('SUDO_USER', os.environ.get('USER', 'root'))

    # Create systemd service file
    service_file_content = f"""[Unit]
Description=Radio Monitor 1.0
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={cwd}
ExecStart={python} {script}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

    service_path = '/etc/systemd/system/radio-monitor.service'

    try:
        # Write service file
        with open(service_path, 'w') as f:
            f.write(service_file_content)

        # Reload systemd
        subprocess.run(['systemctl', 'daemon-reload'], check=True)

        # Enable service
        subprocess.run(['systemctl', 'enable', 'radio-monitor'], check=True)

        # Start service
        subprocess.run(['systemctl', 'start', 'radio-monitor'], check=True)

        return True, f"Service installed and started (user: {user})"

    except subprocess.CalledProcessError as e:
        return False, f"Failed to install service: {e}"
    except Exception as e:
        return False, f"Error: {e}"


def uninstall_systemd_service():
    """Uninstall systemd service on Linux

    Stops, disables, and removes the systemd service.

    Returns:
        (success, message) tuple
    """
    # Check if running as root
    if os.geteuid() != 0:
        return False, "Must run as root (use sudo)"

    service_path = '/etc/systemd/system/radio-monitor.service'

    # Check if service is installed
    if not os.path.exists(service_path):
        return False, "Service not installed"

    try:
        # Stop service
        subprocess.run(['systemctl', 'stop', 'radio-monitor'],
                      stderr=subprocess.DEVNULL, check=False)

        # Disable service
        subprocess.run(['systemctl', 'disable', 'radio-monitor'],
                      stderr=subprocess.DEVNULL, check=False)

        # Remove service file
        os.remove(service_path)

        # Reload systemd
        subprocess.run(['systemctl', 'daemon-reload'], check=True)

        return True, "Service uninstalled"

    except Exception as e:
        return False, f"Error: {e}"


def install_windows_service(settings_file='radio_monitor_settings.json'):
    """Install as Windows service using pywin32

    Creates a Windows service that runs the radio monitor.

    Args:
        settings_file: Path to settings file

    Returns:
        (success, message) tuple
    """
    try:
        import win32service
        import win32serviceutil
        import win32event
        import win32evtlogutil
        import servicemanager
    except ImportError:
        return False, "pywin32 not installed. Install with: pip install pywin32"

    # Get paths
    python = get_python_executable()
    script = get_script_path()
    cwd = os.path.dirname(script)

    # For now, return a message explaining manual installation
    # Full Windows service integration requires more complex setup
    return False, "Windows service installation requires manual setup. See documentation."

    # Future implementation:
    # Service class would go here
    # For now, we provide instructions for manual setup


def uninstall_windows_service():
    """Uninstall Windows service

    Stops and removes the Windows service.

    Returns:
        (success, message) tuple
    """
    # For now, Windows service requires manual uninstallation
    # Future implementation would use pywin32 to remove the service
    return False, "Windows service uninstallation requires manual setup. See documentation."


def check_service_installed():
    """Check if service is installed

    Returns:
        (installed, platform, status) tuple
    """
    plat = get_platform()

    if plat == 'linux':
        # Check systemd service
        service_path = '/etc/systemd/system/radio-monitor.service'
        if os.path.exists(service_path):
            try:
                result = subprocess.run(['systemctl', 'is-active', 'radio-monitor'],
                                         capture_output=True, text=True)
                status = result.stdout.strip()
                return True, 'linux', status
            except:
                return True, 'linux', 'unknown'
        return False, 'linux', 'not_installed'

    elif plat == 'windows':
        # Check Windows service
        try:
            import win32service
            import win32serviceutil

            # Try to open the service
            win32serviceutil.QueryServiceStatus('RadioMonitor')
            return True, 'windows', 'installed'
        except:
            return False, 'windows', 'not_installed'

    else:
        return False, plat, 'unsupported'


def get_service_status():
    """Get current service status

    Returns:
        Status string or 'not_installed'
    """
    installed, plat, _ = check_service_installed()

    if not installed:
        return 'not_installed'

    if plat == 'linux':
        try:
            result = subprocess.run(['systemctl', 'status', 'radio-monitor'],
                                     capture_output=True, text=True)
            return result.stdout.strip()
        except:
            return 'unknown'

    elif plat == 'windows':
        try:
            import win32service
            import win32serviceutil

            status = win32serviceutil.QueryServiceStatus('RadioMonitor')
            if status[1] == win32service.SERVICE_RUNNING:
                return 'running'
            else:
                return 'stopped'
        except:
            return 'unknown'

    return 'unknown'


def print_service_info():
    """Print service installation status and info"""
    installed, plat, status = check_service_installed()

    print(f"Platform: {plat}")
    print(f"Service installed: {installed}")

    if installed:
        print(f"Status: {status}")

        if plat == 'linux':
            print("\nCommands:")
            print("  sudo systemctl status radio-monitor  # Check status")
            print("  sudo systemctl stop radio-monitor     # Stop service")
            print("  sudo systemctl start radio-monitor    # Start service")
            print("  sudo systemctl restart radio-monitor  # Restart service")
            print("  journalctl -u radio-monitor           # View logs")

        elif plat == 'windows':
            print("\nCommands:")
            print("  sc query RadioMonitor                # Check status")
            print("  sc stop RadioMonitor                  # Stop service")
            print("  sc start RadioMonitor                 # Start service")
            print("  Services.msc                         # Services GUI")
    else:
        print("\nTo install service:")
        print("  python radio_monitor.py --install")
        print("\n(Requires root/admin privileges)")
