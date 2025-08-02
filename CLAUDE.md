# Tournament Display TUI - Claude Code Documentation

## Project Overview

A **terminal-based tournament display** for Raspberry Pi Zero 2W that shows live match data from start.gg tournaments. This replaces using a web browser (which was too resource-intensive for the Pi Zero 2W's 512MB RAM) with a lightweight TUI that auto-starts on boot and displays real-time tournament status for Tournament Organizers.

## Current Status ✅

- **Working TUI**: Python + Textual displaying real tournament data from start.gg API
- **Hardware Target**: Raspberry Pi Zero 2W in console mode with large fonts (Terminus 32x16 Bold)
- **API Integration**: Successfully fetching live tournament sets with proper authentication
- **Real Data**: Tested with active tournaments showing Ready/In Progress/Waiting matches
- **Smart Status Detection**: Uses `startedAt` timestamps to distinguish between Ready vs In Progress matches

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│   start.gg API  │◄───│  TournamentAPI   │◄───│  TournamentDisplay  │
│   (GraphQL)     │    │   (AsyncIO)      │    │     (Textual)       │
└─────────────────┘    └──────────────────┘    └─────────────────────┘
        │                       │                          │
        │               ┌───────▼──────────┐              │
        │               │   MatchRow       │              │
        │               │  (Data Model)    │              │
        │               └──────────────────┘              │
        │                                                 │
        └─────────────── Real Tournament Data ────────────┘
```

## Key Components

### 1. **TournamentAPI Class**
- **Purpose**: Handles start.gg GraphQL API communication
- **Key Methods**:
  - `get_event_id_from_slug()`: Converts URL slug to event ID
  - `fetch_sets()`: Gets active tournament matches (states 1,2,6)
  - `parse_api_response()`: Transforms API data into app format
- **Authentication**: Bearer token via `Authorization` header

### 2. **TournamentDisplay App**
- **Framework**: Textual TUI with reactive updates
- **Features**:
  - Live data refresh every 30 seconds
  - Real-time timer updates every second
  - Manual refresh with 'R' key
  - Prioritized match sorting (In Progress → Ready → Waiting)
- **Layout**: Header + Info Bar + Match Table + Footer

### 3. **MatchRow Data Model**
- **State Mapping**:
  - State 1: Waiting (⚪)
  - State 2: Ready (🔴) or In Progress (🟡) based on `startedAt`
  - State 3: Completed (filtered out)
  - State 6: In Progress (🟡)
- **Smart Status**: Checks `startedAt` timestamp to distinguish Ready vs In Progress

## Usage

```bash
# Real tournament data
python tournament_display.py --token YOUR_API_TOKEN --slug "tournament/event-name/event/singles"

# Demo mode with mock data
python tournament_display.py --demo

# Example with working tournament
python tournament_display.py --token YOU_API_TOKEN --slug "tournament/melee-at-night-754/event/singles"
```

## Raspberry Pi Setup

### Hardware Configuration
- **Device**: Raspberry Pi Zero 2W (512MB RAM)
- **Display**: Large console fonts for visibility (Terminus 32x16 Bold)
- **Mode**: Console-only (no X11/desktop environment)
- **Auto-start**: Tournament display launches on boot

### Optimizations
- Disabled unnecessary services for minimal resource usage
- Console-only mode for maximum performance
- Direct terminal output with proper font sizing

## API Details

### start.gg Integration
- **Endpoint**: `https://api.start.gg/gql/alpha`
- **Authentication**: API token in Authorization header
- **Query Type**: GraphQL with event slugs (e.g., `tournament/name/event/type`)
- **Rate Limiting**: 30-second refresh intervals for live tournaments

### Event Slug Format
```
tournament/{tournament-slug}/event/{event-slug}
```

Example: `tournament/melee-at-night-754/event/singles`

### Set States
- **1**: Not started/Waiting for previous matches
- **2**: Ready to be called OR In Progress (check `startedAt`)
- **3**: Completed (filtered out for TOs)
- **6**: In Progress (rare, most use state 2 + `startedAt`)

## File Structure

```
tournament_display.py          # Main application
├── TournamentAPI             # API client class
├── TournamentDisplay         # Textual app class
├── MatchRow                  # Data model for matches
└── main()                    # CLI entry point
```

## Development Areas for Claude Code

### 1. **Enhanced Match Management**
- Add station assignment functionality
- Implement match calling notifications
- Stream assignment management
- Score reporting integration

### 2. **Configuration System**
- Config file for API tokens and settings
- Tournament presets and favorites
- Display customization options
- Auto-discovery of active tournaments

### 3. **Advanced Features**
- Multiple tournament monitoring
- Bracket visualization
- Player lookup and statistics
- Integration with OBS for stream overlays

### 4. **Production Deployment**
- Systemd service configuration
- Auto-start scripts for Pi
- Error recovery and logging
- Update mechanism for tournaments

### 5. **Code Architecture Improvements**
- Split into proper modules (`api/`, `ui/`, `models/`)
- Add comprehensive error handling
- Implement caching for reduced API calls
- Add unit tests for API parsing

## Testing Tournaments

### Active Test Tournament
- **URL**: https://www.start.gg/tournament/melee-at-night-754/event/singles
- **Slug**: `tournament/melee-at-night-754/event/singles`  
- **Status**: Has active matches in Ready/In Progress states

### Completed Tournament (for testing edge cases)
- **URL**: https://www.start.gg/tournament/the-c-stick-55/event/melee-singles
- **Slug**: `tournament/the-c-stick-55/event/melee-singles`
- **Status**: All matches completed (good for testing empty states)

## Known Issues & Next Steps

### Current Limitations
1. **Manual tournament selection**: Need to manually find event slugs
2. **Single tournament view**: Can't monitor multiple events simultaneously  
3. **Basic error handling**: API failures fall back to mock data
4. **No persistence**: Settings lost on restart

### Immediate Improvements Needed
1. **Tournament discovery**: Auto-find active tournaments
2. **Better error handling**: Graceful degradation without mock fallback
3. **Configuration management**: Save API tokens and preferences
4. **Status notifications**: Audio/visual alerts for match state changes

### Long-term Enhancements
1. **Multi-tournament dashboard**: Monitor several events at once
2. **Historical data**: Track tournament progress over time
3. **Integration APIs**: Connect with stream software, Discord bots
4. **Mobile companion**: Remote match calling from phone

## Environment Setup

```bash
# Dependencies
pip install textual aiohttp

# Development tools
pip install pytest black isort mypy

# Optional: for advanced features
pip install pydantic python-dotenv
```

## Debug & Logging

Current implementation includes comprehensive file logging:
- **Log file**: `/tmp/tournament_debug.log`
- **Console output**: Captured by Textual, check log file for debugging
- **API responses**: Full request/response cycle logged
- **Match parsing**: Individual set processing details

Use `tail -f /tmp/tournament_debug.log` for real-time debugging.

---

This TUI successfully bridges the gap between start.gg's web interface and embedded tournament displays, providing TOs with a lightweight, reliable way to monitor match status on minimal hardware.
