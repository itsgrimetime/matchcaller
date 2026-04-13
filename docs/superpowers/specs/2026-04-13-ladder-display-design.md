# Ladder Display Design

## Context

Abbey Tavern now runs a start.gg ladder after the main bracket reaches the late-bracket stage. The MatchCaller Pi is partially headless during the event: the TUI is visible, but there is no keyboard or mouse attached. Updating launch arguments by SSH and reboot is possible, but it is not a good tournament-night control surface.

Exploration against Abbey start.gg data on April 13, 2026 showed that ladder is exposed through public GraphQL as a normal event:

- Current event: `Melee Ladder (9:30pm)`, slug `tournament/melee-abbey-tavern-137/event/melee-ladder-9-30pm`
- The ladder event has a `Ladder` phase with `bracketType: MATCHMAKING`
- The ladder phase group also reports `bracketType: MATCHMAKING`
- Public `Event.state` is available as `CREATED`, `ACTIVE`, `COMPLETED`, etc.
- Public `Event.startedAt` is not available; scheduled `startAt` is available
- Completed Abbey ladders expose normal `sets`, `standings`, set W-L records through `setRecordWithoutByes`, and set station assignments

The design should support both a dynamic split display on the primary MatchCaller and a dedicated ladder-only display on a second MatchCaller device.

## Goals

- Add a headless-safe `auto` mode that starts as main bracket only, then reveals ladder automatically after the ladder event starts.
- Add explicit `main`, `split`, and `ladder` modes for preconfigured device roles.
- Auto-discover the ladder event from the current tournament, with event name containing `ladder` as the primary match and `MATCHMAKING` phase/group as a stronger validation signal.
- Keep the existing main bracket behavior intact for explicit `main` mode and for tournaments with no discovered ladder event.
- Show setup availability for ladder by using tournament stations and active set station assignments.
- Parse ladder standings with W-L records for display.
- Keep API parsing and UI rendering testable through pure helpers and injected seams.

## Non-Goals

- Do not add keyboard-driven mode switching as the primary flow; the deployment target often has no keyboard.
- Do not add start.gg mutation support for creating, starting, or reporting ladder sets.
- Do not depend on private start.gg web page fields such as `hasMatchmaking` or `Event.startedAt`; only use public GraphQL fields available through the API token.
- Do not replace the existing pool-grid renderer for the main-only path.

## Runtime Modes

Add a CLI option:

```text
--view auto|main|split|ladder
```

`auto` should be the default when launching with `--short-url abbey`. It should preserve current startup ergonomics while supporting ladder without intervention:

1. Resolve the current tournament from the short URL.
2. Select the main event using the existing `--event-filter` behavior.
3. Discover the ladder event from the same tournament.
4. Start in main-only view while the ladder event is undiscovered or not active.
5. Switch to split view when the ladder is active or has live data.

`main` keeps today's behavior: fetch and display only the selected main event.

`split` is an explicit two-panel mode. If the ladder is not active yet, it should show the same main bracket content with a small waiting/not-started ladder status rather than failing.

`ladder` is for a dedicated second device. It should auto-discover the ladder event, show a waiting state until ladder starts, and switch to the ladder board when active or populated.

## Ladder Activation

A discovered ladder should be considered visible when any of these are true:

- `Event.state == ACTIVE`
- The ladder has active sets in states `[1, 2, 6]`
- The ladder has standings

If the ladder event is `CREATED` and has no active sets or standings, `auto` stays main-only and `ladder` mode shows a waiting screen with the discovered event name and scheduled `startAt` if available.

Entrant count should be fetched for display, but it should not make the ladder visible by itself. This avoids showing the ladder early if entrants are added before the TOs mark the ladder live.

This avoids relying on scheduled time alone. The ladder may be scheduled for a nominal time but should not appear in the main display until the TOs actually start using it.

## API And Data Flow

Introduce a higher-level coordinator instead of overloading `TournamentAPI.fetch_sets()`:

```text
TournamentDashboardAPI
  resolves tournament and event selection
  discovers ladder event
  fetches main event state
  fetches ladder event state
  fetches tournament stations
  returns DashboardState
```

Suggested model shape:

