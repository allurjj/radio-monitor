# Linux Deployment - Radio Monitor

This directory contains files for deploying Radio Monitor on Linux as a native systemd service.

## Files

- **radio-monitor.service** - Systemd service unit file
- **install.sh** - Automated installation script
- **uninstall.sh** - Automated uninstallation script
- **README.md** - This file

## Supported Distributions

- ✅ Ubuntu 18.04+
- ✅ Debian 10+
- ✅ CentOS 7/8
- ✅ RHEL 7/8
- ✅ Fedora 30+
- ✅ Arch Linux

## Quick Start (Automated Installation)

### Prerequisites

- Python 3.10 or higher
- systemd
- Root/sudo access

### Installation

```bash
# From project root
cd linux

# Make scripts executable
chmod +x install.sh uninstall.sh

# Run installation (requires sudo)
sudo ./install.sh
```

The installation script will:
1. Install system dependencies (python3, pip, venv, systemd)
2. Create a dedicated service user (`radio`)
3. Install Radio Monitor to `/opt/radio-monitor`
4. Create a Python virtual environment
5. Install Python dependencies
6. Install and enable the systemd service
7. Start the service

### Access Web Interface

```
http://localhost:5000
```

## Manual Installation

If you prefer manual installation or need to customize:

### 1. Install Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv systemd
```

**CentOS/RHEL:**
```bash
sudo dnf install -y python3 python3-pip systemd
```

**Arch Linux:**
```bash
sudo pacman -S python python-pip systemd
```

### 2. Create Service User

```bash
sudo useradd -r -s /bin/false -d /opt/radio-monitor radio
```

### 3. Install Application

```bash
# Create installation directory
sudo mkdir -p /opt/radio-monitor

# Copy application files
sudo cp -r ../radio_monitor /opt/radio-monitor/
sudo cp -r ../templates /opt/radio-monitor/
sudo cp -r ../prompts /opt/radio-monitor/
sudo cp ../requirements.txt /opt/radio-monitor/
```

### 4. Create Virtual Environment

```bash
cd /opt/radio-monitor
sudo python3 -m venv venv
sudo venv/bin/pip install --upgrade pip
sudo venv/bin/pip install -r requirements.txt
```

### 5. Set Permissions

```bash
sudo chown -R radio:radio /opt/radio-monitor
sudo chmod 755 /opt/radio-monitor
sudo chmod -R 755 /opt/radio-monitor/radio_monitor
sudo chmod -R 755 /opt/radio-monitor/templates
sudo chmod -R 755 /opt/radio-monitor/prompts
```

### 6. Install Systemd Service

```bash
# Copy service file
sudo cp radio-monitor.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable radio-monitor

# Start service
sudo systemctl start radio-monitor
```

### 7. Verify

```bash
# Check service status
sudo systemctl status radio-monitor

# View logs
sudo journalctl -u radio-monitor -f
```

## Service Management

### Start/Stop/Restart

```bash
# Start
sudo systemctl start radio-monitor

# Stop
sudo systemctl stop radio-monitor

# Restart
sudo systemctl restart radio-monitor

# Check status
sudo systemctl status radio-monitor
```

### Enable/Disable Auto-Start

```bash
# Enable (start on boot)
sudo systemctl enable radio-monitor

# Disable (don't start on boot)
sudo systemctl disable radio-monitor
```

### View Logs

```bash
# Follow logs in real-time
sudo journalctl -u radio-monitor -f

# Last 100 lines
sudo journalctl -u radio-monitor -n 100

# Since last boot
sudo journalctl -u radio-monitor -b

# Since yesterday
sudo journalctl -u radio-monitor --since yesterday
```

## Configuration

### Service File Location

`/etc/systemd/system/radio-monitor.service`

### Customization

Edit the service file to customize:

```ini
[Service]
# Change user/group
User=youruser
Group=yourgroup

# Change working directory
WorkingDirectory=/path/to/radio-monitor

# Add environment variables
Environment="TZ=America/Chicago"
Environment="LOG_LEVEL=DEBUG"

# Change restart delay
RestartSec=5
```

After editing:
```bash
sudo systemctl daemon-reload
sudo systemctl restart radio-monitor
```

### Change Port

Edit `/opt/radio-monitor/radio_monitor_settings.json`:

```json
{
  "gui": {
    "port": 8000
  }
}
```

Then restart:
```bash
sudo systemctl restart radio-monitor
```

### Firewall

Allow port through firewall:

**Ubuntu/Debian (UFW):**
```bash
sudo ufw allow 5000/tcp
sudo ufw reload
```

**CentOS/RHEL (firewalld):**
```bash
sudo firewall-cmd --permanent --add-port=5000/tcp
sudo firewall-cmd --reload
```

** iptables:**
```bash
sudo iptables -A INPUT -p tcp --dport 5000 -j ACCEPT
sudo iptables-save > /etc/iptables/rules.v4
```

## Data Location

All data is stored in `/opt/radio-monitor`:

```
/opt/radio-monitor/
├── radio_monitor/              # Application code
├── templates/                  # HTML templates
├── prompts/                    # AI prompts
├── venv/                       # Python virtual environment
├── radio_songs.db              # Database
├── radio_monitor_settings.json # Settings
└── radio_monitor.log           # Application logs
```

## Backup and Restore

### Backup

```bash
# Stop service
sudo systemctl stop radio-monitor

