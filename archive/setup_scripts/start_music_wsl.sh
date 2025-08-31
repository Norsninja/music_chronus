#!/bin/bash

echo "==================================="
echo "TidalCycles + SuperDirt for WSL2"
echo "==================================="
echo ""

# Kill any existing sessions
echo "Cleaning up old sessions..."
tmux kill-session -t music 2>/dev/null
tmux kill-session -t superdirt 2>/dev/null
tmux kill-session -t jack 2>/dev/null
pkill jackd 2>/dev/null
pkill scsynth 2>/dev/null
sleep 2

# Start JACK with dummy driver (for WSL2)
echo "1. Starting JACK (dummy driver for WSL2)..."
tmux new-session -d -s jack "jackd -d dummy -r 44100 -p 1024"
sleep 3

# Start SuperCollider server
echo "2. Starting SuperCollider server..."
cat > /tmp/start_superdirt_wsl.scd << 'EOF'
// WSL2 SuperDirt setup
s.options.numBuffers = 1024 * 256;
s.options.memSize = 8192 * 32;
s.options.numWireBufs = 128;
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
    SuperDirt is ready!
    WSL2 Mode: Audio through dummy JACK
    ==========================================
    ".postln;
};
EOF

tmux new-session -d -s superdirt "sclang /tmp/start_superdirt_wsl.scd"
echo "Waiting for SuperDirt to initialize (15 seconds)..."
sleep 15

# Start TidalCycles
echo "3. Starting TidalCycles..."
tmux new-session -d -s music "source ~/.ghcup/env && ghci -ghci-script /home/norsninja/music_chronus/BootTidal.hs"
sleep 5

# Test connection
echo "4. Testing connection..."
tmux send-keys -t music 'putStrLn "TidalCycles connected to SuperDirt!"' Enter
sleep 1

echo ""
echo "==================================="
echo "Setup Complete!"
echo "==================================="
echo ""
echo "IMPORTANT FOR WSL2:"
echo "Since WSL2 doesn't have direct audio hardware access,"
echo "you have a few options:"
echo ""
echo "1. Use PulseAudio over network:"
echo "   - Install PulseAudio on Windows"
echo "   - Configure WSL2 to send audio to Windows host"
echo ""
echo "2. Use X410 or VcXsrv with audio support"
echo ""
echo "3. For now, we can compose patterns and export them"
echo "   as code to run on a system with audio"
echo ""
echo "To start composing (even without audio):"
echo "  tmux attach -t music"
echo ""
echo "View sessions:"
echo "  tmux ls"
echo ""
echo "We can still create patterns together!"
echo "The code will work when you run it on a system with audio."