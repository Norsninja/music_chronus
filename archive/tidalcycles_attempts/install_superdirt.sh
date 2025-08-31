#!/bin/bash
# Install SuperDirt in SuperCollider

echo "Installing SuperDirt in SuperCollider..."
echo ""
echo "This will open SuperCollider IDE. Please:"
echo "1. Wait for SuperCollider to open"
echo "2. In the editor, type or paste:"
echo ""
echo 'Quarks.checkForUpdates({Quarks.install("SuperDirt", "v1.7.3"); thisProcess.recompile()});'
echo ""
echo "3. Place cursor on that line and press Ctrl+Enter to execute"
echo "4. Wait for installation to complete (check Post window for progress)"
echo "5. When done, you can close SuperCollider"
echo ""
echo "Alternatively, you can run this command-line version:"
echo ""

# Try command-line installation
sclang << EOF
Quarks.checkForUpdates({
    Quarks.install("SuperDirt", "v1.7.3");
    "SuperDirt installation started...".postln;
    0.exit;
});
EOF

echo ""
echo "If the command-line version didn't work, please use the GUI method above."
echo "Press Enter to open SuperCollider IDE, or Ctrl+C to skip..."
read

# Open SuperCollider IDE
scide &