# Refactor Plan

## Goals

- Make the display update path readable without tracing multiple timer and worker callbacks.
- Move sorting, grouping, and width decisions into pure functions that can be unit tested.
- Reduce the size and responsibility count of `matchcaller/ui/tournament_display.py`.
- Make API parsing easier to test without driving the full Textual app.

## Current Pain Points

- `matchcaller/ui/tournament_display.py` mixes timers, async fetch orchestration, DOM rebuild logic, row formatting, layout decisions, and alert rendering.
- Pool grouping, pool sorting, and column width selection are embedded in the UI class instead of living in pure helpers.
- `matchcaller/api/tournament_api.py` owns both transport and response-to-domain parsing.
- The app still relies heavily on integration tests for behavior that should be covered with smaller unit tests.

## Phase 1: Extract Pure Presentation Logic

- Create `matchcaller/ui/presentation.py` for pure helpers that:
  - group matches by pool
  - sort pools and matches
  - decide column counts and column widths from terminal width
  - build row strings and alert tags
- Move `TournamentDisplay._sort_pool_matches`, `_column_widths`, and `_match_row_data` logic into that module.
- Keep `TournamentDisplay` as the caller only.

## Phase 2: Isolate Pool Table Rendering

- Create `matchcaller/ui/pool_grid.py` with a small object or helper functions responsible for:
  - creating a pool `DataTable`
  - syncing rows into an existing `DataTable`
  - rebuilding the pool column layout
- Reduce `TournamentDisplay.update_table()` to:
  - compute presentation state
  - decide rebuild vs in-place sync
  - delegate actual widget mutation

## Phase 3: Separate Refresh Coordination

- Create `matchcaller/ui/refresh_controller.py` or similar to own:
  - poll timers
  - manual refresh triggering
  - “update in progress” / queued update state
  - fetch completion and error timestamp behavior
- Keep the Textual `App` responsible for binding keys and composing widgets, not coordinating state transitions.

## Phase 4: Split API Transport From Parsing

- Keep GraphQL request execution in `matchcaller/api/tournament_api.py` or rename it to a transport-focused client.
- Move response parsing into `matchcaller/api/parsers.py`.
- Add fixture-driven tests for parser edge cases:
  - unknown states
  - missing entrants
  - missing phase groups
  - station/stream metadata
  - slug resolution failures

## Phase 5: Tighten Test Strategy

- Add unit tests for presentation helpers instead of asserting the same behavior indirectly through the app.
- Keep a small number of Textual integration tests for:
  - refresh without rebuild
  - empty state
  - narrow terminal layout
  - snapshot regressions
- Add parser fixture tests so API coverage does not depend on large mocked response objects inline.

## Suggested Order

1. Extract presentation helpers with no behavior changes.
2. Extract pool grid rendering and keep existing snapshots passing.
3. Move refresh coordination into a dedicated controller.
4. Split API parsing from transport and convert tests to fixtures.
5. Remove dead compatibility paths that are no longer needed after the split.

## Exit Criteria

- `TournamentDisplay` is mostly compose/bind/wire-up code.
- Pool sorting and layout decisions are testable without Textual.
- API parsing is testable without spinning up the app.
- The current snapshot suite remains small and focused on visual regressions, not business logic.

## Status

- Phase 1 completed: pure presentation logic extracted to `matchcaller/ui/presentation.py`
- Phase 2 completed: pool grid rendering and sync extracted to `matchcaller/ui/pool_grid.py`
- Phase 3 completed: refresh coordination extracted to `matchcaller/ui/refresh_controller.py`
- Phase 4 completed: API parsing split into `matchcaller/api/parsers.py` with query definitions in `matchcaller/api/queries.py`
- Additional second-pass refactor completed: app-shell dependency injection in `matchcaller/ui/dependencies.py` and HTTP transport injection in `matchcaller/api/transport.py`
- Current verification baseline: `pytest -q` passing with `98` tests and `9` passing snapshots

## Deferred Next Pass

- Extract the remaining fetch/apply/update orchestration from `matchcaller/ui/tournament_display.py` into a dedicated coordinator or presenter-facing service
- Reduce legacy compatibility in `matchcaller/models/match.py` once downstream callers are normalized
- Move remaining older tests and snapshot harnesses to the newer injected seams
- Extend transport injection to the rest of the network code, especially simulator/cloner paths
- Run hardware validation on the Raspberry Pi target environment
