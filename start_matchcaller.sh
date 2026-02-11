#!/bin/bash
# Complete startup script for matchcaller with network waiting and slug resolution
# Designed for Raspberry Pi auto-start via ~/.bashrc or systemd

set -e  # Exit on error


# Configuration
MATCHCALLER_DIR="/home/abbey/matchcaller"
SHORT_URL="abbey"
EVENT_FILTER="${EVENT_FILTER:-melee}"
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
# Activate virtual environment if it exists
if [ -d "/home/abbey/matchcaller-venv" ]; then
    source "/home/abbey/matchcaller-venv/bin/activate"
fi


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

# Step 2: Update code from git (if this is a git repo)
if git rev-parse --git-dir > /dev/null 2>&1; then
    echo "📦 Updating from git..."

    # Store current commit for comparison
    BEFORE_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

    # Fetch latest changes
    if git fetch origin 2>/dev/null; then
        # Get the remote branch name
        CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

        # Check if we have a remote tracking branch
        if git rev-parse --verify "origin/$CURRENT_BRANCH" >/dev/null 2>&1; then
            # Check if there are updates
            LOCAL=$(git rev-parse HEAD)
            REMOTE=$(git rev-parse "origin/$CURRENT_BRANCH")

            if [ "$LOCAL" != "$REMOTE" ]; then
                echo "   📥 Updates available, pulling..."

                # Stash any local changes
                git stash push -m "Auto-stash before update" 2>/dev/null || true

                # Pull the latest changes
                if git pull origin "$CURRENT_BRANCH" 2>/dev/null; then
                    AFTER_COMMIT=$(git rev-parse --short HEAD)
                    echo "   ✅ Updated: $BEFORE_COMMIT → $AFTER_COMMIT"
                else
                    echo "   ⚠️  Pull failed, continuing with current version"
                fi
            else
                echo "   ✅ Already up to date ($BEFORE_COMMIT)"
            fi
        else
            echo "   ⚠️  No remote tracking branch, skipping update"
        fi
    else
        echo "   ⚠️  Git fetch failed, continuing with current version"
    fi
else
    echo "⚠️  Not a git repository, skipping update"
fi

# Step 3: Launch matchcaller (slug resolution handled by Python)
echo "🚀 Starting matchcaller with short URL: ${SHORT_URL}, filter: ${EVENT_FILTER}..."
sleep 1

exec python -m matchcaller --token "$API_TOKEN" --short-url "$SHORT_URL" --event-filter "$EVENT_FILTER"
