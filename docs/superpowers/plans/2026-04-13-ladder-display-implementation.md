# Ladder Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add auto-discovered start.gg ladder support with `auto`, `main`, `split`, and `ladder` TUI modes while preserving the current main-bracket display path.

**Architecture:** Add small dashboard models and pure helpers first, then add a dashboard API coordinator that composes existing `TournamentAPI` behavior with ladder discovery/detail/station queries. Finally wire CLI/view-mode selection into `TournamentDisplay` and add a Textual-specific dashboard renderer for split and ladder-only views.

**Tech Stack:** Python 3.11, Pydantic models via the existing `DictCompatibleBaseModel`, aiohttp through the existing `HTTPTransport`, Textual widgets, pytest and pytest-asyncio.

---

## File Structure

- Create `matchcaller/models/dashboard.py`: view-mode enums, ladder display statuses, station/standing/dashboard models, and pure view/status helpers.
- Modify `matchcaller/models/__init__.py`: export the new dashboard model names used by UI/API modules.
- Create `tests/test_dashboard_models.py`: unit tests for ladder status, auto view promotion, station availability, and late-bracket filtering helpers.
- Modify `matchcaller/api/queries.py`: add GraphQL documents for tournament event discovery, ladder event detail, and tournament stations; add `station` to the existing active sets query.
- Create `matchcaller/api/dashboard_api.py`: `TournamentDashboardAPI` coordinator and dict-based parsers for new dashboard query payloads.
- Modify `matchcaller/api/__init__.py`: export `TournamentDashboardAPI`.
- Create `tests/test_dashboard_api.py`: transport-injected tests for discovery, rediscovery, completed ladders, station parsing, and event-ID-only fallback.
- Modify `matchcaller/ui/dependencies.py`: add a `DashboardDataSource` protocol.
- Create `matchcaller/ui/dashboard_grid.py`: Textual-specific split/ladder layout manager.
- Modify `matchcaller/ui/tournament_display.py`: add view-mode/dashboard-source support and route `update_table()` between existing pool grid and new dashboard grid.
- Modify `matchcaller/__main__.py`: parse `--view`, default real-data launches to `auto`, pass `tournament_slug` and view mode into `TournamentDisplay`, and preserve demo/simulation behavior.
- Modify focused tests in `tests/test_demo_mode.py` and `tests/test_display_injection.py`; keep snapshot helper apps on the main-only path by preserving `view_mode="main"` as the `TournamentDisplay` constructor default.

## Task 1: Dashboard Models And Pure Helpers

**Files:**
- Create: `matchcaller/models/dashboard.py`
- Modify: `matchcaller/models/__init__.py`
- Test: `tests/test_dashboard_models.py`

- [ ] **Step 1: Write failing model/helper tests**

Create `tests/test_dashboard_models.py`:

```python
"""Unit tests for dashboard mode and ladder helper models."""

import pytest

from matchcaller.models.dashboard import (
    DashboardState,
    LadderDisplayStatus,
    LadderState,
    LadderStanding,
    Station,
    ViewMode,
    derive_ladder_display_status,
    derive_station_state,
    filter_late_bracket_matches,
    resolve_dashboard_view,
)
from matchcaller.models.match import MatchData, MatchRow, PlayerData, TournamentState


def _match(
    match_id: int,
    *,
    display_name: str,
    pool_name: str,
    state: int = 2,
    station: int | None = None,
) -> MatchRow:
    return MatchRow(
        MatchData(
            id=match_id,
            displayName=display_name,
            poolName=pool_name,
            player1=PlayerData(tag=f"Player {match_id}A"),
            player2=PlayerData(tag=f"Player {match_id}B"),
            state=state,
            updatedAt=100 + match_id,
            station=station,
        )
    )


@pytest.mark.unit
class TestDashboardModels:
    def test_ladder_status_not_found_waiting_active_completed(self):
        assert derive_ladder_display_status(
            event_state=None,
            active_set_count=0,
        ) == LadderDisplayStatus.NOT_FOUND
        assert derive_ladder_display_status(
            event_state="CREATED",
            active_set_count=0,
        ) == LadderDisplayStatus.WAITING
        assert derive_ladder_display_status(
            event_state="ACTIVE",
            active_set_count=0,
        ) == LadderDisplayStatus.ACTIVE
        assert derive_ladder_display_status(
            event_state="CREATED",
            active_set_count=2,
        ) == LadderDisplayStatus.ACTIVE
        assert derive_ladder_display_status(
            event_state="COMPLETED",
            active_set_count=2,
        ) == LadderDisplayStatus.COMPLETED

    def test_auto_does_not_promote_completed_fresh_launch_but_keeps_visible_ladder(self):
        completed = LadderState(
            display_status=LadderDisplayStatus.COMPLETED,
            event_id="1",
            event_name="Melee Ladder",
            event_slug="tournament/test/event/ladder",
            event_state="COMPLETED",
            start_at=None,
            entrants_count=10,
            sets=[],
            standings=[LadderStanding(placement=1, entrant_name="Snap", wins=8, losses=0)],
            auto_should_show=False,
        )

        assert resolve_dashboard_view(
            requested_view=ViewMode.AUTO,
            ladder=completed,
            ladder_was_visible=False,
        ) == ViewMode.MAIN
        assert resolve_dashboard_view(
            requested_view=ViewMode.AUTO,
            ladder=completed,
            ladder_was_visible=True,
        ) == ViewMode.SPLIT

    def test_explicit_modes_resolve_without_auto_promotion(self):
        waiting = LadderState(
            display_status=LadderDisplayStatus.WAITING,
            event_id="1",
            event_name="Melee Ladder",
            event_slug="tournament/test/event/ladder",
            event_state="CREATED",
            start_at=1776229200,
            entrants_count=0,
            sets=[],
            standings=[],
            auto_should_show=False,
        )

        assert resolve_dashboard_view(ViewMode.MAIN, waiting) == ViewMode.MAIN
        assert resolve_dashboard_view(ViewMode.SPLIT, waiting) == ViewMode.SPLIT
        assert resolve_dashboard_view(ViewMode.LADDER, waiting) == ViewMode.LADDER

    def test_station_availability_uses_active_match_station_numbers(self):
        state = derive_station_state(
            stations=[
                Station(id="s1", number=1),
                Station(id="s2", number=2),
                Station(id="s3", number=3),
            ],
            active_matches=[
                _match(1, display_name="Top 24 - WQ", pool_name="Top 24", station=2),
                _match(2, display_name="Ladder - Round 1", pool_name="Ladder", station=None),
            ],
        )

        assert state.occupied_numbers == {2}
        assert state.available_numbers == [1, 3]

    def test_filter_late_bracket_matches_prefers_top_24_and_top_8(self):
        matches = [
            _match(1, display_name="Pool A - Round 1", pool_name="Bracket - Pool 1"),
            _match(2, display_name="Top 24 - Winners", pool_name="Top 24 - Pool 1"),
            _match(3, display_name="Top 8 - Winners", pool_name="Top 8 - Pool 1"),
        ]

        assert [match.id for match in filter_late_bracket_matches(matches)] == [2, 3]

    def test_filter_late_bracket_matches_falls_back_to_all_matches(self):
        matches = [
            _match(1, display_name="Bracket - Round 1", pool_name="Bracket - Pool 1"),
            _match(2, display_name="Bracket - Round 2", pool_name="Bracket - Pool 2"),
        ]

        assert [match.id for match in filter_late_bracket_matches(matches)] == [1, 2]

    def test_dashboard_state_tracks_ladder_was_visible(self):
        main = TournamentState(event_name="Singles", tournament_name="Weekly", sets=[])
        dashboard = DashboardState(
            tournament_name="Weekly",
            main=main,
            ladder=None,
            stations=None,
            requested_view=ViewMode.AUTO,
            resolved_view=ViewMode.MAIN,
            ladder_was_visible=False,
            last_update="12:00:00",
        )

        assert dashboard.main is main
        assert dashboard.ladder is None
        assert dashboard.resolved_view == ViewMode.MAIN
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
pytest tests/test_dashboard_models.py -v
```

