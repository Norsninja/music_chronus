#!/bin/bash

echo "==================================="
echo "Starting TidalCycles Music Session"
echo "==================================="

# Set PulseAudio
export PULSE_SERVER=tcp:172.21.240.1:4713

# Clean up
tmux kill-server 2>/dev/null
pkill scsynth 2>/dev/null
pkill sclang 2>/dev/null
sleep 2

# Start SuperDirt with PulseAudio
echo "1. Starting SuperDirt..."
tmux new-session -d -s superdirt "export PULSE_SERVER=tcp:172.21.240.1:4713 && sclang /home/norsninja/music_chronus/start_superdirt_fixed.scd"

echo "   Waiting for SuperDirt (20 seconds)..."
sleep 20

# Start TidalCycles
echo "2. Starting TidalCycles..."
tmux new-session -d -s music "source ~/.ghcup/env && ghci -ghci-script /home/norsninja/music_chronus/BootTidal.hs"

sleep 5

echo ""
echo "==================================="
echo "Ready! Join with: tmux attach -t music"
echo "==================================="