#!/bin/bash

echo "==================================="
echo "TidalCycles + SuperDirt with PulseAudio"
echo "==================================="
echo ""

# Set PulseAudio server
export PULSE_SERVER=tcp:$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):4713

# Test PulseAudio connection
echo "Testing audio connection to Windows..."
if pactl info > /dev/null 2>&1; then
    echo "✓ PulseAudio connected successfully!"
else
    echo "✗ PulseAudio connection failed!"
    echo "  Make sure PulseAudio is running on Windows"
    exit 1
fi

# Kill any existing sessions
echo "Cleaning up old sessions..."
tmux kill-session -t music 2>/dev/null
tmux kill-session -t superdirt 2>/dev/null
pkill scsynth 2>/dev/null
pkill sclang 2>/dev/null
sleep 2

# Start SuperCollider with PulseAudio
echo "Starting SuperDirt audio engine..."
cat > /tmp/start_superdirt_pulse.scd << 'EOF'
// Configure for PulseAudio
s.options.numBuffers = 1024 * 256;
s.options.memSize = 8192 * 32;
s.options.numWireBus = 128;
s.options.maxNodes = 1024 * 32;
s.options.numOutputBusChannels = 2;
s.options.numInputBusChannels = 2;

s.waitForBoot {
    ~dirt = SuperDirt(2, s);
    ~dirt.loadSoundFiles;
    s.sync;
    ~dirt.start(57120, 0 ! 12);
    "
    ==========================================
    SuperDirt is ready with PulseAudio!
    Audio is routing through Windows
    ==========================================
    ".postln;
};
EOF

tmux new-session -d -s superdirt "export PULSE_SERVER=tcp:\$(cat /etc/resolv.conf | grep nameserver | awk '{print \$2}'):4713 && sclang /tmp/start_superdirt_pulse.scd"

echo "Waiting for SuperDirt to initialize (15 seconds)..."
sleep 15

# Start TidalCycles
echo "Starting TidalCycles..."
tmux new-session -d -s music "source ~/.ghcup/env && ghci -ghci-script /home/norsninja/music_chronus/BootTidal.hs"
sleep 5

echo ""
echo "==================================="
echo "Ready to make music!"
echo "==================================="
echo ""
echo "Join the session with:"
echo "  tmux attach -t music"
echo ""
echo "Basic commands:"
echo "  d1 $ sound \"bd sn\"    -- Simple beat"
echo "  hush                  -- Stop all sounds"
echo "  Ctrl+B, D            -- Detach from tmux"
echo ""
echo "Let's create together!"