#!/bin/bash

echo "Testing basic audio through PulseAudio..."

# Set PulseAudio
export PULSE_SERVER=tcp:172.21.240.1:4713

# First, test if we can make ANY sound through PulseAudio
echo "Installing sox for audio test..."
sudo apt-get install -y sox libsox-fmt-pulse 2>/dev/null || true

echo "Playing test tone (440Hz for 2 seconds)..."
play -n synth 2 sine 440

echo ""
echo "Did you hear a beep?"
echo "If yes: PulseAudio works, issue is with SuperCollider"
echo "If no: Check Windows Volume Mixer for 'sox' or 'play'"