#!/bin/bash
# Complete startup script for matchcaller with network waiting and slug resolution
# Designed for Raspberry Pi auto-start via ~/.bashrc or systemd

set -e  # Exit on error

# Configuration
MATCHCALLER_DIR="/home/pi/matchcaller"
SHORT_URL="abbey"
EVENT_TYPE="singles"
NETWORK_TIMEOUT=120  # 2 minutes
API_TOKEN="${STARTGG_API_TOKEN:-}"  # Read from environment or set below

# Override with your actual token if not using environment variable
if [ -z "$API_TOKEN" ]; then
    echo "ERROR: STARTGG_API_TOKEN not set"
    echo "Set it in environment or edit this script"
    exit 1
fi

# Navigate to matchcaller directory
cd "$MATCHCALLER_DIR"

echo "================================================"
echo "MatchCaller Tournament Display"
echo "================================================"

# Step 1: Wait for network connectivity
echo "⏳ Waiting for network connectivity (timeout: ${NETWORK_TIMEOUT}s)..."
./wait_for_network "$NETWORK_TIMEOUT"

if [ $? -ne 0 ]; then
    echo "❌ Network connection timeout"
    echo "ERROR: No network connection" > /dev/tty1 2>/dev/null || true
    exit 1
fi

echo "✅ Network connected"

# Step 2: Resolve tournament slug
echo "🔍 Resolving tournament from start.gg/${SHORT_URL}..."
if SLUG_PART=$(./resolve_slug "$SHORT_URL" 2>/dev/null); then
    TOURNAMENT_SLUG="tournament/${SLUG_PART}/event/${EVENT_TYPE}"
    echo "✅ Resolved: $TOURNAMENT_SLUG"
else
    echo "❌ Failed to resolve slug"
    echo "ERROR: Could not resolve tournament" > /dev/tty1 2>/dev/null || true
    exit 1
fi

# Step 3: Launch matchcaller
echo "🚀 Starting matchcaller..."
sleep 1

exec python -m matchcaller --token "$API_TOKEN" --slug "$TOURNAMENT_SLUG"
