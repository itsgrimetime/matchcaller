#!/bin/bash
# Setup or verify ~/.bashrc configuration for MatchCaller auto-start
# Run this on the Raspberry Pi after deploying the code

set -e

BASHRC="$HOME/.bashrc"
MATCHCALLER_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "================================================"
echo "MatchCaller .bashrc Setup"
echo "================================================"
echo ""
echo "Matchcaller directory: $MATCHCALLER_DIR"
echo "Target .bashrc: $BASHRC"
echo ""

# Check if .bashrc exists
if [ ! -f "$BASHRC" ]; then
    echo "Creating new .bashrc..."
    touch "$BASHRC"
fi

# Define the configuration block to add
read -r -d '' BASHRC_CONFIG <<'EOF' || true
# ===== MatchCaller Auto-Start =====
# Added by matchcaller/scripts/setup_bashrc.sh

# Set your start.gg API token here
export STARTGG_API_TOKEN="REPLACE_WITH_YOUR_TOKEN"

# Auto-start MatchCaller (only once per session)
if [ -z "$MATCHCALLER_STARTED" ]; then
    export MATCHCALLER_STARTED=1
    cd MATCHCALLER_DIR_PLACEHOLDER && ./start_matchcaller.sh
fi
# ===== End MatchCaller Auto-Start =====
EOF

# Replace placeholder with actual directory
BASHRC_CONFIG="${BASHRC_CONFIG//MATCHCALLER_DIR_PLACEHOLDER/$MATCHCALLER_DIR}"

# Check if MatchCaller config already exists
if grep -q "MatchCaller Auto-Start" "$BASHRC" 2>/dev/null; then
    echo "⚠️  MatchCaller configuration already exists in .bashrc"
    echo ""
    echo "Options:"
    echo "  1) Keep existing configuration (no changes)"
    echo "  2) Update configuration (replace with new version)"
    echo "  3) Remove configuration"
    echo "  4) Show current configuration"
    echo ""
    read -p "Choose [1-4]: " choice

    case $choice in
        1)
            echo "✅ Keeping existing configuration"
            ;;
        2)
            echo "📝 Updating configuration..."
            # Remove old config
            sed -i.bak '/# ===== MatchCaller Auto-Start =====/,/# ===== End MatchCaller Auto-Start =====/d' "$BASHRC"
            # Add new config
            echo "" >> "$BASHRC"
            echo "$BASHRC_CONFIG" >> "$BASHRC"
            echo "✅ Configuration updated"
            echo "   Backup saved to: ${BASHRC}.bak"
            ;;
        3)
            echo "🗑️  Removing configuration..."
            sed -i.bak '/# ===== MatchCaller Auto-Start =====/,/# ===== End MatchCaller Auto-Start =====/d' "$BASHRC"
            echo "✅ Configuration removed"
            echo "   Backup saved to: ${BASHRC}.bak"
            ;;
        4)
            echo ""
            echo "Current configuration:"
            echo "----------------------------------------"
            sed -n '/# ===== MatchCaller Auto-Start =====/,/# ===== End MatchCaller Auto-Start =====/p' "$BASHRC"
            echo "----------------------------------------"
            exit 0
            ;;
        *)
            echo "Invalid choice, exiting"
            exit 1
            ;;
    esac
else
    echo "Adding MatchCaller configuration to .bashrc..."
    echo "" >> "$BASHRC"
    echo "$BASHRC_CONFIG" >> "$BASHRC"
    echo "✅ Configuration added"
fi

echo ""
echo "================================================"
echo "Next Steps"
echo "================================================"
echo ""
echo "1. Edit your API token in .bashrc:"
echo "   nano ~/.bashrc"
echo "   (Find STARTGG_API_TOKEN and replace with your actual token)"
echo ""
echo "2. Test the configuration:"
echo "   source ~/.bashrc"
echo ""
echo "3. Or simply reboot:"
echo "   sudo reboot"
echo ""

# Check if token is still the placeholder
if grep -q "REPLACE_WITH_YOUR_TOKEN" "$BASHRC" 2>/dev/null; then
    echo "⚠️  WARNING: API token not set yet!"
    echo "   Edit ~/.bashrc and set STARTGG_API_TOKEN"
    echo ""
fi
