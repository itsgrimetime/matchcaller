# Tournament Bracket Simulator

A powerful tool for cloning completed tournaments and simulating their state transitions for development and testing.

## Overview

The Tournament Simulator solves the problem of needing live tournament data for development and testing. Instead of waiting for real tournaments to happen and hoping for state changes, you can:

1. **Clone** any completed tournament from start.gg
2. **Replay** its entire timeline at accelerated speed
3. **Test** your TUI with realistic state transitions

## Quick Start

### 1. Clone a Tournament

```bash
# Clone a completed tournament (requires API token)
python simulator_cli.py clone --token YOUR_API_TOKEN --slug "tournament/the-c-stick-55/event/melee-singles"
```

This captures all historical match data including:
- Match creation times
- Start times (when matches became active)  
- Completion times
- Player information
- Bracket structure

### 2. List Available Tournaments

```bash
# See all cloned tournaments
python simulator_cli.py list
```

### 3. Run Simulation

```bash
# Run with TUI interface (recommended)
python simulator_cli.py simulate tournament_data_file.json --gui

# Or run console-only simulation
python simulator_cli.py simulate tournament_data_file.json --speed 120
```

### 4. Analyze Tournament Data

```bash
# Get detailed statistics about a tournament
python simulator_cli.py analyze tournament_data_file.json
```

## Features

### Tournament Cloner (`TournamentCloner`)
- Fetches complete tournament history via start.gg GraphQL API
- Handles pagination for large tournaments
- Captures all match states and timestamps
- Saves data in structured JSON format

### Bracket Simulator (`BracketSimulator`)
- Replays tournament timeline at configurable speed
- Simulates realistic state transitions:
  - Matches appear when created
  - Become "Ready" when players are available
  - Switch to "In Progress" when started
  - Disappear when completed
- Provides current state snapshots for testing

### CLI Interface
- Simple commands for common workflows
- Built-in help and examples
- Integration with existing TUI application

## Use Cases

### 🧪 Development Testing
```bash
# Test your TUI with realistic data flow
python simulator_cli.py simulate tournament.json --gui --speed 60
```

### 🔧 Feature Development  
```bash
# Test new features against various tournament formats
python simulator_cli.py clone --token TOKEN --slug "tournament/evo-2023/event/tekken-8"
python simulator_cli.py simulate tournament_evo_2023_tekken_8.json --gui
```

### 🐛 Bug Reproduction
```bash
# Reproduce issues with specific tournament structures
python simulator_cli.py analyze problematic_tournament.json
python simulator_cli.py simulate problematic_tournament.json --gui --speed 30
```

### 📊 Performance Testing
```bash
# Test with large tournaments at high speed
python simulator_cli.py simulate large_tournament.json --speed 300
```

## Technical Details

### Data Format
Cloned tournaments are saved as JSON files with:
```json
{
  "metadata": {
    "event_name": "Melee Singles",
    "tournament_name": "The C-Stick #55",
    "event_slug": "tournament/the-c-stick-55/event/melee-singles",
    "total_matches": 127,
    "cloned_at": 1234567890
  },
  "duration_minutes": 180,
  "matches": [
    {
      "id": 12345,
      "display_name": "Winners Round 1",
      "player1": {"tag": "Alice"},
      "player2": {"tag": "Bob"},
      "state": 3,
      "created_at": 1234567800,
      "started_at": 1234567900,
      "completed_at": 1234568000,
      "phase_group": "A1",
      "phase_name": "Winner's Bracket"
    }
  ]
}
```

### State Simulation Logic
The simulator intelligently determines match states:
- **Created** matches start in "Waiting" state (1)
- When **started**, matches become "Ready" (2) or "In Progress" (6)
- **Completed** matches are filtered out of active display
- **TBD** matches (missing players) are skipped

### Speed Control
The `--speed` parameter controls simulation rate:
- `1.0` = Real-time (very slow)
- `60.0` = 1 hour becomes 1 minute (default)
- `300.0` = 5-minute tournaments for quick testing

## Integration

### With Existing TUI
The simulator provides a `SimulatedTournamentAPI` class that's a drop-in replacement for the real `TournamentAPI`:

```python
from matchcaller.utils.bracket_simulator import BracketSimulator, SimulatedTournamentAPI

# Load simulation
simulator = BracketSimulator("tournament.json")
simulator.load_tournament()

# Use simulated API
sim_api = SimulatedTournamentAPI(simulator)
app = TournamentDisplay(api_token=None, event_id=None, event_slug=None)
app.api = sim_api
```

### Custom Applications
You can build custom applications using the simulator:

```python
async def my_callback(tournament_state):
    print(f"Active matches: {len(tournament_state['sets'])}")
    # Process state changes...

await simulator.start_simulation(callback=my_callback)
```

## File Management

Cloned tournaments are stored in `simulator_data/` directory:
```
simulator_data/
├── tournament_the_c_stick_55_event_melee_singles_20240830_143022.json
├── tournament_evo_2023_event_tekken_8_20240830_150112.json
└── tournament_genesis_10_event_melee_singles_20240830_152030.json
```

## API Requirements

Tournament cloning requires a start.gg API token:
1. Create account at [start.gg](https://start.gg)
2. Go to [Developer Settings](https://start.gg/admin/profile/developer)
3. Generate an API token
4. Use with `--token YOUR_TOKEN`

## Tips

### Finding Good Tournaments to Clone
- Look for recently completed tournaments
- Choose tournaments with varied match states
- Larger tournaments provide more realistic testing data
- Different game types have different bracket structures

### Simulation Speed Guidelines
- **Development**: 30-60x (easy to follow)
- **Testing**: 120-300x (faster feedback)
- **Demos**: 10-30x (good for presentations)

### Storage Considerations
- Cloned files are typically 50KB-2MB depending on tournament size
- Keep frequently used tournaments for different test scenarios
- Clean up old clones periodically

---

This simulator transforms tournament development from "wait and hope" to "clone and test", making it much easier to build robust tournament management tools.