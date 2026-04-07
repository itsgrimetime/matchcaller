"""Focused tests for transport-injected API clients."""

import pytest

from matchcaller.api.jsonbin_api import AlertData, JsonBinAPI
from matchcaller.api.tournament_api import TournamentAPI
from matchcaller.api.transport import HTTPResult


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
