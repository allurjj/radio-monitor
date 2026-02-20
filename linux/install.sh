#!/bin/bash
###############################################################################
# Radio Monitor 1.0 - Linux Installation Script
#
# This script installs Radio Monitor as a systemd service on Linux.
#
# Usage:
#   sudo ./install.sh
#
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/radio-monitor"
SERVICE_NAME="radio-monitor"
SERVICE_USER="radio"
SERVICE_GROUP="radio"
VENV_DIR="$INSTALL_DIR/venv"

echo "=============================================================================="
echo "Radio Monitor 1.0 - Linux Installation"
echo "=============================================================================="
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}Error: This script must be run as root (sudo)${NC}"
   exit 1
fi

# Detect distribution
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO=$ID
else
    echo -e "${RED}Error: Cannot detect Linux distribution${NC}"
    exit 1
fi

echo -e "${GREEN}Detected distribution: $DISTRO${NC}"
echo ""

# Step 1: Install dependencies
echo "Step 1: Installing system dependencies..."
if [[ "$DISTRO" == "ubuntu" ]] || [[ "$DISTRO" == "debian" ]]; then
    apt-get update
    apt-get install -y python3 python3-pip python3-venv systemd
elif [[ "$DISTRO" == "centos" ]] || [[ "$DISTRO" == "rhel" ]] || [[ "$DISTRO" == "fedora" ]]; then
    dnf install -y python3 python3-pip systemd
elif [[ "$DISTRO" == "arch" ]]; then
    pacman -S --noconfirm python python-pip systemd
else
    echo -e "${YELLOW}Warning: Unknown distribution '$DISTRO'${NC}"
    echo "Please install: python3, python3-pip, python3-venv, systemd"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi
echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# Step 2: Create service user
echo "Step 2: Creating service user..."
if id "$SERVICE_USER" &>/dev/null; then
    echo -e "${YELLOW}User '$SERVICE_USER' already exists${NC}"
else
    useradd -r -s /bin/false -d "$INSTALL_DIR" $SERVICE_USER
    echo -e "${GREEN}✓ User '$SERVICE_USER' created${NC}"
fi
echo ""

# Step 3: Create installation directory
echo "Step 3: Creating installation directory..."
mkdir -p "$INSTALL_DIR"
echo -e "${GREEN}✓ Installation directory created: $INSTALL_DIR${NC}"
echo ""

# Step 4: Copy application files
echo "Step 4: Copying application files..."
# Note: This script assumes it's run from the linux/ directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

if [ -d "$PROJECT_ROOT/radio_monitor" ]; then
    cp -r "$PROJECT_ROOT/radio_monitor" "$INSTALL_DIR/"
    cp -r "$PROJECT_ROOT/templates" "$INSTALL_DIR/"
    cp -r "$PROJECT_ROOT/prompts" "$INSTALL_DIR/"
    if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
        cp "$PROJECT_ROOT/requirements.txt" "$INSTALL_DIR/"
    fi
    echo -e "${GREEN}✓ Application files copied${NC}"
else
    echo -e "${RED}Error: Cannot find application files in $PROJECT_ROOT${NC}"
    echo "Please ensure you're running this script from the project directory."
    exit 1
fi
echo ""

# Step 5: Create virtual environment
echo "Step 5: Creating Python virtual environment..."
python3 -m venv "$VENV_DIR"
echo -e "${GREEN}✓ Virtual environment created${NC}"
echo ""

# Step 6: Install Python dependencies
echo "Step 6: Installing Python dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
echo -e "${GREEN}✓ Python dependencies installed${NC}"
echo ""

# Step 7: Set ownership and permissions
echo "Step 7: Setting ownership and permissions..."
chown -R $SERVICE_USER:$SERVICE_GROUP "$INSTALL_DIR"
chmod 755 "$INSTALL_DIR"
chmod -R 755 "$INSTALL_DIR/radio_monitor"
chmod -R 755 "$INSTALL_DIR/templates"
chmod -R 755 "$INSTALL_DIR/prompts"
echo -e "${GREEN}✓ Ownership and permissions set${NC}"
echo ""

# Step 8: Install systemd service file
echo "Step 8: Installing systemd service..."
cp "$SCRIPT_DIR/radio-monitor.service" /etc/systemd/system/
systemctl daemon-reload
echo -e "${GREEN}✓ Systemd service installed${NC}"
echo ""

# Step 9: Enable and start service
echo "Step 9: Enabling and starting service..."
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME
sleep 2
echo -e "${GREEN}✓ Service enabled and started${NC}"
echo ""

# Step 10: Verify service is running
echo "Step 10: Verifying service status..."
if systemctl is-active --quiet $SERVICE_NAME; then
    echo -e "${GREEN}✓ Service is running!${NC}"
else
    echo -e "${RED}✗ Service failed to start${NC}"
    echo ""
    echo "Check logs with: journalctl -u $SERVICE_NAME -n 50"
    exit 1
fi
echo ""

# Installation complete
echo "=============================================================================="
echo -e "${GREEN}Installation Complete!${NC}"
echo "=============================================================================="
echo ""
echo "Service Management:"
echo "  Start:   sudo systemctl start $SERVICE_NAME"
echo "  Stop:    sudo systemctl stop $SERVICE_NAME"
echo "  Restart: sudo systemctl restart $SERVICE_NAME"
echo "  Status:  sudo systemctl status $SERVICE_NAME"
echo "  Logs:    sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "Web Interface:"
echo "  URL: http://localhost:5000"
echo "  To access from other computers, allow port 5000 through firewall:"
echo "  sudo ufw allow 5000/tcp"
echo ""
echo "Data Location:"
echo "  Database:   $INSTALL_DIR/radio_songs.db"
echo "  Settings:   $INSTALL_DIR/radio_monitor_settings.json"
echo "  Logs:       sudo journalctl -u $SERVICE_NAME"
echo ""
echo "For more information, see linux/README.md"
echo ""
