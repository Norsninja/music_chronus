#!/bin/bash

echo "==================================="
echo "TidalCycles Test Script"
echo "==================================="
echo ""
echo "This will:"
echo "1. Start SuperCollider with SuperDirt"
echo "2. Start TidalCycles in a separate terminal"
echo "3. Play a test pattern"
echo ""
echo "Press Enter to continue..."
read

# Start SuperCollider with SuperDirt in background
echo "Starting SuperDirt..."
cat > /tmp/start_superdirt.scd << 'EOF'
s.waitForBoot {
    ~dirt = SuperDirt(2, s);
    ~dirt.loadSoundFiles;
    s.sync;
    ~dirt.start(57120, 0 ! 12);
    "SuperDirt is ready!".postln;
};
EOF

# Start SuperCollider in a tmux session
tmux new-session -d -s superdirt "sclang /tmp/start_superdirt.scd"

echo "Waiting for SuperDirt to start (10 seconds)..."
sleep 10

# Start TidalCycles in another tmux session
echo "Starting TidalCycles..."
tmux new-session -d -s tidal "source ~/.ghcup/env && ghci -ghci-script /home/norsninja/music_chronus/BootTidal.hs"

echo "Waiting for TidalCycles to load (5 seconds)..."
sleep 5

# Send a test pattern
echo "Sending test pattern: d1 $ sound \"bd sn\""
tmux send-keys -t tidal "d1 $ sound \"bd sn\"" Enter

echo ""
echo "==================================="
echo "Test Complete!"
echo "==================================="
echo ""
echo "You should hear a kick-snare pattern playing."
echo ""
echo "Useful commands:"
echo "  View SuperDirt:  tmux attach -t superdirt"
echo "  View Tidal:      tmux attach -t tidal"
echo "  Stop pattern:    tmux send-keys -t tidal 'hush' Enter"
echo "  Kill sessions:   tmux kill-session -t tidal && tmux kill-session -t superdirt"
echo ""