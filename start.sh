#!/bin/bash
# ============================================================================
# Lucy Smart Glasses - Startup Script
# ============================================================================
# This script starts the Lucy Smart Glasses application
# It is designed to work with systemd for auto-start on boot
# ============================================================================

set -e  # Exit on error

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "======================================"
echo "Lucy Smart Glasses - Starting..."
echo "======================================"
echo "Working directory: $SCRIPT_DIR"
echo "Current user: $(whoami)"
echo "Date: $(date)"
echo "======================================"

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo "ERROR: main.py not found in $SCRIPT_DIR"
    exit 1
fi

# Activate virtual environment
if [ ! -d "venv" ]; then
    echo "ERROR: Virtual environment not found at $SCRIPT_DIR/venv"
    echo "Please run setup.sh first"
    exit 1
fi

echo "Activating virtual environment..."
# Use absolute path for activation
source "$SCRIPT_DIR/venv/bin/activate"

# Verify Python is from venv
echo "Python path: $(which python)"
echo "Python version: $(python --version)"

# Run the application
echo ""
echo "Starting Lucy Smart Glasses..."
echo "======================================"
echo ""

# Run with unbuffered output so logs appear in journalctl
exec python -u main.py
