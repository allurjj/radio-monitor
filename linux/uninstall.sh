#!/bin/bash
###############################################################################
# Radio Monitor 1.0 - Linux Uninstallation Script
#
# This script removes Radio Monitor and its systemd service.
#
# Usage:
#   sudo ./uninstall.sh
#
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="radio-monitor"
SERVICE_USER="radio"
INSTALL_DIR="/opt/radio-monitor"

echo "=============================================================================="
echo "Radio Monitor 1.0 - Linux Uninstallation"
echo "=============================================================================="
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}Error: This script must be run as root (sudo)${NC}"
   exit 1
fi

# Warning
echo -e "${YELLOW}WARNING: This will remove Radio Monitor from your system.${NC}"
echo ""
echo "This will:"
echo "  - Stop and disable the systemd service"
echo "  - Remove the systemd service file"
echo "  - Remove the installation directory: $INSTALL_DIR"
echo "  - Remove the service user: $SERVICE_USER"
echo ""
read -p "Do you want to continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstallation cancelled."
    exit 0
fi
echo ""

# Ask about data backup
echo "Would you like to backup your data before uninstalling?"
read -p "Backup data to /tmp/radio-monitor-backup? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    BACKUP_DIR="/tmp/radio-monitor-backup-$(date +%Y%m%d-%H%M%S)"
    echo "Creating backup: $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
    if [ -d "$INSTALL_DIR" ]; then
        cp -r "$INSTALL_DIR" "$BACKUP_DIR/"
        echo -e "${GREEN}✓ Data backed up to: $BACKUP_DIR${NC}"
    fi
fi
echo ""

# Step 1: Stop and disable service
echo "Step 1: Stopping and disabling service..."
if systemctl is-active --quiet $SERVICE_NAME; then
    systemctl stop $SERVICE_NAME
    echo -e "${GREEN}✓ Service stopped${NC}"
else
    echo -e "${YELLOW}Service was not running${NC}"
fi

if systemctl is-enabled --quiet $SERVICE_NAME; then
    systemctl disable $SERVICE_NAME
    echo -e "${GREEN}✓ Service disabled${NC}"
else
    echo -e "${YELLOW}Service was not enabled${NC}"
fi
echo ""

# Step 2: Remove systemd service file
echo "Step 2: Removing systemd service..."
if [ -f "/etc/systemd/system/$SERVICE_NAME.service" ]; then
    rm -f "/etc/systemd/system/$SERVICE_NAME.service"
    systemctl daemon-reload
    echo -e "${GREEN}✓ Service file removed${NC}"
else
    echo -e "${YELLOW}Service file not found${NC}"
fi
echo ""

# Step 3: Remove installation directory
echo "Step 3: Removing installation directory..."
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo -e "${GREEN}✓ Installation directory removed${NC}"
else
    echo -e "${YELLOW}Installation directory not found${NC}"
fi
echo ""

# Step 4: Remove service user
echo "Step 4: Removing service user..."
if id "$SERVICE_USER" &>/dev/null; then
    userdel $SERVICE_USER
    echo -e "${GREEN}✓ Service user removed${NC}"
else
    echo -e "${YELLOW}Service user not found${NC}"
fi
echo ""

# Uninstallation complete
echo "=============================================================================="
echo -e "${GREEN}Uninstallation Complete!${NC}"
echo "=============================================================================="
echo ""

if [ -d "$BACKUP_DIR" ]; then
    echo -e "${YELLOW}Data backup saved to: $BACKUP_DIR${NC}"
    echo "This backup will be kept until system cleanup."
    echo ""
fi

echo "Radio Monitor has been removed from your system."
echo ""
