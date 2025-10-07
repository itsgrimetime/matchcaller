# Network Setup for Raspberry Pi Auto-Start

Quick guide for setting up matchcaller to auto-start on Raspberry Pi with network waiting and automatic tournament resolution.

## Problem

Raspberry Pi Zero 2W needs time to connect to WiFi on boot, and tournament slugs change weekly. Hard-coding slugs in ~/.bashrc requires manual updates.

## Solution

Three utilities work together:
1. **wait_for_network** - Waits for WiFi/network connectivity
2. **resolve_slug** - Resolves start.gg short URL to current tournament
3. **start_matchcaller.sh** - Complete startup script that uses both

## Setup

### 1. Set API Token

Edit `~/.bashrc` and add:

```bash
export STARTGG_API_TOKEN="your-actual-token-here"
```

### 2. Add Auto-Start to ~/.bashrc

```bash
# MatchCaller Auto-Start
if [ -z "$MATCHCALLER_STARTED" ]; then
    export MATCHCALLER_STARTED=1
    cd /home/pi/matchcaller && ./start_matchcaller.sh
fi
```

The `MATCHCALLER_STARTED` check prevents the script from running multiple times if you open new shells.

### 3. Reboot

```bash
sudo reboot
```

## What Happens on Boot

```
Pi boots → bashrc runs → start_matchcaller.sh
    ↓
Wait for network (up to 2 minutes)
    ↓
Resolve start.gg/abbey → tournament/melee-abbey-tavern-114/event/singles
    ↓
Launch: python -m matchcaller --token XXX --slug tournament/...
```

## Customization

Edit `start_matchcaller.sh` to change:

```bash
SHORT_URL="abbey"           # Your start.gg short URL
EVENT_TYPE="singles"         # Or "doubles", "crews", etc.
NETWORK_TIMEOUT=120          # Seconds to wait for network
MATCHCALLER_DIR="/home/pi/matchcaller"  # Installation path
```

## Manual Testing

```bash
# Test network waiting
./wait_for_network 30

# Test slug resolution
./resolve_slug abbey

# Test complete startup
./start_matchcaller.sh
```

## Troubleshooting

### Network never connects
- Check WiFi credentials: `sudo nano /etc/wpa_supplicant/wpa_supplicant.conf`
- Verify WiFi is enabled: `sudo rfkill list`
- Check network status: `ip addr show`

### Slug resolution fails
- Test manually: `curl -I https://start.gg/abbey`
- Check DNS: `ping start.gg`
- Verify short URL exists in browser

### MatchCaller doesn't start
- Check logs: `tail -f /tmp/tournament_debug.log`
- Verify API token: `echo $STARTGG_API_TOKEN`
- Test manually: `python -m matchcaller --demo`

## Advanced: Systemd Service

For more robust auto-start (instead of ~/.bashrc):

```ini
# /etc/systemd/system/matchcaller.service
[Unit]
Description=MatchCaller Tournament Display
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
Environment="STARTGG_API_TOKEN=your-token-here"
WorkingDirectory=/home/pi/matchcaller
ExecStart=/home/pi/matchcaller/start_matchcaller.sh
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable with:
```bash
sudo systemctl enable matchcaller
sudo systemctl start matchcaller
```

## Files Reference

- **wait_for_network** - Network connectivity checker
- **resolve_slug** - Tournament slug resolver
- **start_matchcaller.sh** - Complete startup orchestrator
- **RESOLVE_SLUG_USAGE.md** - Detailed API documentation
- **NETWORK_SETUP.md** - This file

## Benefits

✅ No manual tournament slug updates
✅ Handles slow WiFi connections gracefully
✅ Automatic recovery from network issues
✅ Clean, maintainable configuration
✅ Works with any start.gg short URL