Expected: FAIL during import with `ModuleNotFoundError: No module named 'matchcaller.models.dashboard'`.

- [ ] **Step 3: Add dashboard models and helpers**

Create `matchcaller/models/dashboard.py`:

```python
"""Dashboard data models and pure helper functions."""

from enum import Enum
from typing import Sequence

from pydantic import Field

from .match import DictCompatibleBaseModel, MatchData, MatchRow, TournamentState


class ViewMode(str, Enum):
    """Supported runtime display modes."""

    AUTO = "auto"
    MAIN = "main"
    SPLIT = "split"
    LADDER = "ladder"


class LadderDisplayStatus(str, Enum):
    """Render status for the ladder portion of the dashboard."""

    NOT_FOUND = "not_found"
    WAITING = "waiting"
    ACTIVE = "active"
    COMPLETED = "completed"


class LadderStanding(DictCompatibleBaseModel):
    """One row in the ladder standings table."""

    placement: int
    entrant_name: str
    wins: int | None = None
    losses: int | None = None
    win_percentage: str | None = None

    @property
    def record_text(self) -> str:
        """Return the W-L record for compact display."""
        if self.wins is None or self.losses is None:
            return "-"
        return f"{self.wins}-{self.losses}"


class Station(DictCompatibleBaseModel):
    """Tournament setup/station metadata."""

    id: str | int
    number: int
    enabled: bool | None = None


class StationState(DictCompatibleBaseModel):
    """Available and occupied station numbers."""

    stations: list[Station]
    occupied_numbers: set[int] = Field(default_factory=set)
    available_numbers: list[int] = Field(default_factory=list)


class LadderState(DictCompatibleBaseModel):
    """Current ladder event state."""

    display_status: LadderDisplayStatus
    event_id: str | int | None = None
    event_name: str | None = None
    event_slug: str | None = None
    event_state: str | None = None
    start_at: int | None = None
    entrants_count: int = 0
    sets: list[MatchData] = Field(default_factory=list)
    standings: list[LadderStanding] = Field(default_factory=list)
    auto_should_show: bool = False
    waiting_reason: str | None = None


class DashboardState(DictCompatibleBaseModel):
    """Combined main bracket and ladder dashboard state."""

    tournament_name: str
    main: TournamentState | None = None
    ladder: LadderState | None = None
    stations: StationState | None = None
    requested_view: ViewMode = ViewMode.AUTO
    resolved_view: ViewMode = ViewMode.MAIN
    ladder_was_visible: bool = False
    last_update: str


def derive_ladder_display_status(
    *,
    event_state: str | None,
    active_set_count: int,
) -> LadderDisplayStatus:
    """Derive the ladder display status from public start.gg fields."""
    if event_state is None:
        return LadderDisplayStatus.NOT_FOUND

    normalized_state = event_state.upper()
    if normalized_state == "COMPLETED":
        return LadderDisplayStatus.COMPLETED
    if normalized_state == "ACTIVE":
        return LadderDisplayStatus.ACTIVE
    if normalized_state != "INVALID" and active_set_count > 0:
        return LadderDisplayStatus.ACTIVE
    return LadderDisplayStatus.WAITING


def resolve_dashboard_view(
    requested_view: ViewMode,
    ladder: LadderState | None,
    *,
    ladder_was_visible: bool = False,
) -> ViewMode:
    """Resolve the actual view to render for a dashboard refresh."""
    if requested_view == ViewMode.MAIN:
        return ViewMode.MAIN
    if requested_view in {ViewMode.SPLIT, ViewMode.LADDER}:
        return requested_view

    if ladder is None:
        return ViewMode.MAIN
    if ladder.display_status == LadderDisplayStatus.ACTIVE:
        return ViewMode.SPLIT
    if ladder.display_status == LadderDisplayStatus.COMPLETED and ladder_was_visible:
        return ViewMode.SPLIT
    return ViewMode.MAIN


def derive_station_state(
    *,
    stations: Sequence[Station],
    active_matches: Sequence[MatchRow],
) -> StationState:
    """Build station availability from configured stations and active matches."""
    occupied_numbers = {
        match.station
        for match in active_matches
        if match.station is not None
    }
    station_numbers = [
        station.number
        for station in stations
        if station.enabled is not False
    ]
    available_numbers = [
        number
        for number in sorted(station_numbers)
        if number not in occupied_numbers
    ]
    return StationState(
        stations=list(stations),
        occupied_numbers=occupied_numbers,
        available_numbers=available_numbers,
    )


def filter_late_bracket_matches(matches: Sequence[MatchRow]) -> list[MatchRow]:
    """Prefer Top 24/Top 8 matches in split view, falling back to all matches."""
    late_matches = [
        match
        for match in matches
        if _has_late_bracket_label(match.bracket) or _has_late_bracket_label(match.pool)
    ]
    return late_matches or list(matches)


def _has_late_bracket_label(value: str) -> bool:
    normalized = value.lower()
    return "top 24" in normalized or "top 8" in normalized
```

Modify `matchcaller/models/__init__.py`:

```python
"""Data models for tournament matches."""

from .dashboard import (
    DashboardState,
    LadderDisplayStatus,
    LadderStanding,
    LadderState,
    Station,
    StationState,
    ViewMode,
)
from .match import MatchRow, MatchState

__all__ = [
    "DashboardState",
    "LadderDisplayStatus",
    "LadderStanding",
    "LadderState",
    "MatchRow",
    "MatchState",
    "Station",
    "StationState",
    "ViewMode",
]
```

- [ ] **Step 4: Run the focused tests and verify they pass**

Run:

```bash
pytest tests/test_dashboard_models.py -v
```

Expected: PASS for all tests in `tests/test_dashboard_models.py`.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add matchcaller/models/dashboard.py matchcaller/models/__init__.py tests/test_dashboard_models.py
git commit -m "Add dashboard ladder models"
```

## Task 2: Dashboard API Coordinator And Parsers

**Files:**
- Modify: `matchcaller/api/queries.py`
- Create: `matchcaller/api/dashboard_api.py`
- Modify: `matchcaller/api/__init__.py`
- Test: `tests/test_dashboard_api.py`

- [ ] **Step 1: Write failing dashboard API tests**

Create `tests/test_dashboard_api.py`:

```python
"""Unit tests for the dashboard API coordinator."""

import pytest

from matchcaller.api.dashboard_api import (
    TournamentDashboardAPI,
    derive_tournament_slug_from_event_slug,
)
from matchcaller.api.transport import HTTPResult
from matchcaller.models.dashboard import LadderDisplayStatus, ViewMode


class FakeTransport:
    """Queue-backed fake transport for dashboard API tests."""

    def __init__(self, post_results: list[HTTPResult]) -> None:
        self.post_results = list(post_results)
        self.post_calls: list[dict] = []

    async def post_json(self, url, *, payload, headers, timeout_seconds):
        self.post_calls.append(
            {
                "url": url,
                "payload": payload,
                "headers": headers,
                "timeout_seconds": timeout_seconds,
            }
        )
        return self.post_results.pop(0)


