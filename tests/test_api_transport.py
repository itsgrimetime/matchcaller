"""Focused tests for transport-injected API clients."""

from unittest.mock import patch

import pytest

from matchcaller.api.jsonbin_api import AlertData, JsonBinAPI
from matchcaller.api.tournament_api import TournamentAPI
from matchcaller.api.transport import HTTPResult


def _set_node(set_id: int) -> dict:
    return {
        "id": set_id,
        "fullRoundText": "Round 1",
        "identifier": None,
        "state": 2,
        "updatedAt": 300,
        "startedAt": None,
        "round": 1,
        "station": None,
        "stream": None,
        "phaseGroup": {
            "displayIdentifier": "1",
            "phase": {"name": "Pools"},
        },
        "slots": [
            {"entrant": {"participants": [{"gamerTag": f"Player {set_id}A"}]}},
            {"entrant": {"participants": [{"gamerTag": f"Player {set_id}B"}]}},
        ],
    }


def _event_sets_payload(nodes: list[dict]) -> dict:
    return {
        "data": {
            "event": {
                "name": "Test Event",
                "tournament": {"name": "Test Tournament"},
                "sets": {
                    "pageInfo": {"totalPages": 2},
                    "nodes": nodes,
                },
            }
        }
    }


class FakeTransport:
    """Queue-backed transport stub for API client tests."""

    def __init__(
        self,
        *,
        post_results: list[HTTPResult] | None = None,
        get_results: list[HTTPResult] | None = None,
    ) -> None:
        self.post_results = list(post_results or [])
        self.get_results = list(get_results or [])
        self.post_calls: list[dict] = []
        self.get_calls: list[dict] = []

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
        self.get_calls.append(
            {
                "url": url,
                "headers": headers,
                "timeout_seconds": timeout_seconds,
            }
        )
        return self.get_results.pop(0)


