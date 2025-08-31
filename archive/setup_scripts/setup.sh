#!/bin/bash
# Setup script for Music Chronus project

echo "========================================="
echo "Music Chronus - Project Setup"
echo "========================================="

# Check Python version
python_version=$(python3 --version 2>&1 | grep -oP '\d+\.\d+')
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then 
    echo "❌ Python $required_version or higher is required (found $python_version)"
    exit 1
fi
echo "✓ Python $python_version detected"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate
echo "✓ Virtual environment activated"

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip setuptools wheel > /dev/null 2>&1
echo "✓ pip upgraded"

# Install system dependencies for audio (WSL2/Ubuntu)
echo ""
echo "Checking system dependencies..."
packages_needed=""

# Check for each package
for pkg in libportaudio2 libsndfile1 libpulse-dev pulseaudio-utils; do
    if ! dpkg -l | grep -q "^ii  $pkg"; then
        packages_needed="$packages_needed $pkg"
    fi
done

if [ -n "$packages_needed" ]; then
    echo "Installing system packages:$packages_needed"
    echo "Please enter your password if prompted:"
    sudo apt-get update && sudo apt-get install -y$packages_needed
else
    echo "✓ All system dependencies installed"
fi

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
echo "This may take a few minutes..."

# Install basic requirements first (without rtmixer)
pip install sounddevice numpy cffi scipy librosa 2>&1 | grep -E "(Successfully|Requirement already)"

# Try to install rtmixer separately (it may fail due to compilation issues)
echo ""
echo "Attempting to install rtmixer..."
if pip install rtmixer 2>/dev/null; then
    echo "✓ rtmixer installed successfully"
else
    echo "⚠️  rtmixer installation failed (expected in WSL2)"
    echo "   We'll use alternative audio backend for now"
fi

# Install remaining requirements
pip install python-osc libtmux prompt-toolkit pytest pytest-asyncio pytest-benchmark 2>&1 | grep -E "(Successfully|Requirement already)"

echo ""
echo "========================================="
echo "✓ Setup complete!"
echo "========================================="
echo ""
echo "To activate the environment in future sessions:"
echo "  source venv/bin/activate"
echo ""
echo "To run tests:"
echo "  pytest tests/"
echo ""
echo "To check audio setup:"
echo "  python3 -c 'import sounddevice as sd; print(sd.query_devices())'"
echo ""