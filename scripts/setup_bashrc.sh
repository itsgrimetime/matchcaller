#!/bin/bash
# Set up a Raspberry Pi for matchcaller. Idempotent — safe to re-run.
#
# Steps:
#   1. Add the matchcaller auto-start block to ~/.bashrc (with the tty1 guard
#      and a pre-launch display-state snapshot for diagnostics).
#   2. Make scripts/ entries executable.
#   3. Install + enable the matchcaller-display-log.service systemd unit so
#      boot-time display state is captured before the TUI runs.

set -e

BASHRC="$HOME/.bashrc"
MATCHCALLER_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_SCRIPT="$MATCHCALLER_DIR/scripts/log_display_state.sh"
SERVICE_TEMPLATE="$MATCHCALLER_DIR/scripts/matchcaller-display-log.service"
SERVICE_NAME="matchcaller-display-log.service"
SERVICE_DEST="/etc/systemd/system/$SERVICE_NAME"

echo "================================================"
echo "MatchCaller Pi Setup"
echo "================================================"
echo ""
echo "Matchcaller directory: $MATCHCALLER_DIR"
echo "Target .bashrc: $BASHRC"
echo ""

# --- Step 1: ~/.bashrc auto-start block -----------------------------------

if [ ! -f "$BASHRC" ]; then
    echo "Creating new .bashrc..."
    touch "$BASHRC"
fi

read -r -d '' BASHRC_CONFIG <<'EOF' || true
# ===== MatchCaller Auto-Start =====
# Added by matchcaller/scripts/setup_bashrc.sh

# Set your start.gg API token here
export STARTGG_API_TOKEN="REPLACE_WITH_YOUR_TOKEN"

# Auto-start MatchCaller (only once per session, only on a real TTY).
# Login over SSH gets a /dev/pts/* and won't trigger this.
if [ -z "$MATCHCALLER_STARTED" ] && [[ $(tty) == /dev/tty* ]]; then
    export MATCHCALLER_STARTED=1
    cd MATCHCALLER_DIR_PLACEHOLDER || exit
    # Snapshot display/console state right before the TUI launches, so we
    # can compare it to the boot-time snapshot from the systemd unit and
    # diagnose intermittent HDMI/resolution issues.
    ./scripts/log_display_state.sh "tty1-bashrc-pre" >/dev/null 2>&1 || true
    ./start_matchcaller.sh
fi
# ===== End MatchCaller Auto-Start =====
EOF
BASHRC_CONFIG="${BASHRC_CONFIG//MATCHCALLER_DIR_PLACEHOLDER/$MATCHCALLER_DIR}"

if grep -q "MatchCaller Auto-Start" "$BASHRC" 2>/dev/null; then
    echo "[1/3] .bashrc already has a MatchCaller block."
    echo ""
    echo "  1) Keep existing"
    echo "  2) Update (replace block, preserve token from old block)"
    echo "  3) Remove"
    echo "  4) Show current"
    echo ""
    read -p "Choose [1-4]: " choice

    case $choice in
        1)
            echo "Keeping existing .bashrc block."
            ;;
        2)
            # Preserve the user's existing token if it's not the placeholder.
            EXISTING_TOKEN=$(grep -E '^export STARTGG_API_TOKEN=' "$BASHRC" | head -1 | sed -E 's/^export STARTGG_API_TOKEN="?([^"]*)"?$/\1/')
            if [ -n "$EXISTING_TOKEN" ] && [ "$EXISTING_TOKEN" != "REPLACE_WITH_YOUR_TOKEN" ]; then
                BASHRC_CONFIG="${BASHRC_CONFIG//REPLACE_WITH_YOUR_TOKEN/$EXISTING_TOKEN}"
            fi
            sed -i.bak '/# ===== MatchCaller Auto-Start =====/,/# ===== End MatchCaller Auto-Start =====/d' "$BASHRC"
            printf '\n%s\n' "$BASHRC_CONFIG" >> "$BASHRC"
            echo "Updated .bashrc (backup: ${BASHRC}.bak)"
            ;;
        3)
            sed -i.bak '/# ===== MatchCaller Auto-Start =====/,/# ===== End MatchCaller Auto-Start =====/d' "$BASHRC"
            echo "Removed .bashrc block (backup: ${BASHRC}.bak)"
            exit 0
            ;;
        4)
            echo ""
            sed -n '/# ===== MatchCaller Auto-Start =====/,/# ===== End MatchCaller Auto-Start =====/p' "$BASHRC"
            exit 0
            ;;
        *)
            echo "Invalid choice."
            exit 1
            ;;
    esac
else
    echo "[1/3] Adding MatchCaller auto-start block to .bashrc..."
    printf '\n%s\n' "$BASHRC_CONFIG" >> "$BASHRC"
fi

# --- Step 2: make scripts executable --------------------------------------

echo ""
echo "[2/3] Marking scripts executable..."
chmod +x "$MATCHCALLER_DIR/scripts/"*.sh 2>/dev/null
chmod +x "$MATCHCALLER_DIR/start_matchcaller.sh" 2>/dev/null
chmod +x "$MATCHCALLER_DIR/wait_for_network" 2>/dev/null
chmod +x "$MATCHCALLER_DIR/resolve_slug" 2>/dev/null

# --- Step 3: install/enable the boot-time display-log systemd unit --------

echo ""
echo "[3/3] Installing $SERVICE_NAME..."

if [ ! -f "$SERVICE_TEMPLATE" ]; then
    echo "  Skip: template not found at $SERVICE_TEMPLATE"
elif [ ! -f "$LOG_SCRIPT" ]; then
    echo "  Skip: $LOG_SCRIPT missing"
elif ! command -v systemctl >/dev/null 2>&1; then
    echo "  Skip: systemctl not available (not a systemd host)"
else
    # Materialize the unit file from the template, substituting the absolute
    # path to the log script. We use a temp file then sudo-install it.
    TMP_UNIT=$(mktemp)
    sed "s|__LOG_SCRIPT_PATH__|$LOG_SCRIPT|g" "$SERVICE_TEMPLATE" > "$TMP_UNIT"

    if sudo -n install -m 644 "$TMP_UNIT" "$SERVICE_DEST"; then
        sudo -n systemctl daemon-reload
        sudo -n systemctl enable "$SERVICE_NAME" >/dev/null
        echo "  Installed and enabled $SERVICE_NAME"
        echo "  Will run on next boot. To run now: sudo systemctl start $SERVICE_NAME"
    else
        echo "  Failed to install unit (need passwordless sudo)."
        echo "  Manual install:"
        echo "    sudo cp $TMP_UNIT $SERVICE_DEST"
        echo "    sudo systemctl daemon-reload"
        echo "    sudo systemctl enable $SERVICE_NAME"
    fi
    rm -f "$TMP_UNIT"
fi

# --- Summary --------------------------------------------------------------

echo ""
echo "================================================"
echo "Done."
echo "================================================"
echo ""
echo "Display-state log:  ~/matchcaller/logs/display_state.log"
echo "TUI app log:        ~/matchcaller/logs/tournament_debug.log"
echo ""
echo "Next steps:"
echo "  1) Set your token in ~/.bashrc (look for STARTGG_API_TOKEN)"
echo "  2) sudo reboot   # to verify boot-time logging fires"
echo ""

if grep -q "REPLACE_WITH_YOUR_TOKEN" "$BASHRC" 2>/dev/null; then
    echo "WARNING: API token is still the placeholder."
    echo "         Edit ~/.bashrc and set STARTGG_API_TOKEN."
    echo ""
fi