@pytest.mark.unit
class TestTransportInjection:
    """Test direct transport injection without network patching."""

    @pytest.mark.asyncio
    async def test_fetch_sets_uses_injected_transport(self):
        transport = FakeTransport(
            post_results=[
                HTTPResult(
                    status=200,
                    text='{"data":{"event":{"name":"Test Event","tournament":{"name":"Test Tournament"},"sets":{"nodes":[]}}}}',
                    json_data={
                        "data": {
                            "event": {
                                "name": "Test Event",
                                "tournament": {"name": "Test Tournament"},
                                "sets": {"nodes": []},
                            }
                        }
                    },
                )
            ]
        )
        api = TournamentAPI(
            api_token="test_token",
            event_id="12345",
            transport=transport,
        )

        result = await api.fetch_sets()

        assert result.event_name == "Test Event"
        assert transport.post_calls[0]["headers"]["Authorization"] == "Bearer test_token"
        assert transport.post_calls[0]["timeout_seconds"] == 10

    @pytest.mark.asyncio
    async def test_fetch_sets_paginates_under_startgg_complexity_limit(self):
        transport = FakeTransport(
            post_results=[
                HTTPResult(
                    status=200,
                    text="",
                    json_data=_event_sets_payload([_set_node(index) for index in range(80)]),
                ),
                HTTPResult(
                    status=200,
                    text="",
                    json_data=_event_sets_payload([_set_node(80)]),
                ),
            ]
        )
        api = TournamentAPI(
            api_token="test_token",
            event_id="12345",
            transport=transport,
        )

        result = await api.fetch_sets()

        assert len(result.sets) == 81
        assert [call["payload"]["variables"]["page"] for call in transport.post_calls] == [
            1,
            2,
        ]
        assert all(
            call["payload"]["variables"]["perPage"] == 80
            for call in transport.post_calls
        )

    @pytest.mark.asyncio
    async def test_fetch_sets_log_does_not_include_token_suffix(self):
        transport = FakeTransport(
            post_results=[
                HTTPResult(
                    status=200,
                    text='{"data":{"event":{"name":"Test Event","tournament":{"name":"Test Tournament"},"sets":{"nodes":[]}}}}',
                    json_data={
                        "data": {
                            "event": {
                                "name": "Test Event",
                                "tournament": {"name": "Test Tournament"},
                                "sets": {"nodes": []},
                            }
                        }
                    },
                )
            ]
        )
        raw_token = "dummy_token_with_unique_SUFFIX"
        suffix = "FFIX"
        api = TournamentAPI(
            api_token=raw_token,
            event_id="12345",
            transport=transport,
        )

        with patch("matchcaller.api.tournament_api.log") as mock_log:
            await api.fetch_sets()

        assert transport.post_calls[0]["headers"]["Authorization"] == (
            f"Bearer {raw_token}"
        )
        log_calls = [str(call) for call in mock_log.call_args_list]
        assert all(raw_token not in call for call in log_calls)
        assert all(suffix not in call for call in log_calls)

    @pytest.mark.asyncio
    async def test_get_event_id_from_slug_uses_injected_transport(self):
        transport = FakeTransport(
            post_results=[
                HTTPResult(
                    status=200,
                    text='{"data":{"event":{"id":"67890","name":"Singles"}}}',
                    json_data={"data": {"event": {"id": "67890", "name": "Singles"}}},
                )
            ]
        )
        api = TournamentAPI(api_token="test_token", transport=transport)

        result = await api.get_event_id_from_slug("tournament/test/event/singles")

        assert result == "67890"
        assert transport.post_calls[0]["payload"]["variables"]["slug"] == (
            "tournament/test/event/singles"
        )

    @pytest.mark.asyncio
    async def test_get_events_for_tournament_uses_injected_transport(self):
        transport = FakeTransport(
            post_results=[
                HTTPResult(
                    status=200,
                    text='{"data":{"tournament":{"name":"Weekly","events":[{"id":1,"name":"Singles","slug":"weekly/event/singles"}]}}}',
                    json_data={
                        "data": {
                            "tournament": {
                                "name": "Weekly",
                                "events": [
                                    {
                                        "id": 1,
                                        "name": "Singles",
                                        "slug": "weekly/event/singles",
                                    }
                                ],
                            }
                        }
                    },
                )
            ]
        )
        api = TournamentAPI(api_token="test_token", transport=transport)

        result = await api.get_events_for_tournament("weekly")

        assert result == [
            {"id": "1", "name": "Singles", "slug": "weekly/event/singles"}
        ]

    @pytest.mark.asyncio
    async def test_find_nearest_abbey_tournament_slug_uses_search_results(self):
        now = 1_776_000_000
        transport = FakeTransport(
            post_results=[
                HTTPResult(
                    status=200,
                    text='{"data":{"tournaments":{"nodes":[]}}}',
                    json_data={
                        "data": {
                            "tournaments": {
                                "nodes": [
                                    {
                                        "id": 1,
                                        "name": "Not Abbey",
                                        "slug": "tournament/not-abbey",
                                        "startAt": now + 1,
                                    },
                                    {
                                        "id": 2,
                                        "name": "Melee @ Abbey Tavern #136",
                                        "slug": "tournament/melee-abbey-tavern-136",
                                        "startAt": now - 100,
                                    },
                                    {
                                        "id": 3,
                                        "name": "Melee @ Abbey Tavern #137",
                                        "slug": "tournament/melee-abbey-tavern-137",
                                        "startAt": now + 50,
                                    },
                                    {
                                        "id": 4,
                                        "name": "Melee @ Abbey Tavern #138",
                                        "slug": "tournament/melee-abbey-tavern-138",
                                        "startAt": now + 150,
                                    },
                                ]
                            }
                        }
                    },
                )
            ]
        )
        api = TournamentAPI(api_token="test_token", transport=transport)

        result = await api.find_nearest_abbey_tournament_slug(now=now)

        assert result == "melee-abbey-tavern-137"
        variables = transport.post_calls[0]["payload"]["variables"]
        assert variables["name"] == "abbey"
        assert variables["after"] == now - 30 * 24 * 60 * 60
        assert variables["before"] == now + 30 * 24 * 60 * 60

    @pytest.mark.asyncio
    async def test_jsonbin_api_uses_injected_transport(self):
        transport = FakeTransport(
            get_results=[
                HTTPResult(
                    status=200,
                    text='{"record":{"lateArrivals":["123"],"dqs":["456"]}}',
                    json_data={
                        "record": {
                            "lateArrivals": ["123"],
                            "dqs": ["456"],
                        }
                    },
                )
            ]
        )
        api = JsonBinAPI("bin-123", api_key="secret", transport=transport)

        result = await api.fetch_alerts()

        assert isinstance(result, AlertData)
        assert result.late_arrivals == {"123"}
        assert result.dqs == {"456"}
        assert transport.get_calls[0]["headers"]["X-Master-Key"] == "secret"