# Create backup
sudo tar czf /tmp/radio-monitor-backup-$(date +%Y%m%d).tar.gz /opt/radio-monitor

# Restart service
sudo systemctl start radio-monitor
```

### Restore

```bash
# Stop service
sudo systemctl stop radio-monitor

# Extract backup
sudo tar xzf /tmp/radio-monitor-backup-20260218.tar.gz -C /

# Start service
sudo systemctl start radio-monitor
```

## Uninstallation

### Automated

```bash
cd linux
sudo ./uninstall.sh
```

### Manual

```bash
# Stop and disable service
sudo systemctl stop radio-monitor
sudo systemctl disable radio-monitor

# Remove service file
sudo rm -f /etc/systemd/system/radio-monitor.service
sudo systemctl daemon-reload

# Remove installation directory
sudo rm -rf /opt/radio-monitor

# Remove service user
sudo userdel radio
```

## Troubleshooting

### Service Won't Start

```bash
# Check service status
sudo systemctl status radio-monitor

# View logs
sudo journalctl -u radio-monitor -n 50

# Check files exist
ls -la /opt/radio-monitor

# Check permissions
sudo ls -la /opt/radio-monitor

# Test run manually
sudo -u radio /opt/radio-monitor/venv/bin/python -m radio_monitor.cli --gui
```

### Permission Errors

```bash
# Fix ownership
sudo chown -R radio:radio /opt/radio-monitor

# Fix permissions
sudo chmod 755 /opt/radio-monitor
sudo chmod -R 755 /opt/radio-monitor/radio_monitor
```

### Can't Access Web Interface

```bash
# Check service is running
sudo systemctl status radio-monitor

# Check port is listening
sudo ss -tlnp | grep 5000

# Check firewall
sudo ufw status
sudo iptables -L -n

# Test from localhost
curl http://localhost:5000
```

### Database Issues

```bash
# Stop service
sudo systemctl stop radio-monitor

# Backup current database
sudo cp /opt/radio-monitor/radio_songs.db /opt/radio-monitor/radio_songs.db.backup

# Start fresh (remove database)
sudo rm /opt/radio-monitor/radio_songs.db

# Start service
sudo systemctl start radio-monitor
```

## Performance Tuning

### Limit Memory Usage

Edit `/etc/systemd/system/radio-monitor.service`:

```ini
[Service]
MemoryMax=512M
MemoryHigh=500M
```

### Limit CPU Usage

```ini
[Service]
CPUQuota=50%
```

### Change Log Level

Edit `/opt/radio-monitor/radio_monitor_settings.json`:

```json
{
  "logging": {
    "level": "WARNING"
  }
}
```

## Security Hardening

The service file includes several security measures:

- `NoNewPrivileges=true` - Prevent process from gaining new privileges
- `PrivateTmp=true` - Separate /tmp namespace
- `ProtectSystem=strict` - Read-only system directories
- `ProtectHome=true` - No access to home directories
- `ReadWritePaths` - Only write to specific directories

For additional security:

### Run as non-root user (already configured)

```ini
[Service]
User=radio
Group=radio
```

### Enable AppArmor/SELinux

**AppArmor (Ubuntu/Debian):**
```bash
sudo aa-complain /opt/radio-monitor/venv/bin/python3
```

**SELinux (CentOS/RHEL):**
```bash
sudo semanage permissive -a httpd_t
```

## Monitoring

### Systemd Monitoring

```bash
# Enable automatic restarts on failure
sudo systemctl edit radio-monitor

# Add:
[Service]
# Restart automatically on failure
Restart=on-failure
RestartSec=10
```

### External Monitoring

Use monitoring tools like:
- **Monit:** Process and resource monitoring
- **Nagios:** Infrastructure monitoring
- **Prometheus:** Metrics collection
- **Grafana:** Visualization

Example Monit config:
```
check process radio-monitor with pidfile /var/run/radio-monitor.pid
  start program = "/bin/systemctl start radio-monitor"
  stop program = "/bin/systemctl stop radio-monitor"
  if failed host localhost port 5000 for 3 cycles then restart
```

## For More Information

- **Main Deployment Guide:** ../DeploymentInfo.md
- **Docker Deployment:** ../DockerInfo.md
- **Systemd Documentation:** https://www.freedesktop.org/software/systemd/man/systemd.service.html
- **Project README:** ../README.md
