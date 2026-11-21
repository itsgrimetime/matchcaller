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


def _amateur_event() -> dict:
    return {
        "id": "3",
        "name": "Melee Amateur Singles",
        "slug": "tournament/weekly/event/amateur-singles",
    }


@pytest.mark.unit
class TestMultiEventTournamentAPI:
    @pytest.mark.asyncio
    async def test_fetch_sets_includes_both_brackets_at_a_doubles_only_tournament(self):
        tournament_slug = "weekend-doubles"
        events = [
            {
                "id": str(event_id),
                "name": f"Melee Doubles ({session})",
                "slug": f"tournament/{tournament_slug}/event/melee-doubles-{session}",
            }
            for event_id, session in enumerate(("early", "late"), start=1)
        ]
        transport = FakeTransport(
            [
                _result(_events_payload(events)),
                _result(_event_sets_payload(events[0]["name"], [_set_node(10, prefix="E")])),
                _result(_event_sets_payload(events[1]["name"], [_set_node(20, prefix="L")])),
            ]
        )
        api = MultiEventTournamentAPI(
            api_token="token", tournament_slug=tournament_slug, transport=transport
        )

        result = await api.fetch_sets()

        assert [match.id for match in result.sets] == [10, 20]
        assert [match.poolName for match in result.sets] == [
            "Melee Doubles (early) - Pools - Pool A",
            "Melee Doubles (late) - Pools - Pool A",
        ]

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

    @pytest.mark.asyncio
    async def test_fetch_sets_keeps_amateur_pools_separate_from_main_events(self):
        transport = FakeTransport(
            [
                # Amateur appears before main singles in the API's event order.
                _result(_events_payload([_amateur_event()] + _main_events())),
                _result(_event_sets_payload("Melee Doubles", [_set_node(20, prefix="D")])),
                _result(_event_sets_payload("Melee Singles", [_set_node(10, prefix="S")])),
                _result(_event_sets_payload("Melee Amateur Singles", [_set_node(30, prefix="A")])),
            ]
        )
        api = MultiEventTournamentAPI(
            api_token="token", tournament_slug="weekly", transport=transport
        )

        result = await api.fetch_sets()

        assert result.event_name == "Melee Doubles + Melee Singles + Melee Amateur Singles"
        assert [match.id for match in result.sets] == [20, 10, 30]
        assert [match.poolName for match in result.sets] == [
            "Melee Doubles - Pools - Pool A",
            "Melee Singles - Pools - Pool A",
            "Melee Amateur Singles - Pools - Pool A",
        ]
        assert [call["payload"]["variables"]["eventId"] for call in transport.post_calls[1:]] == [
            "2", "1", "3"
        ]

    @pytest.mark.asyncio
    async def test_refresh_discovers_new_amateur_event_and_drops_it_when_empty(self):
        transport = FakeTransport(
            [
                _result(_events_payload(_main_events())),
                _result(_event_sets_payload("Melee Doubles", [])),
                _result(_event_sets_payload("Melee Singles", [_set_node(10, prefix="S")])),
                _result(_events_payload(_main_events() + [_amateur_event()])),
                _result(_event_sets_payload("Melee Doubles", [])),
                _result(_event_sets_payload("Melee Singles", [])),
                _result(_event_sets_payload("Melee Amateur Singles", [_set_node(30, prefix="A")])),
                _result(_events_payload(_main_events() + [_amateur_event()])),
                _result(_event_sets_payload("Melee Doubles", [])),
                _result(_event_sets_payload("Melee Singles", [])),
                _result(_event_sets_payload("Melee Amateur Singles", [])),
            ]
        )
        api = MultiEventTournamentAPI(
            api_token="token", tournament_slug="weekly", transport=transport
        )

        initial = await api.fetch_sets()
        assert initial.event_name == "Melee Singles"
        assert [match.id for match in initial.sets] == [10]

        amateur = await api.fetch_sets()
        assert amateur.event_name == "Melee Amateur Singles"
        assert [match.id for match in amateur.sets] == [30]

        finished = await api.fetch_sets()
        assert finished.sets == []
        assert finished.event_name == "No active singles/doubles/amateur matches"

    @pytest.mark.parametrize(
        "name, event_slug",
        [
            ("Melee Amateur Singles", "side-bracket"),
            ("AMMY", "side-bracket"),
            ("Redemption Bracket - Melee Singles", "side-bracket"),
            ("Side Bracket", "amateur"),
            ("Side Bracket", "ammy"),
            ("Side Bracket", "redemption"),
        ],
    )
    def test_select_main_events_includes_amateur_aliases(self, name, event_slug):
        amateur = {
            "id": "3", "name": name, "slug": f"tournament/weekly/event/{event_slug}"
        }

        selected = select_main_events([amateur] + _main_events())

        assert [event["id"] for event in selected] == ["2", "1", "3"]

    def test_select_main_events_includes_multiple_amateur_brackets(self):
        amateur = _amateur_event()
        redemption = {
            "id": "4", "name": "Redemption", "slug": "tournament/weekly/event/redemption"
        }

        selected = select_main_events([amateur, redemption] + _main_events())

        assert [event["id"] for event in selected] == ["2", "1", "3", "4"]

    def test_select_main_events_uses_main_fallback_alongside_amateur(self):
        main = {
            "id": "1", "name": "Main Bracket", "slug": "tournament/weekly/event/main"
        }

        selected = select_main_events([_amateur_event(), main])

        assert [event["id"] for event in selected] == ["1", "3"]

    def test_tournament_name_does_not_classify_every_event_as_amateur(self):
        events = [
            {
                "id": str(index),
                "name": "Melee Singles",
                "slug": f"tournament/amateur-weekly/event/singles-{index}",
            }
            for index in (1, 2)
        ]

        assert select_main_events(events) == [events[0]]

    @pytest.mark.parametrize("keyword", ["waitlist", "ladder", "staging"])
    def test_amateur_waitlist_ladder_and_staging_events_are_excluded(self, keyword):
        ignored = {
            "id": "4",
            "name": f"Amateur {keyword.title()}",
            "slug": f"tournament/weekly/event/ammy-{keyword}",
        }

        assert select_main_events([ignored]) == []
        assert select_main_events([ignored] + _main_events()) == [
            _main_events()[1], _main_events()[0]
        ]

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
