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

`auto` should be the default for real-data launches. It should preserve current startup ergonomics while supporting ladder without intervention:

1. Resolve the current tournament from the short URL.
2. Select the main event using the existing `--event-filter` behavior.
3. Discover the ladder event from the same tournament on each refresh until one is found.
4. Start in main-only view while the ladder event is undiscovered or the ladder visibility rule does not pass.
5. Switch to split view when the ladder visibility rule passes.

For `--short-url`, the coordinator can discover both the main event and the ladder event from the tournament. For `--slug`, the app should treat the provided slug as the main event and derive the tournament slug from it for ladder discovery. For `--event`, the app can fetch main sets but cannot reliably auto-discover a sibling ladder event unless a tournament slug is also known; in that case `auto` should behave like `main` and log that ladder discovery was skipped because only an event ID was provided.

Ladder discovery should not be a one-time startup step. If no ladder event is found, `auto`, `split`, and `ladder` modes should continue probing on later refreshes so a ladder created or exposed after the TUI starts can still appear without rebooting the Pi.

`main` keeps today's behavior: fetch and display only the selected main event.

`split` is an explicit two-panel mode. It should always keep the main bracket visible and render the ladder side according to `LadderDisplayStatus` rather than failing when the ladder is not found, waiting, or completed.

`ladder` is for a dedicated second device. It should auto-discover the ladder event, show a waiting state until ladder starts, and switch to the ladder board when the ladder visibility rule passes. If the event is already `COMPLETED` on a fresh launch, ladder-only mode can render a completed ladder board with final standings instead of waiting forever.

`--demo` and `--simulate` should preserve their current behavior unless a later fixture/simulator task explicitly adds ladder fixtures. If `--view ladder` or `--view split` is passed with demo or simulation mode before ladder fixtures exist, the app should log that ladder view is unsupported for that mode and fall back to the existing demo/simulation display.

## Ladder Activation

Track ladder state separately from whether `auto` should promote the split view:

```text
LadderDisplayStatus = not_found | waiting | active | completed
```

Use these statuses:

- `not_found`: no ladder event discovered yet
- `waiting`: ladder discovered, but not started and no active sets
- `active`: `Event.state == ACTIVE`, or `Event.state` is not `COMPLETED` or `INVALID` and active sets exist in states `[1, 2, 6]`
- `completed`: `Event.state == COMPLETED`

`auto` should switch from main-only to split when ladder status becomes `active`. It should not switch to split on a fresh launch if the ladder is already `completed`. If the app already showed the ladder as active during the current process and a later refresh reports `completed`, it can keep the split view and render final standings instead of making the ladder disappear.

Explicit `split` and `ladder` modes should render their ladder area based on `LadderDisplayStatus`: `not_found` means keep probing and show a not-found-yet panel, `waiting` means show a waiting panel, `active` means show live ladder, and `completed` means show the completed ladder board with standings when available.

The active status should be set when any of these are true:

- `Event.state == ACTIVE`
- `Event.state` is not `COMPLETED` or `INVALID`, and the ladder has active sets in states `[1, 2, 6]`

If the ladder event is `CREATED` and has no active sets, `auto` stays main-only and `ladder` mode shows a waiting screen with the discovered event name and scheduled `startAt` if available.

Entrant count should be fetched for display, but it should not make the ladder visible by itself. This avoids showing the ladder early if entrants are added before the TOs mark the ladder live.

Standings should be rendered once a ladder is already visible, or in explicit ladder views for a completed ladder, but standings should not activate `auto` by themselves. Completed ladders still expose standings, so using standings as a visibility signal would make a fresh `auto` launch after the event promote an already-finished ladder.

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
  ladder_was_visible: bool
  last_update: str

LadderState
  event_id: str | None
  event_name: str | None
  event_slug: str | None
  event_state: str | None
  start_at: int | None
  entrants_count: int
  sets: list[MatchData]
  standings: list[LadderStanding]
  display_status: not_found|waiting|active|completed
  auto_should_show: bool
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

- `auto`: stay main-only, log that no ladder event was found on this refresh, and keep probing on later refreshes
- `split`: show main bracket plus a small "No ladder event found yet" ladder panel, and keep probing on later refreshes
- `ladder`: show a full-screen "Looking for ladder event" state, and keep probing on later refreshes

If ladder is discovered with `waiting` status:

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
- ladder rediscovery continues after a no-ladder refresh
- activation from `Event.state == ACTIVE`
- activation fallback from active sets when the event is not completed or invalid
- completed ladder is renderable for explicit ladder mode but does not activate `auto` on a fresh launch
- `auto` can keep split view after a ladder that was already visible becomes completed
- entrant count alone does not activate ladder visibility
- standings alone do not activate ladder visibility
- event ID-only launches skip ladder discovery unless a tournament slug is also known
- demo and simulation modes preserve current behavior when ladder fixtures are unavailable
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
