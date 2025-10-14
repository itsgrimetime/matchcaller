# Deployment System Changelog

Summary of new deployment infrastructure added for Raspberry Pi auto-start.

## What Was Added

### Core Scripts

1. **`wait_for_network`** - Network connectivity checker
   - Waits for internet before proceeding
   - Configurable timeout (default 60s)
   - Tests both 8.8.8.8 and start.gg connectivity

2. **`resolve_slug`** - Tournament slug resolver (enhanced)
   - Converts short URLs to tournament slugs
   - Example: `abbey` → `melee-abbey-tavern-114`
   - Can be called from bash or Python

3. **`start_matchcaller.sh`** - Complete startup orchestrator
   - Waits for network (120s timeout)
   - Auto-updates code via git pull
   - Resolves tournament from short URL
   - Launches matchcaller TUI
   - Designed for ~/.bashrc auto-start

### Testing & Verification

4. **`test_startup.sh`** - Pre-deployment testing
   - Simulates Pi environment on dev machine
   - Tests network, slug resolution, Python env
   - Runs demo mode and API mode
   - Validates git repository
   - Exit codes for CI/CD integration

5. **`scripts/setup_bashrc.sh`** - Auto-start configuration
   - Interactive .bashrc setup
   - Add/update/remove configuration
   - Validates API token
   - Shows current config

6. **`scripts/verify_deployment.sh`** - Deployment verification
   - Checks all requirements
   - Validates scripts, Python, git
   - Tests network and API
   - Reports errors and warnings

### Documentation

7. **`DEPLOYMENT.md`** - Complete deployment guide
   - Step-by-step setup instructions
   - Development workflow
   - Troubleshooting section
   - Configuration options

8. **`NETWORK_SETUP.md`** - Network configuration details
   - WiFi setup on Pi
   - Network waiting explanation
   - Systemd service example

9. **`RESOLVE_SLUG_USAGE.md`** - Slug resolver API docs
   - Python module usage
   - Command-line usage
   - Bash integration examples
   - Error handling

10. **`QUICK_REFERENCE.md`** - Fast answers
    - Common commands
    - Troubleshooting quick fixes
    - File locations
    - Workflow cheatsheet

11. **`README.md`** - Project overview
    - Architecture diagram
    - Quick start guide
    - Links to all docs
    - Feature list

## Key Features

### Auto-Start on Boot

Minimal `.bashrc` entry:

```bash
export STARTGG_API_TOKEN="your-token"
if [ -z "$MATCHCALLER_STARTED" ]; then
    export MATCHCALLER_STARTED=1
    cd /home/pi/matchcaller && ./start_matchcaller.sh
fi
```

### Auto-Update on Boot

`start_matchcaller.sh` automatically:
- Fetches from git remote
- Compares local vs remote commits
- Pulls updates if available
- Stashes local changes
- Continues if update fails

### Network-Aware Startup

`wait_for_network`:
- Essential for Pi WiFi connection delays
- Prevents startup failures
- Configurable timeout
- Tests actual connectivity

### Dynamic Tournament Resolution

`resolve_slug`:
- No more hard-coded slugs
- Works with start.gg short URLs
- Automatic discovery of current tournament
- Updates weekly without code changes

## Testing Workflow

### On Development Machine

```bash
# Test everything before deploying
./test_startup.sh
```

This validates:
- ✅ Network connectivity
- ✅ Slug resolution (start.gg/abbey)
- ✅ Git repository valid
- ✅ Python environment
- ✅ Demo mode works
- ✅ API mode works (if token set)

### On Raspberry Pi

```bash
# After initial deployment
./scripts/verify_deployment.sh
```

This checks:
- ✅ All scripts present and executable
- ✅ Python dependencies installed
- ✅ Git configured correctly
- ✅ Network connectivity working
- ✅ API token set
- ✅ .bashrc configured

## Deployment Process

### Before (Manual)

1. Edit `~/.bashrc` with hard-coded tournament slug
2. Manual updates required for each tournament
3. No network handling
4. No auto-update capability
5. Manual testing only

### After (Automated)

1. Run `./scripts/setup_bashrc.sh` once
2. Set API token in `.bashrc` once
3. Network handled automatically
4. Auto-updates from git on every boot
5. Auto-resolves current tournament
6. Comprehensive testing with `test_startup.sh`
7. Deployment verification with `verify_deployment.sh`

## Benefits

1. **Zero-Touch Operation**
   - Pi boots → connects to WiFi → updates → displays tournament
   - No manual intervention needed

2. **Easy Development**
   - Test locally with `./test_startup.sh`
   - Push to git
   - Pi auto-updates on next boot

3. **Tournament Day Ready**
   - Always shows current tournament
   - No need to update slugs weekly
   - Handles venue WiFi delays

4. **Robust Error Handling**
   - Network timeout handling
   - Git update failures don't block startup
   - Slug resolution fallback possible

5. **Comprehensive Documentation**
   - Multiple guides for different needs
   - Quick reference for common tasks
   - Troubleshooting section

## Migration Guide

If you have an existing deployment:

1. **Pull latest code**
   ```bash
   cd /home/pi/matchcaller
   git pull
   ```

2. **Update .bashrc**
   ```bash
   ./scripts/setup_bashrc.sh
   # Choose option 2 to update
   ```

3. **Verify deployment**
   ```bash
   ./scripts/verify_deployment.sh
   ```

4. **Test without reboot**
   ```bash
   source ~/.bashrc
   ```

5. **Reboot for auto-start**
   ```bash
   sudo reboot
   ```

## Files Changed

### New Files
- `wait_for_network`
- `resolve_slug` (wrapper script)
- `start_matchcaller.sh`
- `test_startup.sh`
- `scripts/setup_bashrc.sh`
- `scripts/verify_deployment.sh`
- `DEPLOYMENT.md`
- `NETWORK_SETUP.md`
- `QUICK_REFERENCE.md`
- `CHANGELOG_DEPLOYMENT.md` (this file)
- `README.md`

### Modified Files
- `matchcaller/utils/resolve.py` (added CLI entry point)
- `RESOLVE_SLUG_USAGE.md` (updated with network examples)

### Configuration
- `~/.bashrc` (via setup script)

## Next Steps

Recommended future improvements:

1. **Systemd Service** - More robust than .bashrc
2. **Encrypted Token Storage** - Better security
3. **Remote Management** - Update without SSH
4. **Health Monitoring** - Alert on failures
5. **Multi-Tournament** - Display multiple events
6. **Backup Tournament Data** - Offline mode

## Version Info

- **Date**: 2025-10-13
- **Type**: Infrastructure enhancement
- **Compatibility**: Backward compatible with existing deployments
- **Breaking Changes**: None
