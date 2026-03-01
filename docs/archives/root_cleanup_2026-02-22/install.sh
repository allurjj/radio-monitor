#!/bin/bash
# Radio Monitor 1.0 - Linux Installation Script
# Usage: bash install.sh

set -e  # Exit on error

echo "=========================================="
echo "Radio Monitor 1.0 - Installation"
echo "=========================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $python_version"

# Check if Python 3.10 or higher
if ! python3 -c 'import sys; exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    echo "❌ Error: Python 3.10 or higher required"
    echo "Current version: $python_version"
    exit 1
fi
echo "✓ Python version OK"
echo ""

# Create directory structure
echo "Creating directory structure..."
mkdir -p backups
mkdir -p logs
mkdir -p templates
echo "✓ Directories created"
echo ""

# Install dependencies
echo "Installing Python dependencies..."
pip3 install -r requirements.txt
echo "✓ Dependencies installed"
echo ""

# Create settings file from template if it doesn't exist
if [ ! -f "radio_monitor_settings.json" ]; then
    echo "Creating settings file from template..."
    cp radio_monitor_settings.json.template radio_monitor_settings.json
    echo "✓ Settings file created: radio_monitor_settings.json"
    echo "⚠️  Please edit radio_monitor_settings.json with your configuration"
else
    echo "⚠️  Settings file already exists, skipping..."
fi
echo ""

# Set permissions
echo "Setting permissions..."
chmod +x install.sh 2>/dev/null || true
echo "✓ Permissions set"
echo ""

echo "=========================================="
echo "Installation complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit radio_monitor_settings.json with your configuration"
echo "2. Run: python3 radio_monitor.py --test"
echo "3. Start monitoring: python3 radio_monitor.py"
echo ""
