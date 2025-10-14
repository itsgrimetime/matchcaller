# Deployment Guide

Complete guide for deploying MatchCaller to Raspberry Pi with auto-start, auto-update, and network handling.

## Quick Deployment (TL;DR)

```bash
# On your dev machine
cd /path/to/matchcaller
./test_startup.sh  # Verify everything works

# On Raspberry Pi
cd /home/pi
git clone <your-repo> matchcaller
cd matchcaller
./scripts/setup_bashrc.sh
# Edit ~/.bashrc and set your API token
sudo reboot
```

---

## Development Workflow

### 1. Test Locally First

Before deploying, always test on your development machine:

```bash
cd /path/to/matchcaller

# Run comprehensive tests
./test_startup.sh

# This will test:
# - Network connectivity
# - Slug resolution
# - Git repository status
# - Python environment
# - Demo mode
# - Real API mode (if token set)
```

**Set your API token for full testing:**
```bash
export STARTGG_API_TOKEN="your-token-here"
./test_startup.sh
```

### 2. Commit and Push Changes

```bash
git add .
git commit -m "Update matchcaller"
git push origin main
```

### 3. Deploy to Raspberry Pi

The Pi will auto-update on next boot, or manually pull:

```bash
# SSH into Pi
ssh pi@raspberrypi.local

cd /home/pi/matchcaller
git pull origin main

# Verify deployment
./scripts/verify_deployment.sh

# Restart matchcaller
sudo reboot
```

---

## Initial Raspberry Pi Setup

### Prerequisites

- Raspberry Pi Zero 2W with Raspbian/Raspberry Pi OS
- WiFi configured and working
- SSH access enabled
- Python 3.7+ installed
- Git installed

### Step-by-Step Setup

#### 1. Clone Repository

```bash
cd /home/pi
git clone https://github.com/your-username/matchcaller.git
cd matchcaller
```

#### 2. Install Python Dependencies

```bash
# Install in development mode (editable)
pip install -e .

# Or install dependencies manually
pip install textual aiohttp requests
```

#### 3. Make Scripts Executable

```bash
chmod +x wait_for_network
chmod +x resolve_slug
chmod +x start_matchcaller.sh
chmod +x test_startup.sh
chmod +x scripts/*.sh
```

#### 4. Configure .bashrc

Run the setup script:

```bash
./scripts/setup_bashrc.sh
```

This will add the auto-start configuration to `~/.bashrc`.

#### 5. Set Your API Token

```bash
nano ~/.bashrc

# Find this line:
export STARTGG_API_TOKEN="REPLACE_WITH_YOUR_TOKEN"

# Change it to:
export STARTGG_API_TOKEN="your-actual-token-here"

# Save and exit (Ctrl+X, Y, Enter)
```

#### 6. Verify Deployment

```bash
./scripts/verify_deployment.sh
```

This checks:
- Required scripts present and executable
- Python environment configured
- Git repository valid
- Network connectivity
- API token set
- .bashrc configured

#### 7. Test Without Rebooting

```bash
# Source bashrc to test
source ~/.bashrc

# This should start matchcaller
# Press Ctrl+C to exit
```

#### 8. Reboot for Auto-Start

```bash
sudo reboot
```

The Pi will now:
1. Boot up
2. Connect to WiFi (wait up to 2 minutes)
3. Auto-update code from git
4. Resolve tournament slug from start.gg/abbey
5. Launch matchcaller TUI

---

## Configuration Options

### Customizing start_matchcaller.sh

Edit `/home/pi/matchcaller/start_matchcaller.sh`:

```bash
# Configuration section at top of file
SHORT_URL="abbey"           # Your start.gg short URL
EVENT_TYPE="singles"         # Event type: singles, doubles, etc.
NETWORK_TIMEOUT=120          # Seconds to wait for WiFi (2 minutes)
MATCHCALLER_DIR="/home/pi/matchcaller"  # Install directory
```

### Minimal .bashrc Entry

The setup script adds this to your `~/.bashrc`:

```bash
# ===== MatchCaller Auto-Start =====
export STARTGG_API_TOKEN="your-token"

if [ -z "$MATCHCALLER_STARTED" ]; then
    export MATCHCALLER_STARTED=1
    cd /home/pi/matchcaller && ./start_matchcaller.sh
fi
# ===== End MatchCaller Auto-Start =====
```

The `MATCHCALLER_STARTED` guard ensures it only runs once per session.

---

## How It Works

### Boot Sequence

```
1. Pi boots
   ↓
2. Raspbian starts
   ↓
3. Auto-login to console
   ↓
4. .bashrc executes
   ↓
5. start_matchcaller.sh runs
   ↓
6. Wait for network (up to 2 min)
   ├─→ Ping 8.8.8.8
   └─→ Ping start.gg
   ↓
7. Git fetch & pull (if updates available)
   ↓
8. Resolve slug: start.gg/abbey → tournament/melee-abbey-tavern-114
   ↓
9. Launch: python -m matchcaller --token XXX --slug tournament/...
   ↓
10. TUI displays on screen
```

### Auto-Update Process

On each boot, `start_matchcaller.sh` automatically:

