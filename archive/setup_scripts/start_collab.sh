#!/bin/bash

echo "==================================="
echo "Starting Collaborative Music Session"
echo "==================================="
echo ""
echo "Setting up our shared creative space..."
echo ""

# Kill any existing sessions
tmux kill-session -t music 2>/dev/null
tmux kill-session -t superdirt 2>/dev/null

# Start SuperDirt in background
echo "1. Starting SuperDirt audio engine..."
cat > /tmp/start_superdirt.scd << 'EOF'
s.waitForBoot {
    ~dirt = SuperDirt(2, s);
    ~dirt.loadSoundFiles;
    s.sync;
    ~dirt.start(57120, 0 ! 12);
    "
    ==========================================
    SuperDirt is ready for our collaboration!
    ==========================================
    ".postln;
};
EOF

tmux new-session -d -s superdirt "sclang /tmp/start_superdirt.scd"
sleep 8

# Create main music session with TidalCycles
echo "2. Starting TidalCycles live coding environment..."
tmux new-session -d -s music "source ~/.ghcup/env && ghci -ghci-script /home/norsninja/music_chronus/BootTidal.hs"
sleep 3

# Send initial welcome
tmux send-keys -t music "-- Welcome to our collaborative music session!" Enter
tmux send-keys -t music "-- Chronus Nexus & Human, creating together" Enter
tmux send-keys -t music "" Enter

echo ""
echo "==================================="
echo "Session Ready!"
echo "==================================="
echo ""
echo "To begin our collaboration:"
echo "  tmux attach -t music"
echo ""
echo "I'll be able to send patterns to this same session,"
echo "and you'll see everything I write in real-time."
echo "You can also type directly to modify or stop patterns."
echo ""
echo "Basic commands:"
echo "  hush           -- Stop all sounds"
echo "  d1 $ silence   -- Stop just track 1"
echo "  Ctrl+B, D      -- Detach from tmux (session keeps running)"
echo ""
echo "Ready to make music together!"