def _result(json_data: dict) -> HTTPResult:
    return HTTPResult(status=200, text="", json_data=json_data)


def _event_sets_payload(event_name: str = "Singles") -> dict:
    return {
        "data": {
            "event": {
                "name": event_name,
                "tournament": {"name": "Melee @ Abbey Tavern"},
                "sets": {"nodes": []},
            }
        }
    }


def _discovery_payload(*, ladder_state: str = "CREATED") -> dict:
    return {
        "data": {
            "tournament": {
                "name": "Melee @ Abbey Tavern",
                "events": [
                    {
                        "id": 11,
                        "name": "Melee Singles",
                        "slug": "tournament/weekly/event/singles",
                        "state": "ACTIVE",
                        "startAt": 100,
                        "numEntrants": 32,
                        "phases": [
                            {"id": 21, "name": "Top 24", "bracketType": "DOUBLE_ELIMINATION"}
                        ],
                        "phaseGroups": [],
                    },
                    {
                        "id": 12,
                        "name": "Melee Ladder",
                        "slug": "tournament/weekly/event/melee-ladder",
                        "state": ladder_state,
                        "startAt": 200,
                        "numEntrants": 10,
                        "phases": [
                            {"id": 22, "name": "Ladder", "bracketType": "MATCHMAKING"}
                        ],
                        "phaseGroups": [
                            {
                                "id": 31,
                                "displayIdentifier": "1",
                                "bracketType": "MATCHMAKING",
                                "phase": {"id": 22, "name": "Ladder", "bracketType": "MATCHMAKING"},
                            }
                        ],
                    },
                ],
            }
        }
    }


def _ladder_detail_payload(*, event_state: str = "ACTIVE", active_sets: list[dict] | None = None) -> dict:
    return {
        "data": {
            "event": {
                "id": 12,
                "name": "Melee Ladder",
                "slug": "tournament/weekly/event/melee-ladder",
                "state": event_state,
                "startAt": 200,
                "updatedAt": 250,
                "numEntrants": 10,
                "sets": {
                    "pageInfo": {"total": len(active_sets or [])},
                    "nodes": active_sets or [],
                },
                "standings": {
                    "pageInfo": {"total": 1},
                    "nodes": [
                        {
                            "id": 1,
                            "placement": 1,
                            "entrant": {"id": 1, "name": "Snap", "participants": [{"gamerTag": "Snap"}]},
                            "setRecordWithoutByes": {"wins": 8, "losses": 0, "winPercentage": "100%"},
                        }
                    ],
                },
            }
        }
    }


def _stations_payload() -> dict:
    return {
        "data": {
            "tournament": {
                "stations": {
                    "pageInfo": {"total": 2, "totalPages": 1},
                    "nodes": [
                        {"id": "s1", "number": 1, "enabled": True},
                        {"id": "s2", "number": 2, "enabled": True},
                    ],
                }
            }
        }
    }


@pytest.mark.unit
class TestTournamentDashboardAPI:
    def test_derive_tournament_slug_from_event_slug(self):
        assert derive_tournament_slug_from_event_slug(
            "tournament/melee-abbey-tavern-137/event/singles"
        ) == "melee-abbey-tavern-137"
        assert derive_tournament_slug_from_event_slug("not-an-event-slug") is None

    @pytest.mark.asyncio
    async def test_fetch_dashboard_discovers_active_ladder_and_resolves_split(self):
        active_set = {
            "id": 100,
            "fullRoundText": "Round 1",
            "identifier": None,
            "state": 2,
            "updatedAt": 300,
            "startedAt": 290,
            "round": 1,
            "station": {"number": 2},
            "stream": None,
            "phaseGroup": {
                "displayIdentifier": "1",
                "phase": {"name": "Ladder"},
            },
            "slots": [
                {"entrant": {"participants": [{"gamerTag": "Snap"}]}},
                {"entrant": {"participants": [{"gamerTag": "Chetter"}]}},
            ],
        }
        transport = FakeTransport(
            [
                _result(_event_sets_payload()),
                _result(_discovery_payload(ladder_state="ACTIVE")),
                _result(_ladder_detail_payload(event_state="ACTIVE", active_sets=[active_set])),
                _result(_stations_payload()),
            ]
        )
        api = TournamentDashboardAPI(
            api_token="token",
            event_slug="tournament/weekly/event/singles",
            tournament_slug="weekly",
            requested_view=ViewMode.AUTO,
            transport=transport,
        )

        dashboard = await api.fetch_dashboard_state()

        assert dashboard.resolved_view == ViewMode.SPLIT
        assert dashboard.ladder is not None
        assert dashboard.ladder.display_status == LadderDisplayStatus.ACTIVE
        assert dashboard.ladder.standings[0].record_text == "8-0"
        assert dashboard.stations is not None
        assert dashboard.stations.occupied_numbers == {2}
        assert dashboard.stations.available_numbers == [1]

    @pytest.mark.asyncio
    async def test_fetch_dashboard_keeps_auto_main_when_ladder_not_found_and_retries_next_refresh(self):
        transport = FakeTransport(
            [
                _result(_event_sets_payload()),
                _result({"data": {"tournament": {"name": "Weekly", "events": []}}}),
                _result(_stations_payload()),
                _result(_event_sets_payload()),
                _result(_discovery_payload(ladder_state="ACTIVE")),
                _result(_ladder_detail_payload(event_state="ACTIVE", active_sets=[])),
                _result(_stations_payload()),
            ]
        )
        api = TournamentDashboardAPI(
            api_token="token",
            event_slug="tournament/weekly/event/singles",
            tournament_slug="weekly",
            requested_view=ViewMode.AUTO,
            transport=transport,
        )

        first = await api.fetch_dashboard_state()
        second = await api.fetch_dashboard_state(previous_state=first)

        assert first.resolved_view == ViewMode.MAIN
        assert first.ladder is not None
        assert first.ladder.display_status == LadderDisplayStatus.NOT_FOUND
        assert second.ladder is not None
        assert second.ladder.display_status == LadderDisplayStatus.ACTIVE
        assert second.resolved_view == ViewMode.SPLIT

    @pytest.mark.asyncio
    async def test_completed_ladder_does_not_promote_auto_on_fresh_launch(self):
        transport = FakeTransport(
            [
                _result(_event_sets_payload()),
                _result(_discovery_payload(ladder_state="COMPLETED")),
                _result(_ladder_detail_payload(event_state="COMPLETED", active_sets=[])),
                _result(_stations_payload()),
            ]
        )
        api = TournamentDashboardAPI(
            api_token="token",
            event_slug="tournament/weekly/event/singles",
            tournament_slug="weekly",
            requested_view=ViewMode.AUTO,
            transport=transport,
        )

        dashboard = await api.fetch_dashboard_state()

        assert dashboard.ladder is not None
        assert dashboard.ladder.display_status == LadderDisplayStatus.COMPLETED
        assert dashboard.resolved_view == ViewMode.MAIN

    @pytest.mark.asyncio
    async def test_event_id_only_auto_skips_ladder_discovery(self):
        transport = FakeTransport([_result(_event_sets_payload())])
        api = TournamentDashboardAPI(
            api_token="token",
            event_id="12345",
            requested_view=ViewMode.AUTO,
            transport=transport,
        )

        dashboard = await api.fetch_dashboard_state()

        assert dashboard.resolved_view == ViewMode.MAIN
        assert dashboard.ladder is None
        assert len(transport.post_calls) == 1
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
pytest tests/test_dashboard_api.py -v
```

Expected: FAIL during import with `ModuleNotFoundError: No module named 'matchcaller.api.dashboard_api'`.

- [ ] **Step 3: Add GraphQL query documents**

Modify `matchcaller/api/queries.py` by adding `station` to `EVENT_SETS_QUERY` nodes if it is not already present:

```graphql
station {
    number
}
```

Then append these query constants:

```python
TOURNAMENT_DASHBOARD_EVENTS_QUERY = """
query TournamentDashboardEvents($slug: String!) {
    tournament(slug: $slug) {
        name
        events {
            id
            name
            slug
            state
            startAt
            numEntrants
            phases {
                id
                name
                bracketType
            }
            phaseGroups {
                id
                displayIdentifier
                bracketType
                phase {
                    id
                    name
                    bracketType
                }
            }
        }
    }
}
"""


