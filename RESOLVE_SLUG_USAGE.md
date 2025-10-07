# Tournament Slug Resolver

Utility to resolve start.gg short URLs to tournament slugs for automatic tournament lookup.

## Usage

### From Command Line

```bash
# Direct usage
./resolve_slug abbey
# Output: melee-abbey-tavern-114

# Store in variable
TOURNAMENT_SLUG=$(./resolve_slug abbey)
echo $TOURNAMENT_SLUG
# Output: melee-abbey-tavern-114
```

### Integration with ~/.bashrc

Instead of hard-coding the tournament slug in your ~/.bashrc, you can dynamically resolve it:

**Old way (hard-coded):**
```bash
export TOURNAMENT_SLUG="tournament/melee-abbey-tavern-114"
```

**New way (auto-resolved):**
```bash
# Add to ~/.bashrc
cd /path/to/matchcaller
export TOURNAMENT_SLUG="tournament/$(./resolve_slug abbey)/event/singles"
export API_TOKEN="your-api-token-here"

# Start the matchcaller TUI
python -m matchcaller --token "$API_TOKEN" --slug "$TOURNAMENT_SLUG"
```

### Complete ~/.bashrc Example

```bash
#!/bin/bash

# Navigate to matchcaller directory
cd /home/pi/matchcaller

# Wait for network connectivity (with 60 second timeout)
./wait_for_network 60
if [ $? -ne 0 ]; then
    echo "Network connection failed, exiting"
    exit 1
fi

# Resolve the current tournament from short URL
SLUG_PART=$(./resolve_slug abbey)

# Build full tournament slug with event
export TOURNAMENT_SLUG="tournament/${SLUG_PART}/event/singles"

# Your API token (store securely!)
export API_TOKEN="your-actual-token-here"

# Launch the tournament display
python -m matchcaller --token "$API_TOKEN" --slug "$TOURNAMENT_SLUG"
```

### Raspberry Pi Auto-Start Example (with Network Wait)

For reliable auto-start on boot, especially in environments with slow WiFi:

```bash
#!/bin/bash

cd /home/pi/matchcaller

# Wait up to 2 minutes for network
echo "Waiting for network connectivity..."
./wait_for_network 120

if [ $? -eq 0 ]; then
    # Network is up, resolve tournament
    if SLUG_PART=$(./resolve_slug abbey 2>/dev/null); then
        export TOURNAMENT_SLUG="tournament/${SLUG_PART}/event/singles"
        export API_TOKEN="your-token-here"

        # Start the display
        python -m matchcaller --token "$API_TOKEN" --slug "$TOURNAMENT_SLUG"
    else
        # Fallback to last known tournament
        echo "Failed to resolve slug, using fallback"
        export TOURNAMENT_SLUG="tournament/melee-abbey-tavern-114/event/singles"
        export API_TOKEN="your-token-here"
        python -m matchcaller --token "$API_TOKEN" --slug "$TOURNAMENT_SLUG"
    fi
else
    echo "Network unavailable, cannot start matchcaller"
    # Show error on screen
    echo "ERROR: No network connection" > /dev/tty1
fi
```

## How It Works

### Tournament Slug Resolution

1. The script makes an HTTP request to `https://start.gg/abbey`
2. start.gg redirects to the full tournament URL
3. The script extracts the tournament slug from the redirect
4. Returns just the slug portion (e.g., `melee-abbey-tavern-114`)

### Network Waiting

The `wait_for_network` script:
1. Pings Google DNS (8.8.8.8) to check for basic internet connectivity
2. Also tries to ping start.gg specifically to ensure the API is reachable
3. Retries every 2 seconds until timeout is reached
4. Returns exit code 0 on success, 1 on timeout

## Benefits

- **No manual updates**: The short URL always points to the latest tournament
- **Clean configuration**: One short URL instead of full slugs
- **Auto-discovery**: Pi automatically finds the current tournament on boot
- **Flexible**: Works with any start.gg short URL

## Quick Start (Recommended)

The easiest way to use network waiting + slug resolution is with the included startup script:

```bash
# Set your API token in environment
export STARTGG_API_TOKEN="your-token-here"

# Run the startup script
./start_matchcaller.sh
```

This script automatically:
1. Waits for network connectivity (up to 2 minutes)
2. Resolves the tournament slug from start.gg/abbey
3. Launches matchcaller with the correct parameters

### Add to ~/.bashrc for Auto-Start

```bash
# Add to the end of ~/.bashrc
export STARTGG_API_TOKEN="your-token-here"
cd /home/pi/matchcaller && ./start_matchcaller.sh
```

## API

### Python Module

```python
from matchcaller.utils.resolve import resolve_tournament_slug_from_unique_string

slug = resolve_tournament_slug_from_unique_string("abbey")
print(slug)  # melee-abbey-tavern-114
```

### Command Line

```bash
python -m matchcaller.utils.resolve abbey
# Output: melee-abbey-tavern-114
```

### Shell Script

```bash
./resolve_slug abbey
# Output: melee-abbey-tavern-114
```

## Error Handling

The script exits with status code 1 if resolution fails:

```bash
if SLUG_PART=$(./resolve_slug abbey 2>/dev/null); then
    export TOURNAMENT_SLUG="tournament/${SLUG_PART}/event/singles"
else
    echo "Failed to resolve tournament, using fallback"
    export TOURNAMENT_SLUG="tournament/melee-abbey-tavern-114/event/singles"
fi
```
