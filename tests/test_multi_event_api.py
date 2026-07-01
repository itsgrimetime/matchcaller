"""Tests for combining active sets across tournament events."""

import pytest

from matchcaller.api.multi_event_api import (
    MultiEventTournamentAPI,
    select_main_events,
)
from matchcaller.api.transport import HTTPResult


class FakeTransport:
    """Queue-backed transport stub for multi-event API tests."""

    def __init__(self, post_results: list[HTTPResult]) -> None:
        self.post_results = list(post_results)
        self.post_calls: list[dict] = []

    async def post_json(
        self,
        url: str,
        *,
        payload: dict,
        headers: dict,
        timeout_seconds: float,
    ) -> HTTPResult:
        self.post_calls.append(
            {
                "url": url,
                "payload": payload,
                "headers": headers,
                "timeout_seconds": timeout_seconds,
            }
        )
        return self.post_results.pop(0)

    async def get_json(
        self,
        url: str,
        *,
        headers: dict,
        timeout_seconds: float,
    ) -> HTTPResult:
        raise AssertionError("MultiEventTournamentAPI should not use GET")


def _result(json_data: dict) -> HTTPResult:
    return HTTPResult(status=200, text="", json_data=json_data)


def _events_payload(events: list[dict]) -> dict:
    return {
        "data": {
            "tournament": {
                "name": "Weekly",
                "events": events,
            }
        }
    }


def _set_node(set_id: int, *, prefix: str) -> dict:
    return {
        "id": set_id,
        "fullRoundText": "Round 1",
        "identifier": None,
        "state": 2,
        "updatedAt": 300 + set_id,
        "startedAt": None,
        "round": 1,
        "station": None,
        "stream": None,
        "phaseGroup": {
            "displayIdentifier": "A",
            "phase": {"name": "Pools"},
        },
        "slots": [
            {
                "entrant": {
                    "participants": [
                        {"gamerTag": f"{prefix} A1"},
                        {"gamerTag": f"{prefix} A2"},
                    ]
                }
            },
            {
                "entrant": {
                    "participants": [
                        {"gamerTag": f"{prefix} B1"},
                        {"gamerTag": f"{prefix} B2"},
                    ]
                }
            },
        ],
    }


def _event_sets_payload(event_name: str, nodes: list[dict]) -> dict:
    return {
        "data": {
            "event": {
                "name": event_name,
                "tournament": {"name": "Weekly"},
                "sets": {
                    "pageInfo": {"totalPages": 1},
                    "nodes": nodes,
                },
            }
        }
    }


def _main_events() -> list[dict]:
    return [
        {
            "id": "1",
            "name": "Melee Singles",
            "slug": "tournament/weekly/event/melee-singles",
        },
        {
            "id": "2",
            "name": "Melee Doubles",
            "slug": "tournament/weekly/event/melee-doubles",
        },
    ]


@pytest.mark.unit
class TestMultiEventTournamentAPI:
    @pytest.mark.asyncio
    async def test_fetch_sets_shows_doubles_when_only_doubles_has_active_sets(self):
        transport = FakeTransport(
            [
                _result(_events_payload(_main_events())),
                _result(_event_sets_payload("Melee Doubles", [_set_node(20, prefix="D")])),
                _result(_event_sets_payload("Melee Singles", [])),
            ]
        )
        api = MultiEventTournamentAPI(
            api_token="token",
            tournament_slug="weekly",
            transport=transport,
        )

        result = await api.fetch_sets()

        assert result.event_name == "Melee Doubles"
        assert result.tournament_name == "Weekly"
        assert len(result.sets) == 1
        assert result.sets[0].poolName == "Melee Doubles - Pools - Pool A"
        assert result.sets[0].player1.tag == "D A1 / D A2"

    @pytest.mark.asyncio
    async def test_fetch_sets_combines_doubles_and_singles_when_both_active(self):
        transport = FakeTransport(
            [
                _result(_events_payload(_main_events())),
                _result(_event_sets_payload("Melee Doubles", [_set_node(20, prefix="D")])),
                _result(_event_sets_payload("Melee Singles", [_set_node(10, prefix="S")])),
            ]
        )
        api = MultiEventTournamentAPI(
            api_token="token",
            tournament_slug="weekly",
            transport=transport,
        )

        result = await api.fetch_sets()

        assert result.event_name == "Melee Doubles + Melee Singles"
        assert [set_data.poolName for set_data in result.sets] == [
            "Melee Doubles - Pools - Pool A",
            "Melee Singles - Pools - Pool A",
        ]
        assert [set_data.player1.tag for set_data in result.sets] == [
            "D A1 / D A2",
            "S A1 / S A2",
        ]

    @pytest.mark.asyncio
    async def test_fetch_sets_drops_doubles_when_only_singles_has_active_sets(self):
        transport = FakeTransport(
            [
                _result(_events_payload(_main_events())),
                _result(_event_sets_payload("Melee Doubles", [])),
                _result(_event_sets_payload("Melee Singles", [_set_node(10, prefix="S")])),
            ]
        )
        api = MultiEventTournamentAPI(
            api_token="token",
            tournament_slug="weekly",
            transport=transport,
        )

        result = await api.fetch_sets()

        assert result.event_name == "Melee Singles"
        assert len(result.sets) == 1
        assert result.sets[0].poolName == "Melee Singles - Pools - Pool A"

    def test_select_main_events_ignores_waitlists_and_ladder_events(self):
        selected = select_main_events(
            [
                {
                    "id": "1",
                    "name": "Melee Doubles Waitlist",
                    "slug": "tournament/weekly/event/doubles-waitlist",
                },
                {
                    "id": "2",
                    "name": "Melee Ladder",
                    "slug": "tournament/weekly/event/ladder",
                },
                {
                    "id": "3",
                    "name": "Melee Singles",
                    "slug": "tournament/weekly/event/melee-singles",
                },
            ]
        )

        assert [event["name"] for event in selected] == ["Melee Singles"]
