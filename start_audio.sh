#!/bin/bash

echo "Setting up audio system for TidalCycles..."

# Check if JACK is already running
if pgrep -x "jackd" > /dev/null; then
    echo "JACK is already running"
else
    echo "Starting JACK audio server..."
    # Start JACK with reasonable settings for live coding
    # -d alsa: use ALSA driver
    # -r 44100: sample rate
    # -p 256: period size (lower = less latency)
    # -n 3: number of periods
    jackd -d alsa -r 44100 -p 256 -n 3 &
    sleep 2
    
    if pgrep -x "jackd" > /dev/null; then
        echo "JACK started successfully!"
    else
        echo "Failed to start JACK. Trying with dummy driver for testing..."
        jackd -d dummy -r 44100 -p 256 &
        sleep 2
    fi
fi

# Check if PulseAudio is running and might conflict
if pgrep -x "pulseaudio" > /dev/null; then
    echo "Warning: PulseAudio is running and might conflict with JACK"
    echo "You may need to: pasuspender -- jackd -d alsa -r 44100 -p 256 -n 3"
fi

echo ""
echo "Audio setup complete. Now restart SuperDirt."