LADDER_EVENT_DETAIL_QUERY = """
query LadderEventDetail($slug: String!, $page: Int!, $perPage: Int!) {
    event(slug: $slug) {
        id
        name
        slug
        state
        startAt
        updatedAt
        numEntrants
        sets(
            page: $page
            perPage: $perPage
            sortType: CALL_ORDER
            filters: {
                state: [1, 2, 6]
            }
        ) {
            pageInfo {
                total
                totalPages
            }
            nodes {
                id
                fullRoundText
                identifier
                state
                updatedAt
                startedAt
                round
                slots {
                    entrant {
                        participants {
                            gamerTag
                            user {
                                authorizations(types: [DISCORD]) {
                                    externalUsername
                                    externalId
                                }
                            }
                        }
                    }
                }
                phaseGroup {
                    displayIdentifier
                    phase {
                        name
                    }
                }
                station {
                    number
                }
                stream {
                    streamName
                }
            }
        }
        standings(query: { page: 1, perPage: 20 }) {
            pageInfo {
                total
                totalPages
            }
            nodes {
                id
                placement
                entrant {
                    id
                    name
                    participants {
                        gamerTag
                    }
                }
                setRecordWithoutByes
            }
        }
    }
}
"""


TOURNAMENT_STATIONS_QUERY = """
query TournamentStations($slug: String!) {
    tournament(slug: $slug) {
        stations(page: 1, perPage: 100) {
            pageInfo {
                total
                totalPages
            }
            nodes {
                id
                number
                enabled
            }
        }
    }
}
"""
```

- [ ] **Step 4: Implement `TournamentDashboardAPI` and parsers**

Create `matchcaller/api/dashboard_api.py`:

```python
"""Dashboard API coordinator for main bracket plus ladder display."""

from datetime import datetime
from typing import Any

import aiohttp

from ..models.dashboard import (
    DashboardState,
    LadderDisplayStatus,
    LadderStanding,
    LadderState,
    Station,
    ViewMode,
    derive_ladder_display_status,
    derive_station_state,
    resolve_dashboard_view,
)
from ..models.match import MatchData, MatchRow, PlayerData, TournamentState
from ..utils.logging import log
from .parsers import parse_event_sets_response, validate_startgg_response
from .queries import (
    EVENT_SETS_QUERY,
    LADDER_EVENT_DETAIL_QUERY,
    TOURNAMENT_DASHBOARD_EVENTS_QUERY,
    TOURNAMENT_STATIONS_QUERY,
)
from .transport import AiohttpTransport, HTTPTransport


def derive_tournament_slug_from_event_slug(event_slug: str | None) -> str | None:
    """Extract the tournament slug segment from a start.gg event slug."""
    if not event_slug:
        return None
    prefix = "tournament/"
    marker = "/event/"
    if not event_slug.startswith(prefix) or marker not in event_slug:
        return None
    return event_slug[len(prefix): event_slug.index(marker)]


class TournamentDashboardAPI:
    """Fetch combined main bracket and ladder dashboard state."""

    def __init__(
        self,
        *,
        api_token: str | None,
        event_id: str | None = None,
        event_slug: str | None = None,
        tournament_slug: str | None = None,
        requested_view: ViewMode = ViewMode.AUTO,
        transport: HTTPTransport | None = None,
    ) -> None:
        self.api_token = api_token
        self.event_id = event_id
        self.event_slug = event_slug
        self.tournament_slug = tournament_slug or derive_tournament_slug_from_event_slug(event_slug)
        self.requested_view = requested_view
        self.transport = transport or AiohttpTransport()
        self.base_url = "https://api.start.gg/gql/alpha"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    async def fetch_dashboard_state(
        self,
        previous_state: DashboardState | None = None,
    ) -> DashboardState:
        """Fetch one combined dashboard refresh."""
        main = await self._fetch_main_state()
        tournament_name = main.tournament_name
        ladder_was_visible = bool(previous_state and previous_state.ladder_was_visible)

        ladder: LadderState | None = None
        stations = None
        if self.tournament_slug:
            ladder_summary = await self._discover_ladder_summary()
            if ladder_summary:
                ladder = await self._fetch_ladder_state(ladder_summary)
            else:
                ladder = LadderState(
                    display_status=LadderDisplayStatus.NOT_FOUND,
                    event_state=None,
                    auto_should_show=False,
                    waiting_reason="No ladder event found yet",
                )
            all_matches = [*main.sets]
            if ladder:
                all_matches.extend(ladder.sets)
            stations = await self._fetch_station_state([MatchRow(match) for match in all_matches])
        elif self.requested_view == ViewMode.AUTO:
            log("Ladder discovery skipped: no tournament slug available")

        resolved_view = resolve_dashboard_view(
            self.requested_view,
            ladder,
            ladder_was_visible=ladder_was_visible,
        )
        ladder_visible_now = resolved_view == ViewMode.SPLIT or self.requested_view == ViewMode.LADDER

        return DashboardState(
            tournament_name=tournament_name,
            main=main,
            ladder=ladder,
            stations=stations,
            requested_view=self.requested_view,
            resolved_view=resolved_view,
            ladder_was_visible=ladder_was_visible or ladder_visible_now,
            last_update=datetime.now().strftime("%H:%M:%S"),
        )

    async def _post_graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        response = await self.transport.post_json(
            self.base_url,
            payload={"query": query, "variables": variables},
            headers=self._headers(),
            timeout_seconds=10,
        )
        if response.status != 200:
            raise aiohttp.ClientError(f"HTTP {response.status}: {response.text}")
        if not isinstance(response.json_data, dict):
            raise Exception("Expected JSON object from start.gg API")
        if response.json_data.get("errors"):
            raise Exception(f"GraphQL errors: {response.json_data['errors']}")
        return response.json_data

    async def _fetch_main_state(self) -> TournamentState:
        variables = {"eventId": self.event_id, "page": 1, "perPage": 100}
        if self.event_slug and not self.event_id:
            event_id = await self._fetch_event_id_from_slug(self.event_slug)
            self.event_id = event_id
            variables["eventId"] = event_id
        if not variables["eventId"]:
            raise Exception("Dashboard API requires event_id or event_slug for main event")
        raw = await self._post_graphql(EVENT_SETS_QUERY, variables)
        return parse_event_sets_response(validate_startgg_response(raw))

    async def _fetch_event_id_from_slug(self, event_slug: str) -> str:
        from .queries import EVENT_ID_BY_SLUG_QUERY

        raw = await self._post_graphql(EVENT_ID_BY_SLUG_QUERY, {"slug": event_slug})
        event = (raw.get("data") or {}).get("event") or {}
        if not event.get("id"):
            raise Exception(f"Could not resolve event ID from slug: {event_slug}")
        return str(event["id"])

    async def _discover_ladder_summary(self) -> dict[str, Any] | None:
        raw = await self._post_graphql(
            TOURNAMENT_DASHBOARD_EVENTS_QUERY,
            {"slug": self.tournament_slug},
        )
        events = ((raw.get("data") or {}).get("tournament") or {}).get("events") or []
        for event in events:
            if _is_ladder_event(event):
                return event
        return None

    async def _fetch_ladder_state(self, summary: dict[str, Any]) -> LadderState:
        raw = await self._post_graphql(
            LADDER_EVENT_DETAIL_QUERY,
            {"slug": summary["slug"], "page": 1, "perPage": 100},
        )
        event = (raw.get("data") or {}).get("event") or {}
        sets = [_parse_match_data(node) for node in ((event.get("sets") or {}).get("nodes") or [])]
        standings = [_parse_standing(node) for node in ((event.get("standings") or {}).get("nodes") or [])]
        status = derive_ladder_display_status(
            event_state=event.get("state"),
            active_set_count=len(sets),
        )
        return LadderState(
            display_status=status,
            event_id=str(event.get("id")) if event.get("id") is not None else None,
            event_name=event.get("name"),
            event_slug=event.get("slug"),
            event_state=event.get("state"),
            start_at=event.get("startAt"),
            entrants_count=event.get("numEntrants") or 0,
            sets=sets,
            standings=standings,
            auto_should_show=status == LadderDisplayStatus.ACTIVE,
            waiting_reason=None if status == LadderDisplayStatus.ACTIVE else "Ladder is not active yet",
        )

    async def _fetch_station_state(self, active_matches: list[MatchRow]):
        if not self.tournament_slug:
            return None
        raw = await self._post_graphql(TOURNAMENT_STATIONS_QUERY, {"slug": self.tournament_slug})
        nodes = (((raw.get("data") or {}).get("tournament") or {}).get("stations") or {}).get("nodes") or []
        stations = [
            Station(id=node["id"], number=node["number"], enabled=node.get("enabled"))
            for node in nodes
            if node.get("number") is not None
        ]
        return derive_station_state(stations=stations, active_matches=active_matches)


