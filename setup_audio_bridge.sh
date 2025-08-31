#!/bin/bash

echo "Setting up JACK → PulseAudio bridge for SuperCollider"
echo "======================================================"

# Set PulseAudio server
export PULSE_SERVER=tcp:172.21.240.1:4713

# Kill any existing JACK
pkill jackd 2>/dev/null
sleep 2

# Start JACK with dummy driver (since we have no real hardware in WSL2)
echo "Starting JACK with dummy driver..."
jackd -d dummy -r 44100 -p 1024 &
sleep 3

# Load PulseAudio JACK modules to bridge JACK to PulseAudio
echo "Creating bridge from JACK to PulseAudio..."
pactl load-module module-jack-sink channels=2
pactl load-module module-jack-source channels=2 connect=0

echo ""
echo "Testing JACK..."
jack_lsp

echo ""
echo "Bridge setup complete!"
echo "Now SuperCollider can use JACK, and JACK routes to PulseAudio → Windows"
echo ""
echo "Next steps:"
echo "1. Start SuperCollider IDE: scide"
echo "2. In IDE, run: s.boot"
echo "3. Then run: SuperDirt.start"