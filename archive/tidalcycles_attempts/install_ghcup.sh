#!/bin/bash
# Non-interactive GHCup installation

# First, check if dependencies are installed
echo "Checking system dependencies..."
DEPS="build-essential curl libffi-dev libffi8 libgmp-dev libgmp10 libncurses-dev pkg-config"
MISSING=""
for dep in $DEPS; do
    if ! dpkg -l | grep -q "^ii  $dep"; then
        MISSING="$MISSING $dep"
    fi
done

if [ ! -z "$MISSING" ]; then
    echo "Missing dependencies:$MISSING"
    echo "Please install with: sudo apt-get install$MISSING"
    exit 1
fi

# Download GHCup if not already installed
if [ ! -f "$HOME/.ghcup/bin/ghcup" ]; then
    echo "Downloading GHCup..."
    curl --proto '=https' --tlsv1.2 -sSf https://get-ghcup.haskell.org > /tmp/ghcup-install.sh
    
    # Run in non-interactive mode
    BOOTSTRAP_HASKELL_NONINTERACTIVE=1 \
    BOOTSTRAP_HASKELL_GHC_VERSION=recommended \
    BOOTSTRAP_HASKELL_CABAL_VERSION=recommended \
    BOOTSTRAP_HASKELL_INSTALL_STACK=0 \
    BOOTSTRAP_HASKELL_INSTALL_HLS=0 \
    BOOTSTRAP_HASKELL_ADJUST_BASHRC=1 \
    sh /tmp/ghcup-install.sh
else
    echo "GHCup already installed"
fi

# Source the environment
source "$HOME/.ghcup/env"

echo "GHCup installation complete!"
echo "Versions installed:"
ghc --version
cabal --version

echo ""
echo "Next steps:"
echo "1. Source the environment: source ~/.ghcup/env"
echo "2. Update cabal: cabal update"
echo "3. Install TidalCycles: cabal install tidal --lib"