#!/bin/bash
# Verify deployment is ready for production on Raspberry Pi
# Run this on the Pi to check everything is configured correctly

MATCHCALLER_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$MATCHCALLER_DIR"

echo "================================================"
echo "MatchCaller Deployment Verification"
echo "================================================"
echo ""

ERRORS=0
WARNINGS=0

# Check 1: Required scripts exist and are executable
echo "✓ Checking required scripts..."
REQUIRED_SCRIPTS=(
    "wait_for_network"
    "resolve_slug"
    "start_matchcaller.sh"
    "scripts/setup_bashrc.sh"
)

for script in "${REQUIRED_SCRIPTS[@]}"; do
    if [ ! -f "$script" ]; then
        echo "  ❌ Missing: $script"
        ((ERRORS++))
    elif [ ! -x "$script" ]; then
        echo "  ⚠️  Not executable: $script"
        ((WARNINGS++))
        chmod +x "$script" 2>/dev/null && echo "     Fixed: made executable"
    else
        echo "  ✅ $script"
    fi
done

# Check 2: Python environment
echo ""
echo "✓ Checking Python environment..."
if command -v python &> /dev/null || command -v python3 &> /dev/null; then
    PYTHON_CMD=$(command -v python3 || command -v python)
    echo "  ✅ Python: $PYTHON_CMD"

    # Check if matchcaller module can be imported
    if $PYTHON_CMD -c "import matchcaller" 2>/dev/null; then
        echo "  ✅ matchcaller module importable"
    else
        echo "  ❌ matchcaller module not found"
        echo "     Try: pip install -e ."
        ((ERRORS++))
    fi

    # Check required dependencies
    for module in textual aiohttp requests; do
        if $PYTHON_CMD -c "import $module" 2>/dev/null; then
            echo "  ✅ $module installed"
        else
            echo "  ❌ $module not installed"
            ((ERRORS++))
        fi
    done
else
    echo "  ❌ Python not found"
    ((ERRORS++))
fi

# Check 3: Git repository
echo ""
echo "✓ Checking Git repository..."
if git rev-parse --git-dir > /dev/null 2>&1; then
    echo "  ✅ Git repository valid"

    BRANCH=$(git rev-parse --abbrev-ref HEAD)
    COMMIT=$(git rev-parse --short HEAD)
    echo "     Branch: $BRANCH"
    echo "     Commit: $COMMIT"

    # Check for uncommitted changes
    if [ -n "$(git status --porcelain)" ]; then
        echo "  ⚠️  Uncommitted changes present"
        ((WARNINGS++))
    fi

    # Check if we can fetch from remote
    if git fetch origin --dry-run 2>/dev/null; then
        echo "  ✅ Can fetch from remote"
    else
        echo "  ⚠️  Cannot fetch from remote (auto-update will be skipped)"
        ((WARNINGS++))
    fi
else
    echo "  ⚠️  Not a git repository (auto-update will be disabled)"
    ((WARNINGS++))
fi

# Check 4: Network connectivity
echo ""
echo "✓ Checking network connectivity..."
if ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1; then
    echo "  ✅ Internet connection active"

    if ping -c 1 -W 2 start.gg >/dev/null 2>&1; then
        echo "  ✅ start.gg reachable"

        # Test slug resolution
        if SLUG=$(./resolve_slug abbey 2>/dev/null); then
            echo "  ✅ Slug resolution working: $SLUG"
        else
            echo "  ❌ Slug resolution failed"
            ((ERRORS++))
        fi
    else
        echo "  ⚠️  start.gg not reachable"
        ((WARNINGS++))
    fi
else
    echo "  ⚠️  No internet connection (test may be incomplete)"
    ((WARNINGS++))
fi

# Check 5: API Token configuration
echo ""
echo "✓ Checking API token configuration..."
if [ -n "$STARTGG_API_TOKEN" ]; then
    if [ "$STARTGG_API_TOKEN" = "REPLACE_WITH_YOUR_TOKEN" ]; then
        echo "  ❌ API token not set (still placeholder)"
        ((ERRORS++))
    else
        echo "  ✅ API token configured: ***${STARTGG_API_TOKEN: -4}"
    fi
else
    echo "  ⚠️  STARTGG_API_TOKEN not set in environment"
    echo "     Check ~/.bashrc or set manually"
    ((WARNINGS++))
fi

# Check 6: .bashrc configuration
echo ""
echo "✓ Checking .bashrc configuration..."
if [ -f "$HOME/.bashrc" ]; then
    if grep -q "MatchCaller Auto-Start" "$HOME/.bashrc" 2>/dev/null; then
        echo "  ✅ .bashrc configured for auto-start"

        if grep -q "REPLACE_WITH_YOUR_TOKEN" "$HOME/.bashrc" 2>/dev/null; then
            echo "  ❌ API token still has placeholder in .bashrc"
            echo "     Edit ~/.bashrc and set your actual token"
            ((ERRORS++))
        fi
    else
        echo "  ⚠️  .bashrc not configured for auto-start"
        echo "     Run: ./scripts/setup_bashrc.sh"
        ((WARNINGS++))
    fi
else
    echo "  ⚠️  No .bashrc file found"
    ((WARNINGS++))
fi

# Summary
echo ""
echo "================================================"
echo "Verification Summary"
echo "================================================"
echo ""

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo "✅ All checks passed! Ready for production."
    echo ""
    echo "To start:"
    echo "  source ~/.bashrc    (test now)"
    echo "  sudo reboot         (test auto-start)"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo "⚠️  $WARNINGS warning(s) found"
    echo "Deployment will work but some features may be limited."
    exit 0
else
    echo "❌ $ERRORS error(s) and $WARNINGS warning(s) found"
    echo "Please fix errors before deploying."
    exit 1
fi