def _is_ladder_event(event: dict[str, Any]) -> bool:
    name_matches = "ladder" in (event.get("name") or "").lower()
    phase_matches = any(
        phase.get("bracketType") == "MATCHMAKING"
        for phase in (event.get("phases") or [])
    )
    group_matches = any(
        group.get("bracketType") == "MATCHMAKING"
        for group in (event.get("phaseGroups") or [])
    )
    return name_matches and (phase_matches or group_matches or not event.get("phases"))


def _parse_match_data(node: dict[str, Any]) -> MatchData:
    players = []
    for slot in node.get("slots") or []:
        entrant = slot.get("entrant") if slot else None
        participants = (entrant or {}).get("participants") or []
        players.append(PlayerData(tag=(participants[0] or {}).get("gamerTag", "TBD") if participants else "TBD"))
    while len(players) < 2:
        players.append(PlayerData(tag="TBD"))
    phase_group = node.get("phaseGroup") or {}
    phase = phase_group.get("phase") or {}
    phase_name = phase.get("name") or "Ladder"
    round_text = node.get("fullRoundText") or node.get("identifier") or "Round"
    pool_name = f"{phase_name} - Pool {phase_group.get('displayIdentifier')}" if phase_group.get("displayIdentifier") else phase_name
    station = node.get("station") or {}
    stream = node.get("stream") or {}
    return MatchData(
        id=node["id"],
        displayName=f"{phase_name} - {round_text}",
        poolName=pool_name,
        phase_group=pool_name,
        phase_name=phase_name,
        player1=players[0],
        player2=players[1],
        state=node["state"],
        updatedAt=node.get("updatedAt"),
        startedAt=node.get("startedAt"),
        station=station.get("number"),
        stream=stream.get("streamName"),
    )


def _parse_standing(node: dict[str, Any]) -> LadderStanding:
    record = node.get("setRecordWithoutByes") or {}
    entrant = node.get("entrant") or {}
    return LadderStanding(
        placement=node.get("placement") or 0,
        entrant_name=entrant.get("name") or "Unknown",
        wins=record.get("wins"),
        losses=record.get("losses"),
        win_percentage=record.get("winPercentage"),
    )
```

Modify `matchcaller/api/__init__.py` to export `TournamentDashboardAPI`:

```python
from .dashboard_api import TournamentDashboardAPI
```

Add `"TournamentDashboardAPI"` to `__all__`.

- [ ] **Step 5: Run focused API tests**

Run:

```bash
pytest tests/test_dashboard_api.py tests/test_api_parsers.py tests/test_api_transport.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git add matchcaller/api/queries.py matchcaller/api/dashboard_api.py matchcaller/api/__init__.py tests/test_dashboard_api.py tests/test_api_parsers.py tests/test_api_transport.py
git commit -m "Add dashboard API coordinator"
```

## Task 3: CLI View Mode And Data Source Wiring

**Files:**
- Modify: `matchcaller/ui/dependencies.py`
- Modify: `matchcaller/ui/tournament_display.py`
- Modify: `matchcaller/__main__.py`
- Test: `tests/test_demo_mode.py`
- Test: `tests/test_display_injection.py`

- [ ] **Step 1: Write failing CLI and injection tests**

Append tests to `tests/test_demo_mode.py`:

```python
    def test_event_id_real_mode_defaults_auto_without_tournament_slug(self):
        test_args = ["--token", "real_token", "--event", "12345"]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):
            mock_app_class.return_value.run.return_value = None

            main()

            kwargs = mock_app_class.call_args.kwargs
            assert kwargs["view_mode"] == "auto"
            assert kwargs["tournament_slug"] is None

    def test_real_mode_defaults_to_auto_view(self):
        test_args = ["--token", "real_token", "--slug", "tournament/test/event/singles"]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):
            mock_app_class.return_value.run.return_value = None

            main()

            kwargs = mock_app_class.call_args.kwargs
            assert kwargs["view_mode"] == "auto"
            assert kwargs["tournament_slug"] == "test"

    def test_real_mode_accepts_explicit_ladder_view(self):
        test_args = [
            "--token",
            "real_token",
            "--slug",
            "tournament/test/event/singles",
            "--view",
            "ladder",
        ]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):
            mock_app_class.return_value.run.return_value = None

            main()

            kwargs = mock_app_class.call_args.kwargs
            assert kwargs["view_mode"] == "ladder"

    def test_demo_mode_falls_back_to_main_view_when_ladder_requested(self):
        test_args = ["--demo", "--view", "ladder"]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):
            mock_app_class.return_value.run.return_value = None

            main()

            kwargs = mock_app_class.call_args.kwargs
            assert kwargs["api_token"] is None
            assert kwargs["view_mode"] == "main"

    def test_short_url_passes_resolved_tournament_slug(self):
        from unittest.mock import AsyncMock

        test_args = [
            "--token",
            "real_token",
            "--short-url",
            "abbey",
            "--event-filter",
            "singles",
        ]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.utils.resolve.resolve_tournament_slug_from_unique_string",
            return_value="melee-abbey-tavern-137",
        ), patch("matchcaller.api.TournamentAPI") as mock_api_class, patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):
            mock_api_class.return_value.get_events_for_tournament = AsyncMock(
                return_value=[
                    {
                        "id": "1",
                        "name": "Melee Singles",
                        "slug": "tournament/melee-abbey-tavern-137/event/melee-singles",
                    },
                    {
                        "id": "2",
                        "name": "Melee Ladder",
                        "slug": "tournament/melee-abbey-tavern-137/event/melee-ladder",
                    },
                ]
            )
            mock_app_class.return_value.run.return_value = None

            main()

            kwargs = mock_app_class.call_args.kwargs
            assert kwargs["event_slug"] == "tournament/melee-abbey-tavern-137/event/melee-singles"
            assert kwargs["tournament_slug"] == "melee-abbey-tavern-137"
            assert kwargs["view_mode"] == "auto"

    def test_simulate_mode_falls_back_to_main_view_when_ladder_requested(self):
        test_args = ["--simulate", "simulator_data/fake.json", "--view", "ladder"]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.simulator.bracket_simulator.BracketSimulator"
        ) as mock_simulator_class, patch(
            "matchcaller.simulator.bracket_simulator.SimulatedTournamentAPI"
        ) as mock_sim_api_class, patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):
            mock_simulator_class.return_value.load_tournament.return_value = True
            mock_app_class.return_value.run.return_value = None

            main()

            kwargs = mock_app_class.call_args.kwargs
            assert kwargs["view_mode"] == "main"
            assert kwargs["tournament_slug"] is None
            assert kwargs["api"] is mock_sim_api_class.return_value