```text
DashboardState
  tournament_name: str
  main: TournamentState | None
  ladder: LadderState | None
  stations: StationState | None
  resolved_view: main|split|ladder
  last_update: str

LadderState
  event_id: str
  event_name: str
  event_slug: str
  event_state: str
  start_at: int | None
  entrants_count: int
  sets: list[MatchData]
  standings: list[LadderStanding]
  is_visible: bool
  waiting_reason: str | None

LadderStanding
  placement: int
  entrant_name: str
  wins: int | None
  losses: int | None
  win_percentage: str | None

StationState
  stations: list[Station]
  occupied_numbers: set[int]
  available_numbers: list[int]
```

Keep existing `TournamentAPI.fetch_sets()` as the source for main-event active sets where possible, but update the active set query to include `station` because the parser already supports station fields.

Add separate GraphQL queries for:

- tournament events with phases and phase groups for ladder discovery
- ladder event detail: `state`, `startAt`, `updatedAt`, `numEntrants`, phases, phase groups, active sets, standings
- tournament stations

Station availability should be derived from station numbers returned by `tournament.stations` minus station numbers assigned to active main or ladder sets. If station data is unavailable or inconsistent, omit the station availability block rather than showing misleading setup availability.

## UI Behavior

The existing pool-grid renderer remains the main-only view.

Split view should be a new dashboard layout:

- Left side: main bracket call list focused on late bracket, especially Top 24 and Top 8 when those phases exist
- Right side: ladder panel
- Ladder panel order: station availability, active/ready ladder matches, top standings

The late-bracket main list should use existing match priority rules: in progress first, ready next, waiting after that, and TBD-heavy rows dimmed. If Top 24 or Top 8 phases are present, prefer those phases in split mode. If they are not present, fall back to the active non-ladder sets from the selected main event.

Ladder-only view should use the full terminal:

- Header with ladder event name and update time
- Station availability
- Ready/in-progress ladder matches
- Wider standings list

Ladder waiting view should show:

- discovered ladder event name
- scheduled `startAt` if available
- current state, usually `CREATED`
- a concise message that the display will switch when the ladder is started

## Error Handling

If no ladder event is discovered:

- `auto`: stay main-only and log that no ladder event was found
- `split`: show main bracket plus a small "No ladder event found" ladder panel
- `ladder`: show a full-screen "No ladder event found" state

If ladder is discovered but not active:

- `auto`: stay main-only
- `split`: show main bracket plus waiting ladder panel
- `ladder`: show full-screen waiting ladder panel

If ladder fetch fails after a ladder state has already been shown, keep the last successful ladder state and update the timestamp/error indicator. This mirrors the current main bracket behavior, which preserves existing data on fetch failure.

If station fetch fails, keep match and standings display working and omit setup availability.

## Testing

Add unit tests for:

- ladder discovery by name containing `ladder`
- ladder discovery validation by `MATCHMAKING` phase/group
- no-ladder tournament behavior
- activation from `Event.state == ACTIVE`
- activation fallback from active sets or standings
- entrant count alone does not activate ladder visibility
- parsing standings W-L records from `setRecordWithoutByes`
- station availability derivation from station list and active set assignments
- view resolution for `auto`, `main`, `split`, and `ladder`

Add UI tests or snapshots for:

- main-only mode remains compatible with current snapshots
- `auto` before ladder activation shows main-only
- `auto` after ladder activation shows split view
- explicit `split` before ladder activation shows a waiting ladder panel
- explicit `ladder` before activation shows the ladder waiting state
- explicit `ladder` after activation shows station availability, ladder sets, and standings

Use injected API/dashboard dependencies for UI tests so snapshots do not depend on live start.gg data.

## Deployment Notes

For the primary TV, use the default:

```text
python -m matchcaller --token "$STARTGG_API_TOKEN" --short-url abbey --event-filter singles
```

This should default to `--view auto`.

For a dedicated ladder device:

```text
python -m matchcaller --token "$STARTGG_API_TOKEN" --short-url abbey --event-filter singles --view ladder
```

No tournament-night keyboard input is required. Configuration changes still require SSH/reboot, but the default primary-device behavior should dynamically adapt when the ladder starts.
