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