```

Append a dashboard-source injection test to `tests/test_display_injection.py`:

```python
from matchcaller.models.dashboard import DashboardState, ViewMode


class StubDashboardSource:
    def __init__(self, snapshots: list[DashboardState]) -> None:
        self.snapshots = list(snapshots)
        self.calls = 0
        self.previous_states: list[DashboardState | None] = []

    async def fetch_dashboard_state(self, previous_state=None) -> DashboardState:
        self.calls += 1
        self.previous_states.append(previous_state)
        index = min(self.calls - 1, len(self.snapshots) - 1)
        return self.snapshots[index]
```

Then add:

```python
    @pytest.mark.asyncio
    async def test_app_uses_injected_dashboard_source(self):
        dashboard_state = DashboardState(
            tournament_name="Injected Tournament",
            main=_single_match_state(state=2),
            ladder=None,
            stations=None,
            requested_view=ViewMode.AUTO,
            resolved_view=ViewMode.MAIN,
            ladder_was_visible=False,
            last_update="12:00:00",
        )
        source = StubDashboardSource([dashboard_state])
        app = TournamentDisplay(
            view_mode="auto",
            dashboard_source=source,
            poll_interval=999.0,
            refresh_controller_factory=passive_refresh_controller_factory,
        )

        async with app.run_test() as pilot:
            await pilot.pause(0.5)

            assert source.calls == 1
            assert app.dashboard_state is dashboard_state
            assert app.event_name == "Injected Event"
```

- [ ] **Step 2: Run focused tests and verify they fail**

Run:

```bash
pytest tests/test_demo_mode.py::TestDemoMode::test_event_id_real_mode_defaults_auto_without_tournament_slug tests/test_demo_mode.py::TestDemoMode::test_real_mode_defaults_to_auto_view tests/test_demo_mode.py::TestDemoMode::test_real_mode_accepts_explicit_ladder_view tests/test_demo_mode.py::TestDemoMode::test_demo_mode_falls_back_to_main_view_when_ladder_requested tests/test_demo_mode.py::TestDemoMode::test_short_url_passes_resolved_tournament_slug tests/test_demo_mode.py::TestDemoMode::test_simulate_mode_falls_back_to_main_view_when_ladder_requested tests/test_display_injection.py::TestDisplayInjection::test_app_uses_injected_dashboard_source -v
```

Expected: FAIL because `--view`, `view_mode`, and `dashboard_source` are not implemented yet.

- [ ] **Step 3: Add dashboard source protocol**

Modify `matchcaller/ui/dependencies.py`:

```python
from ..models.dashboard import DashboardState
```

Add:

```python
class DashboardDataSource(Protocol):
    """Source of combined main/ladder dashboard snapshots."""

    async def fetch_dashboard_state(
        self,
        previous_state: DashboardState | None = None,
    ) -> DashboardState:
        """Fetch the current dashboard state."""
```

- [ ] **Step 4: Extend `TournamentDisplay` constructor and fetch worker**

Modify `matchcaller/ui/tournament_display.py` imports:

```python
from ..api import TournamentAPI, TournamentDashboardAPI
from ..models.dashboard import DashboardState, ViewMode
from .dependencies import AlertSource, DashboardDataSource, RefreshControllerFactory, TournamentDataSource
```

Extend `TournamentDisplay.__init__` signature with:

```python
        tournament_slug: str | None = None,
        view_mode: str | ViewMode = ViewMode.MAIN,
        dashboard_source: DashboardDataSource | None = None,
```

Inside `__init__`, set:

```python
        self.view_mode = ViewMode(view_mode)
        self.tournament_slug = tournament_slug
        self.dashboard_state: DashboardState | None = None
        self.dashboard_source: DashboardDataSource | None = dashboard_source
        if self.dashboard_source is None and self.view_mode != ViewMode.MAIN and api is None and api_token:
            self.dashboard_source = TournamentDashboardAPI(
                api_token=api_token,
                event_id=event_id,
                event_slug=event_slug,
                tournament_slug=self.tournament_slug,
                requested_view=self.view_mode,
            )
```

In `fetch_tournament_data`, before the existing `self.api.fetch_sets()` path, add:

```python
            if self.dashboard_source is not None:
                dashboard = await self.dashboard_source.fetch_dashboard_state(
                    previous_state=self.dashboard_state,
                )
                self.dashboard_state = dashboard
                if dashboard.main is None:
                    raise Exception("Dashboard state did not include main tournament data")
                snapshot = build_display_snapshot(dashboard.main)
                snapshot = replace(snapshot, last_update=dashboard.last_update)
                self._apply_snapshot(snapshot)
                self.update_table()
                return
```

This keeps rendering as main-only for now; Task 4 will add split/ladder rendering.

- [ ] **Step 5: Add `--view` parsing and pass tournament slug**

Modify `matchcaller/__main__.py`:

Add to `MatchCallerArgs`:

```python
    view: str = "auto"
```

Add parser argument:

```python
    parser.add_argument(
        "--view",
        choices=["auto", "main", "split", "ladder"],
        default="auto",
        help="Display mode: auto, main, split, or ladder",
    )
```

Track `tournament_slug_to_use` near token/event/slug variables. When `--short-url` resolves, keep the resolved tournament slug:

```python
            resolved_tournament_slug = tournament_slug
```

Before the short-url block, initialize:

```python
    resolved_tournament_slug = None
```

In demo and simulate modes, pass `view_mode="main"`. In real mode, pass `view_mode=args.view`. For `--slug`, derive `tournament_slug_to_use` from the slug if `resolved_tournament_slug` is not set:

```python
        from .api.dashboard_api import derive_tournament_slug_from_event_slug
        tournament_slug_to_use = resolved_tournament_slug or derive_tournament_slug_from_event_slug(args.slug)
```

Add to `app_kwargs`:

```python
        "tournament_slug": tournament_slug_to_use,
        "view_mode": view_mode_to_use,
