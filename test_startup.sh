#!/bin/bash
# Test the startup script in a simulated Pi environment
# This allows testing on your dev machine before deploying to actual Pi

set -e

echo "================================================"
echo "Testing MatchCaller Startup (Simulated Pi)"
echo "================================================"

# Simulate Pi environment
export MATCHCALLER_DIR="$(pwd)"
export SHORT_URL="abbey"
export EVENT_TYPE="singles"
export NETWORK_TIMEOUT=10  # Shorter timeout for testing

# Check if API token is set
if [ -z "$STARTGG_API_TOKEN" ]; then
    echo "⚠️  STARTGG_API_TOKEN not set, will test with demo mode"
    USE_DEMO=true
else
    echo "✅ STARTGG_API_TOKEN found: ***${STARTGG_API_TOKEN: -4}"
    USE_DEMO=false
fi

# Test 1: Network waiting
echo ""
echo "Test 1: Network Waiting"
echo "------------------------"
./wait_for_network "$NETWORK_TIMEOUT"
if [ $? -eq 0 ]; then
    echo "✅ Network test passed"
else
    echo "❌ Network test failed"
    exit 1
fi

# Test 2: Slug resolution
echo ""
echo "Test 2: Slug Resolution"
echo "------------------------"
if SLUG_PART=$(./resolve_slug "$SHORT_URL" 2>&1); then
    echo "✅ Slug resolved: $SLUG_PART"
    TOURNAMENT_SLUG="tournament/${SLUG_PART}/event/${EVENT_TYPE}"
    echo "   Full slug: $TOURNAMENT_SLUG"
else
    echo "❌ Slug resolution failed"
    echo "   Output: $SLUG_PART"
    exit 1
fi

# Test 3: Git status check
echo ""
echo "Test 3: Git Repository"
echo "------------------------"
if git status &>/dev/null; then
    echo "✅ Git repository valid"

    # Check for uncommitted changes
    if [ -n "$(git status --porcelain)" ]; then
        echo "⚠️  Uncommitted changes detected:"
        git status --short
    else
        echo "   Working directory clean"
    fi

    # Show current branch and latest commit
    BRANCH=$(git rev-parse --abbrev-ref HEAD)
    COMMIT=$(git rev-parse --short HEAD)
    echo "   Branch: $BRANCH"
    echo "   Commit: $COMMIT"
else
    echo "❌ Not a git repository"
fi

# Test 4: Python environment
echo ""
echo "Test 4: Python Environment"
echo "------------------------"
if python -c "import matchcaller" 2>/dev/null; then
    echo "✅ matchcaller module importable"
else
    echo "❌ matchcaller module not found"
    echo "   Try: pip install -e ."
    exit 1
fi

# Test 5: Demo mode execution (brief)
echo ""
echo "Test 5: MatchCaller Demo Mode"
echo "------------------------"
echo "Starting demo mode for 8 seconds..."
if timeout 8 python -m matchcaller --demo 2>&1 | head -20; then
    echo "✅ Demo mode started successfully"
else
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 124 ]; then
        # Timeout is expected
        echo "✅ Demo mode running (timed out as expected)"
    else
        echo "❌ Demo mode failed with exit code: $EXIT_CODE"
        exit 1
    fi
fi

# Test 6: Real API mode (if token available)
if [ "$USE_DEMO" = false ]; then
    echo ""
    echo "Test 6: Real API Connection"
    echo "------------------------"
    echo "Testing with real tournament slug for 8 seconds..."
    if timeout 8 python -m matchcaller --token "$STARTGG_API_TOKEN" --slug "$TOURNAMENT_SLUG" 2>&1 | head -20; then
        echo "✅ Real API mode started successfully"
    else
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 124 ]; then
            # Timeout is expected
            echo "✅ Real API mode running (timed out as expected)"
        else
            echo "❌ Real API mode failed with exit code: $EXIT_CODE"
            exit 1
        fi
    fi
else
    echo ""
    echo "Test 6: Skipped (no API token)"
fi

# Summary
echo ""
echo "================================================"
echo "✅ All Tests Passed!"
echo "================================================"
echo ""
echo "Ready to deploy to Raspberry Pi"
echo ""
echo "Next steps:"
echo "1. Copy this repo to /home/pi/matchcaller on the Pi"
echo "2. Run: ./scripts/setup_bashrc.sh"
echo "3. Reboot the Pi"