1. **Checks for git updates**
   ```bash
   git fetch origin
   ```

2. **Compares local vs remote**
   ```bash
   if [ "$LOCAL" != "$REMOTE" ]; then
       git pull origin main
   fi
   ```

3. **Stashes local changes** (if any)
   ```bash
   git stash push -m "Auto-stash before update"
   ```

4. **Continues with current version if update fails**
   - Never blocks startup due to git issues
   - Shows warning if update failed

This means:
- **Push to main** → Changes deploy on next Pi reboot
- **No manual updates needed** on the Pi
- **Safe fallback** if updates fail

---

## Testing Checklist

### Before Deploying

- [ ] Run `./test_startup.sh` on dev machine
- [ ] All tests pass
- [ ] Changes committed to git
- [ ] Changes pushed to remote

### After Initial Pi Setup

- [ ] `./scripts/verify_deployment.sh` passes
- [ ] API token set in `~/.bashrc`
- [ ] Test with `source ~/.bashrc`
- [ ] Verify TUI displays correctly
- [ ] Test auto-start with `sudo reboot`

### Before Tournament Day

- [ ] Pi boots and connects to tournament WiFi
- [ ] Auto-update pulls latest changes
- [ ] Tournament slug resolves correctly
- [ ] TUI shows live match data
- [ ] Display is readable on target screen

---

## Troubleshooting

### MatchCaller doesn't start on boot

1. Check .bashrc configuration:
   ```bash
   grep "MatchCaller" ~/.bashrc
   ```

2. Check for errors:
   ```bash
   tail -f /tmp/tournament_debug.log
   ```

3. Test manually:
   ```bash
   cd /home/pi/matchcaller
   ./start_matchcaller.sh
   ```

### Network timeout on boot

- Increase timeout in `start_matchcaller.sh`:
  ```bash
  NETWORK_TIMEOUT=180  # 3 minutes instead of 2
  ```

- Check WiFi configuration:
  ```bash
  sudo nano /etc/wpa_supplicant/wpa_supplicant.conf
  ```

### Git auto-update fails

- Check remote access:
  ```bash
  git fetch origin
  git pull origin main
  ```

- Verify SSH keys or credentials configured

### Wrong tournament shows up

- Test slug resolution:
  ```bash
  ./resolve_slug abbey
  ```

- Verify the short URL redirects correctly in browser

### API token not working

- Verify token is set:
  ```bash
  echo $STARTGG_API_TOKEN
  ```

- Test token with API:
  ```bash
  python -m matchcaller --token "$STARTGG_API_TOKEN" --slug "tournament/test/event/singles"
  ```

---

## Development Tips

### Quick Edit Cycle

```bash
# On dev machine
vim matchcaller/ui/tournament_display.py
./test_startup.sh  # Test changes
git commit -am "Fix display bug"
git push

# On Pi (or wait for next reboot)
cd /home/pi/matchcaller
git pull
# Restart matchcaller or reboot
```

### Testing Without Rebooting Pi

```bash
# Kill current matchcaller
pkill -f matchcaller

# Start fresh
cd /home/pi/matchcaller
git pull
./start_matchcaller.sh
```

### Using Demo Mode for Development

```bash
# Test without real tournament data
python -m matchcaller --demo
```

### Bypass Auto-Start Temporarily

```bash
# SSH into Pi and set the guard variable
export MATCHCALLER_STARTED=1

# Now .bashrc won't auto-start matchcaller
# Useful for maintenance
```

---

## File Reference

### Core Scripts

- **`wait_for_network`** - Network connectivity checker (120s timeout)
- **`resolve_slug`** - Convert short URL to tournament slug
- **`start_matchcaller.sh`** - Complete startup orchestrator
- **`test_startup.sh`** - Pre-deployment testing on dev machine

### Setup Scripts

- **`scripts/setup_bashrc.sh`** - Configure .bashrc for auto-start
- **`scripts/verify_deployment.sh`** - Verify Pi is ready for production

### Documentation

- **`DEPLOYMENT.md`** - This file (deployment guide)
- **`NETWORK_SETUP.md`** - Network setup reference
- **`RESOLVE_SLUG_USAGE.md`** - Slug resolution API docs
- **`CLAUDE.md`** - Project overview for Claude Code

---

## Security Notes

- **API Token**: Stored in `~/.bashrc` as environment variable
  - Not checked into git
  - Only readable by pi user
  - Consider using systemd with EnvironmentFile for production

- **Auto-Update**: Automatically pulls from git remote
  - Only pulls from configured origin
  - Stashes local changes before updating
  - Useful for trusted environments (home/venue Pi)
  - Consider disabling for untrusted networks

- **Network Access**: Script pings external servers
  - 8.8.8.8 (Google DNS)
  - start.gg
  - Consider firewall rules if needed

---

## Future Improvements

- [ ] Systemd service instead of .bashrc auto-start
- [ ] Encrypted API token storage
- [ ] Remote management/monitoring
- [ ] OTA updates without reboot
- [ ] Multi-tournament support
- [ ] Health check endpoint
- [ ] Automatic fallback to cached tournament data