```

For demo/simulation mode, set `tournament_slug_to_use = None` and `view_mode_to_use = "main"`.

- [ ] **Step 6: Update existing demo-mode assertions for new kwargs**

Existing tests in `tests/test_demo_mode.py` assert exact constructor kwargs. Update those expected calls to include:

```python
tournament_slug=None,
view_mode="main",
```

For real slug mode expectations, include:

```python
tournament_slug="test",
view_mode="auto",
```

For real event-id mode expectations, include:

```python
tournament_slug=None,
view_mode="auto",
```

- [ ] **Step 7: Run focused wiring tests**

Run:

```bash
pytest tests/test_demo_mode.py tests/test_display_injection.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit Task 3**

Run:

```bash
git add matchcaller/ui/dependencies.py matchcaller/ui/tournament_display.py matchcaller/__main__.py tests/test_demo_mode.py tests/test_display_injection.py
git commit -m "Wire dashboard view mode"
```

## Task 4: Dashboard Textual Rendering

**Files:**
- Create: `matchcaller/ui/dashboard_grid.py`
- Modify: `matchcaller/ui/tournament_display.py`
- Test: `tests/test_dashboard_grid.py`
- Test: `tests/test_display_injection.py`

- [ ] **Step 1: Write focused rendering tests**

Create `tests/test_dashboard_grid.py`:

```python
"""Unit tests for dashboard grid helpers."""

import pytest

from matchcaller.models.dashboard import (
    LadderDisplayStatus,
    LadderState,
    LadderStanding,
    Station,
    StationState,
)
from matchcaller.models.match import MatchData, MatchRow, PlayerData
from matchcaller.ui.dashboard_grid import (
    build_ladder_rows,
    build_station_summary,
    build_standings_rows,
)


def _row(match_id: int, *, station: int | None = None) -> MatchRow:
    return MatchRow(
        MatchData(
            id=match_id,
            displayName=f"Ladder - Round {match_id}",
            poolName="Ladder",
            player1=PlayerData(tag="Snap"),
            player2=PlayerData(tag="Chetter"),
            state=2,
            startedAt=100,
            updatedAt=100,
            station=station,
        )
    )


@pytest.mark.unit
class TestDashboardGridHelpers:
    def test_build_station_summary(self):
        state = StationState(
            stations=[Station(id="1", number=1), Station(id="2", number=2)],
            occupied_numbers={2},
            available_numbers=[1],
        )

        assert build_station_summary(state) == "Free: 1 | Busy: 2"

    def test_build_station_summary_handles_missing_state(self):
        assert build_station_summary(None) == "Stations unavailable"

    def test_build_ladder_rows_uses_existing_match_row_format(self):
        rows = build_ladder_rows([_row(1, station=3)])

        assert rows[0][0].startswith("Snap vs Chetter")
        assert "Station 3" in rows[0][1]

    def test_build_standings_rows(self):
        ladder = LadderState(
            display_status=LadderDisplayStatus.ACTIVE,
            event_name="Melee Ladder",
            standings=[
                LadderStanding(placement=1, entrant_name="Snap", wins=8, losses=0),
                LadderStanding(placement=2, entrant_name="Chetter", wins=9, losses=1),
            ],
        )

        assert build_standings_rows(ladder) == [
            ["#1", "Snap", "8-0"],
            ["#2", "Chetter", "9-1"],
        ]
```

Append an integration-style injected dashboard test to `tests/test_display_injection.py`:

```python
    @pytest.mark.asyncio
    async def test_split_dashboard_mounts_dashboard_container(self):
        from matchcaller.models.dashboard import (
            DashboardState,
            LadderDisplayStatus,
            LadderState,
            ViewMode,
        )

        dashboard_state = DashboardState(
            tournament_name="Injected Tournament",
            main=_single_match_state(state=2),
            ladder=LadderState(
                display_status=LadderDisplayStatus.ACTIVE,
                event_name="Injected Ladder",
                event_state="ACTIVE",
                sets=[],
                standings=[],
                auto_should_show=True,
            ),
            stations=None,
            requested_view=ViewMode.AUTO,
            resolved_view=ViewMode.SPLIT,
            ladder_was_visible=True,
            last_update="12:00:00",
        )
        source = StubDashboardSource([dashboard_state])
        app = TournamentDisplay(
            view_mode="auto",
            dashboard_source=source,
            poll_interval=999.0,
            refresh_controller_factory=passive_refresh_controller_factory,
        )

        async with app.run_test() as pilot:
            await pilot.pause(0.5)

            assert app.query_one("#dashboard-container")
            assert app.query_one("#main-dashboard-table")
            assert app.query_one("#ladder-dashboard-table")
```

- [ ] **Step 2: Run focused rendering tests and verify they fail**

Run:

```bash
pytest tests/test_dashboard_grid.py tests/test_display_injection.py::TestDisplayInjection::test_split_dashboard_mounts_dashboard_container -v
```

Expected: FAIL because `matchcaller.ui.dashboard_grid` and dashboard rendering are not implemented.

- [ ] **Step 3: Implement dashboard rendering helper module**

Create `matchcaller/ui/dashboard_grid.py`:

```python
"""Textual helpers for split and ladder dashboard rendering."""

from typing import Sequence

from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Static

from ..api.jsonbin_api import AlertData
from ..models.dashboard import (
    DashboardState,
    LadderState,
    StationState,
    ViewMode,
    filter_late_bracket_matches,
)
from ..models.match import MatchRow
from .presentation import build_match_row, sort_pool_matches
```

Add pure row helpers:

```python
def build_station_summary(stations: StationState | None) -> str:
    if stations is None:
        return "Stations unavailable"
    free = ", ".join(str(number) for number in stations.available_numbers) or "-"
    busy = ", ".join(str(number) for number in sorted(stations.occupied_numbers)) or "-"
    return f"Free: {free} | Busy: {busy}"


def build_ladder_rows(matches: Sequence[MatchRow]) -> list[list[str]]:
    return [
        build_match_row(match, late_arrivals=set(), dqs=set())
        for match in sort_pool_matches(matches)
    ]


def build_standings_rows(ladder: LadderState | None) -> list[list[str]]:
    if ladder is None:
        return []
    return [
        [f"#{standing.placement}", standing.entrant_name, standing.record_text]
        for standing in ladder.standings[:10]
    ]
```

Add a `DashboardGridManager` class:

