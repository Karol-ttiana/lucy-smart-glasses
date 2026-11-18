#!/bin/bash
# Updated Setup script for Lucy Smart Glasses - Raspberry Pi 5 with Groq

echo "========================================"
echo "Lucy Smart Glasses - Raspberry Pi Setup"
echo "========================================"

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "⚠️  Warning: This script is designed for Raspberry Pi"
    echo "Continuing anyway..."
fi

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed"
    echo "Please install Python 3: sudo apt-get install python3 python3-pip"
    exit 1
fi

echo "✓ Python 3 found"

# Update system packages
echo ""
echo "Updating system packages..."
sudo apt-get update

# Install system dependencies
echo ""
echo "Installing system dependencies..."
sudo apt-get install -y \
    portaudio19-dev \
    python3-pyaudio \
    espeak \
    libopencv-dev \
    python3-opencv \
    libatlas-base-dev \
    libopenblas-dev \
    libcap-dev \
    python3-libgpiod \
    python3-lgpio \
    python3-pip

# Install Python packages globally (Raspberry Pi 5 doesn't need venv for this)
echo ""
echo "Installing Python dependencies..."
pip3 install --break-system-packages -r requirements.txt

# Download Vosk model for wake word detection
echo ""
echo "Downloading Vosk speech recognition model..."
mkdir -p ~/.lucy
cd ~/.lucy

if [ ! -d "vosk-model-small-en-us-0.15" ]; then
    echo "Downloading Vosk model..."
    wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
    unzip vosk-model-small-en-us-0.15.zip
    rm vosk-model-small-en-us-0.15.zip
    echo "✓ Vosk model downloaded"
else
    echo "✓ Vosk model already exists"
fi

cd - > /dev/null

# Check for Groq API key
echo ""
echo "Checking Groq API configuration..."
if [ -f ".env" ]; then
    echo "✓ .env file found"
    if grep -q "GROQ_API_KEY" .env; then
        echo "✓ GROQ_API_KEY configured"
    else
        echo "⚠️  GROQ_API_KEY not found in .env"
    fi
else
    echo "⚠️  .env file not found"
    echo ""
    echo "To set up Groq API:"
    echo "1. Get your API key from: https://console.groq.com/keys"
    echo "2. Create .env file with: echo 'GROQ_API_KEY=your-key-here' > .env"
fi

echo ""
echo "========================================"
echo "Setup complete!"
echo "========================================"
echo ""
echo "To run Lucy Smart Glasses:"
echo "  ./start.sh"
echo ""
echo "Or directly:"
echo "  python3 main.py"
echo ""
echo "Make sure:"
echo "  ✓ Your camera is connected (USB or Pi Camera)"
echo "  ✓ Your microphone is working"
echo "  ✓ GROQ_API_KEY is set in .env file"
echo "  ✓ GPIO button on pin 17 (optional)"
echo ""
echo "For Pi Camera Module, edit config.py and set USE_PI_CAMERA = True"
echo ""
