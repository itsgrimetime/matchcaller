# Quick Reference Guide

Fast answers for common tasks.

## Testing Before Deployment

```bash
# Test everything locally
./test_startup.sh

# Set API token for full test
export STARTGG_API_TOKEN="your-token"
./test_startup.sh
```

## Initial Pi Setup

```bash
# 1. Clone repo
cd /home/pi
git clone <your-repo> matchcaller
cd matchcaller

# 2. Install dependencies
pip install -e .

# 3. Configure auto-start
./scripts/setup_bashrc.sh

# 4. Edit API token
nano ~/.bashrc
# Change: export STARTGG_API_TOKEN="your-token"

# 5. Verify everything
./scripts/verify_deployment.sh

# 6. Reboot
sudo reboot
```

## Deploy Updates

```bash
# On dev machine
git add . && git commit -m "Update" && git push

# On Pi (or just reboot - it auto-updates!)
cd /home/pi/matchcaller
git pull
sudo reboot
```

## Manual Testing on Pi

```bash
# Test without rebooting
cd /home/pi/matchcaller
./start_matchcaller.sh

# Test individual components
./wait_for_network 30
./resolve_slug abbey
python -m matchcaller --demo
```

## Troubleshooting

```bash
# Check logs
tail -f /tmp/tournament_debug.log

# Verify configuration
./scripts/verify_deployment.sh

# Test network
./wait_for_network 30

# Test slug resolution
./resolve_slug abbey

# Check API token
echo $STARTGG_API_TOKEN

# Kill and restart
pkill -f matchcaller
./start_matchcaller.sh
```

## File Locations

| File | Purpose |
|------|---------|
| `~/.bashrc` | Auto-start configuration & API token |
| `/home/pi/matchcaller` | Installation directory |
| `/tmp/tournament_debug.log` | Application logs |
| `start_matchcaller.sh` | Main startup script |
| `wait_for_network` | Network wait utility |
| `resolve_slug` | Tournament resolver |

## Configuration Options

Edit `start_matchcaller.sh`:

```bash
SHORT_URL="abbey"           # Your short URL
EVENT_TYPE="singles"         # Event type
NETWORK_TIMEOUT=120          # Network wait (seconds)
```

## Common Issues

| Problem | Solution |
|---------|----------|
| Won't start on boot | Check `~/.bashrc` has MatchCaller config |
| Network timeout | Increase `NETWORK_TIMEOUT` in script |
| Wrong tournament | Verify `./resolve_slug abbey` works |
| API errors | Check `$STARTGG_API_TOKEN` is set |
| Git update fails | Run `git pull` manually to see error |

## Development Workflow

```bash
# 1. Make changes locally
vim matchcaller/ui/tournament_display.py

# 2. Test locally
./test_startup.sh

# 3. Commit & push
git commit -am "Update display"
git push

# 4. Pi auto-updates on next reboot
# Or manually: ssh pi@pi.local "cd matchcaller && git pull && sudo reboot"
```

## Bypass Auto-Start

```bash
# SSH into Pi
ssh pi@raspberrypi.local

# Set guard variable to prevent auto-start
export MATCHCALLER_STARTED=1

# Now you can do maintenance without TUI starting
```

## Clean Start After Crash

```bash
# Kill any stuck processes
pkill -f matchcaller

# Clean terminal state
printf '\033[?1000l\033[?1003l\033[?1015l\033[?1006l\033[?25h\033[?1004l'

# Restart
./start_matchcaller.sh
```

## Tournament Day Checklist

- [ ] Pi connects to venue WiFi (auto)
- [ ] Updates pulled from git (auto)
- [ ] Slug resolves to correct tournament
- [ ] TUI shows live matches
- [ ] Display readable on screen

## Useful Commands

```bash
# Check what's running
ps aux | grep matchcaller

# Monitor logs in real-time
tail -f /tmp/tournament_debug.log

# Test API connection
python -m matchcaller --token "$STARTGG_API_TOKEN" --slug "tournament/test/event/singles"

# Check git status
cd /home/pi/matchcaller && git status

# See current commit
git log -1 --oneline

# Force git update
git fetch origin && git reset --hard origin/main

# Reboot Pi remotely
ssh pi@raspberrypi.local "sudo reboot"
```
