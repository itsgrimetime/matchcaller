# MatchCaller - Tournament Display TUI

Lightweight terminal-based tournament display for Raspberry Pi showing live match data from start.gg tournaments.

## Features

- 🎮 **Live Tournament Data** - Real-time match updates from start.gg API
- 🔄 **Auto-Update** - Pulls latest code changes on boot
- 🌐 **Smart Network Handling** - Waits for WiFi before starting
- 🔗 **Dynamic Tournament Resolution** - Auto-resolves short URLs (start.gg/abbey)
- 🚀 **Auto-Start on Boot** - Zero-touch operation for Raspberry Pi
- 📊 **Prioritized Match Display** - In Progress → Ready → Waiting
- ⏱️ **Live Timers** - Real-time duration tracking
- 🎨 **Color-Coded Status** - Visual indicators for match states

## Quick Start

### Development Machine

```bash
# Test locally
./test_startup.sh

# With API token
export STARTGG_API_TOKEN="your-token"
./test_startup.sh
```

### Raspberry Pi

```bash
# Initial setup
cd /home/pi
git clone <your-repo> matchcaller
cd matchcaller
pip install -e .
./scripts/setup_bashrc.sh

# Edit API token in ~/.bashrc
nano ~/.bashrc

# Verify & reboot
./scripts/verify_deployment.sh
sudo reboot
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed setup instructions.

## Documentation

- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Fast answers for common tasks
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Complete deployment guide
- **[NETWORK_SETUP.md](NETWORK_SETUP.md)** - Network configuration details
- **[RESOLVE_SLUG_USAGE.md](RESOLVE_SLUG_USAGE.md)** - Slug resolver API docs
- **[CLAUDE.md](CLAUDE.md)** - Project overview for AI assistance

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  Raspberry Pi Boot                                   │
│  ↓                                                   │
│  ~/.bashrc → start_matchcaller.sh                   │
│  ↓                                                   │
│  1. wait_for_network (WiFi detection)               │
│  2. git pull (auto-update)                          │
│  3. resolve_slug (tournament discovery)             │
│  4. python -m matchcaller (TUI launch)              │
│  ↓                                                   │
│  ┌─────────────────────────────────────────┐       │
│  │ TournamentDisplay (Textual TUI)         │       │
│  │  ↓                                       │       │
│  │  TournamentAPI (start.gg GraphQL)       │       │
│  │  ↓                                       │       │
│  │  Match Data → Display Grid              │       │
│  └─────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────┘
```

## Usage

### Command Line

```bash
# Demo mode (mock data)
python -m matchcaller --demo

# Live tournament
python -m matchcaller --token TOKEN --slug "tournament/name/event/singles"

# Auto-resolve from short URL (requires start_matchcaller.sh)
./start_matchcaller.sh
```

### Configuration

Edit `start_matchcaller.sh`:

```bash
SHORT_URL="abbey"           # Your start.gg short URL
EVENT_TYPE="singles"         # Event type: singles, doubles, etc.
NETWORK_TIMEOUT=120          # Max seconds to wait for network
```

Set API token in `~/.bashrc`:

```bash
export STARTGG_API_TOKEN="your-actual-token-here"
```

## Key Components

### Scripts

- **`start_matchcaller.sh`** - Complete startup orchestration
  - Network waiting
  - Git auto-update
  - Tournament resolution
  - TUI launch

- **`wait_for_network`** - Network connectivity checker
  - Pings 8.8.8.8 and start.gg
  - Configurable timeout
  - 2-second retry interval

- **`resolve_slug`** - Tournament slug resolver
  - Converts short URLs to full slugs
  - Usage: `./resolve_slug abbey` → `melee-abbey-tavern-114`

- **`test_startup.sh`** - Pre-deployment testing
  - Validates all components
  - Tests network, slug resolution, Python environment
  - Runs demo and API modes

### Setup Utilities

- **`scripts/setup_bashrc.sh`** - Configure auto-start
  - Adds MatchCaller config to ~/.bashrc
  - Interactive update/remove options
  - Validates configuration

- **`scripts/verify_deployment.sh`** - Deployment verification
  - Checks all requirements
  - Validates configuration
  - Tests connectivity and dependencies

## Development

### Local Testing

```bash
# Run all tests
./test_startup.sh

# Test individual components
./wait_for_network 30
./resolve_slug abbey
python -m matchcaller --demo
```

### Deploy Changes

```bash
# Commit and push
git add .
git commit -m "Update matchcaller"
git push

# Pi auto-updates on next reboot
# Or manually: git pull && sudo reboot
```

### Project Structure

```
matchcaller/
├── matchcaller/              # Main package
│   ├── api/                  # start.gg API client
│   ├── ui/                   # Textual TUI
│   ├── models/               # Data models
│   ├── utils/                # Utilities (logging, resolve)
│   └── simulator/            # Tournament simulation
├── scripts/                  # Setup utilities
│   ├── setup_bashrc.sh       # .bashrc configuration
│   └── verify_deployment.sh  # Deployment checks
├── tests/                    # Unit tests
├── wait_for_network          # Network wait utility
├── resolve_slug              # URL resolver
├── start_matchcaller.sh      # Main startup script
├── test_startup.sh           # Pre-deployment tests
└── docs/                     # Documentation
    ├── DEPLOYMENT.md
    ├── NETWORK_SETUP.md
    ├── QUICK_REFERENCE.md
    └── RESOLVE_SLUG_USAGE.md
```

## Requirements

### Hardware

- Raspberry Pi Zero 2W (or any Pi model)
- Display (HDMI or built-in)
- Network connection (WiFi or Ethernet)

### Software

- Python 3.7+
- Dependencies: `textual`, `aiohttp`, `requests`
- Git (for auto-update)

### API

- start.gg API token
- Tournament with active matches

## Troubleshooting

See [QUICK_REFERENCE.md](QUICK_REFERENCE.md#troubleshooting) for common issues and solutions.

**Common fixes:**

```bash
# Check logs
tail -f /tmp/tournament_debug.log

# Verify deployment
./scripts/verify_deployment.sh

# Test components
./wait_for_network 30
./resolve_slug abbey
python -m matchcaller --demo

# Clean restart
pkill -f matchcaller
./start_matchcaller.sh
```

## Tournament Day Workflow

1. **Pi arrives at venue** → Powers on
2. **Auto-boot sequence**:
   - Connects to venue WiFi (up to 2 min)
   - Pulls latest code from git
   - Resolves current tournament from start.gg/abbey
   - Launches TUI with live data
3. **Display shows** → In Progress / Ready / Waiting matches
4. **Auto-updates** → Every 30 seconds from API
5. **Zero intervention** → Runs unattended all day

## Contributing

This project is designed for personal/tournament use. Key areas for improvement:

- [ ] Systemd service (instead of .bashrc)
- [ ] Remote management API
- [ ] Multi-tournament support
- [ ] OBS integration
- [ ] Discord bot integration
- [ ] Mobile companion app

## License

[Your License Here]

## Credits

Built for Super Smash Bros. Melee tournaments using the start.gg API.

Powered by:
- [Textual](https://textual.textualize.io/) - TUI framework
- [start.gg](https://start.gg/) - Tournament platform
- [aiohttp](https://docs.aiohttp.org/) - Async HTTP client

---

**Ready to deploy?** → See [DEPLOYMENT.md](DEPLOYMENT.md)

**Need quick help?** → See [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