```python
class DashboardGridManager:
    """Own dashboard-specific Textual layout rendering."""

    def reset(self) -> None:
        """Dashboard renderer has no persistent structure cache yet."""
        pass

    async def rebuild(
        self,
        container: Horizontal,
        dashboard: DashboardState,
        alerts: AlertData,
    ) -> None:
        with container.app.batch_update():
            await container.remove_children()
            await container.mount(self._build_dashboard(dashboard, alerts))

    def _build_dashboard(self, dashboard: DashboardState, alerts: AlertData) -> Horizontal | Vertical:
        if dashboard.resolved_view == ViewMode.LADDER:
            return self._build_ladder_only(dashboard)
        return self._build_split(dashboard, alerts)

    def _build_split(self, dashboard: DashboardState, alerts: AlertData) -> Horizontal:
        main_table = self._match_table(
            "main-dashboard-table",
            [
                build_match_row(match, late_arrivals=alerts.late_arrivals, dqs=alerts.dqs)
                for match in filter_late_bracket_matches([MatchRow(set_data) for set_data in (dashboard.main.sets if dashboard.main else [])])
            ],
        )
        ladder_table = self._match_table(
            "ladder-dashboard-table",
            build_ladder_rows([MatchRow(set_data) for set_data in (dashboard.ladder.sets if dashboard.ladder else [])]),
        )
        standings_table = self._standings_table(dashboard.ladder)
        return Horizontal(
            Vertical(
                Static("Main Bracket", classes="pool-title"),
                main_table,
                classes="pool-column",
            ),
            Vertical(
                Static(_ladder_title(dashboard.ladder), classes="pool-title"),
                Static(build_station_summary(dashboard.stations), id="station-summary"),
                ladder_table,
                standings_table,
                classes="pool-column",
            ),
            id="dashboard-container",
        )

    def _build_ladder_only(self, dashboard: DashboardState) -> Vertical:
        ladder_table = self._match_table(
            "ladder-dashboard-table",
            build_ladder_rows([MatchRow(set_data) for set_data in (dashboard.ladder.sets if dashboard.ladder else [])]),
        )
        return Vertical(
            Static(_ladder_title(dashboard.ladder), classes="pool-title"),
            Static(build_station_summary(dashboard.stations), id="station-summary"),
            ladder_table,
            self._standings_table(dashboard.ladder),
            id="dashboard-container",
        )

    def _match_table(self, table_id: str, rows: Sequence[Sequence[str]]) -> DataTable[str]:
        table: DataTable[str] = DataTable(id=table_id, classes="pool-table")
        table.add_column("Match", key="match", width=26)
        table.add_column("Status", key="status", width=16)
        table.add_column("Time", key="duration", width=10)
        table.cursor_type = "none"
        table.cell_padding = 0
        if rows:
            for index, row in enumerate(rows):
                table.add_row(*row, key=str(index))
        else:
            table.add_row("No matches", "-", "-", key="empty")
        return table

    def _standings_table(self, ladder: LadderState | None) -> DataTable[str]:
        table: DataTable[str] = DataTable(id="ladder-standings-table", classes="pool-table")
        table.add_column("Rank", key="rank", width=6)
        table.add_column("Player", key="player", width=18)
        table.add_column("Record", key="record", width=8)
        table.cursor_type = "none"
        table.cell_padding = 0
        rows = build_standings_rows(ladder)
        if rows:
            for index, row in enumerate(rows):
                table.add_row(*row, key=str(index))
        else:
            table.add_row("-", "No standings", "-", key="empty")
        return table


def _ladder_title(ladder: LadderState | None) -> str:
    if ladder is None:
        return "Ladder"
    if ladder.event_name:
        return ladder.event_name
    return ladder.waiting_reason or "Ladder"
```

- [ ] **Step 4: Integrate dashboard rendering into `TournamentDisplay`**

In `matchcaller/ui/tournament_display.py`, import:

```python
from .dashboard_grid import DashboardGridManager
```

Extend `__init__` with:

```python
        dashboard_grid: DashboardGridManager | None = None,
```

Set:

```python
        self.dashboard_grid = dashboard_grid or DashboardGridManager()
```

In `show_loading_state`, reset dashboard state:

```python
        self.dashboard_state = None
```

In `update_table`, add this dashboard branch immediately after `pools_container = self._get_pools_container()` and before the existing `if not self.matches:` block:

```python
        if self.dashboard_state is not None and self.dashboard_state.resolved_view != ViewMode.MAIN:
            self.rebuild_dashboard()
            return
```

Add methods:

```python
    def rebuild_dashboard(self) -> None:
        if self.dashboard_state is None:
            return
        self.refresh_controller.begin_ui_mutation()
        self.run_worker(
            self._rebuild_dashboard_async(self.dashboard_state),
            group="ui",
            exclusive=True,
            exit_on_error=False,
        )

    async def _rebuild_dashboard_async(self, dashboard: DashboardState) -> None:
        try:
            pools_container = self._get_pools_container()
            await self.dashboard_grid.rebuild(pools_container, dashboard, self.alerts)
        except Exception as e:
            log(f"❌ Error during rebuild_dashboard: {e}")
            self.pool_grid.reset()
        finally:
            self.refresh_controller.finish_ui_mutation(flush_update=self.update_table)
```

Update `update_display` so dashboard mode skips pool duration updates until incremental dashboard duration updates are added:

```python
        if self.dashboard_state is not None and self.dashboard_state.resolved_view != ViewMode.MAIN:
            return
```

- [ ] **Step 5: Run focused dashboard UI tests**

Run:

```bash
pytest tests/test_dashboard_grid.py tests/test_display_injection.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

Run:

```bash
git add matchcaller/ui/dashboard_grid.py matchcaller/ui/tournament_display.py tests/test_dashboard_grid.py tests/test_display_injection.py
git commit -m "Add ladder dashboard rendering"
```

## Task 5: End-To-End Verification And Compatibility Cleanup

**Files:**
- Modify only files needed to fix regressions found by the verification commands.
- Test: existing suite and targeted snapshots if available.

- [ ] **Step 1: Run dashboard-related tests together**

Run:

```bash
pytest tests/test_dashboard_models.py tests/test_dashboard_api.py tests/test_dashboard_grid.py tests/test_display_injection.py tests/test_demo_mode.py -v
```

Expected: PASS.

- [ ] **Step 2: Run existing API/UI regression tests likely touched by this work**

Run:

```bash
pytest tests/test_api.py tests/test_api_parsers.py tests/test_api_transport.py tests/test_presentation.py tests/test_pool_grid.py tests/test_refresh_controller.py tests/test_ui.py -v
```

Expected: PASS.

- [ ] **Step 3: Run full test suite**

Run:

```bash
pytest
```

Expected: PASS for all existing and new tests. If snapshot tests fail because dashboard CSS/DOM changes alter existing main-only snapshots, inspect the diff and keep the old pool-grid DOM untouched in `ViewMode.MAIN`; do not update main-only snapshots to accept dashboard markup.

- [ ] **Step 4: Run static checks configured in the repo**

Run:

```bash
python -m py_compile matchcaller/api/dashboard_api.py matchcaller/models/dashboard.py matchcaller/ui/dashboard_grid.py
```

Expected: exit code 0.

Run:

```bash
git diff --check
```

Expected: no output and exit code 0.

- [ ] **Step 5: Run live API smoke probe without printing token**

If `start-gg.token` is present, run:

```bash
python - <<'PY'
import asyncio
from pathlib import Path

from matchcaller.api.dashboard_api import TournamentDashboardAPI
from matchcaller.models.dashboard import ViewMode

async def main():
    token = Path("start-gg.token").read_text().strip()
    api = TournamentDashboardAPI(
        api_token=token,
        event_slug="tournament/melee-abbey-tavern-137/event/melee-singles-7-30-start",
        tournament_slug="melee-abbey-tavern-137",
        requested_view=ViewMode.AUTO,
    )
    dashboard = await api.fetch_dashboard_state()
    print("view", dashboard.resolved_view)
    print("main", dashboard.main.event_name if dashboard.main else None)
    print("ladder_status", dashboard.ladder.display_status if dashboard.ladder else None)
    print("stations", len(dashboard.stations.stations) if dashboard.stations else None)

asyncio.run(main())
PY
```

Expected: output includes a view name, main event name, ladder status, and station count. The token value must not be printed.

- [ ] **Step 6: Commit verification fixes**

If Step 1 through Step 5 required any fixes, commit them:

```bash
git add <changed-files>
git commit -m "Finish ladder dashboard integration"
```

If no files changed during verification, do not create an empty commit.
