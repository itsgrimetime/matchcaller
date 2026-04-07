"""Unit tests for start.gg parser helpers."""

import pytest

from matchcaller.api.parsers import (
    extract_event_id,
    parse_event_sets_response,
    parse_tournament_events_payload,
    validate_startgg_response,
)
from matchcaller.models.startgg_api import StartGGAPIResponse


@pytest.fixture
def base_set_node() -> dict:
    """Return a reusable set node payload."""
    return {
        "id": 1,
        "fullRoundText": "Winners Round 1",
        "identifier": "W1",
        "state": 2,
        "updatedAt": 1640995200,
        "startedAt": None,
        "round": 1,
        "slots": [
            {
                "entrant": {
                    "participants": [
                        {
                            "gamerTag": "Player1",
                            "user": {
                                "authorizations": [
                                    {
                                        "externalUsername": "player1",
                                        "externalId": "discord-1",
                                    }
                                ]
                            },
                        }
                    ]
                }
            },
            {
                "entrant": {
                    "participants": [
                        {
                            "gamerTag": "Player2",
                            "user": {
                                "authorizations": [
                                    {
                                        "externalUsername": "player2",
                                        "externalId": "discord-2",
                                    }
                                ]
                            },
                        }
                    ]
                }
            },
        ],
        "phaseGroup": {
            "displayIdentifier": "A1",
            "phase": {"name": "Winner's Bracket"},
        },
        "station": {"number": 5},
        "stream": {"streamName": "Main Stream"},
    }


@pytest.fixture
def event_sets_raw(base_set_node: dict) -> dict:
    """Return a validated-looking event-sets payload."""
    return {
        "data": {
            "event": {
                "name": "Test Event",
                "tournament": {"name": "Test Tournament"},
                "sets": {"nodes": [base_set_node]},
            }
        }
    }


@pytest.fixture
def validated_event_sets_response(event_sets_raw: dict) -> StartGGAPIResponse:
    """Return a validated event-sets response model."""
    return validate_startgg_response(event_sets_raw)


@pytest.mark.unit
class TestAPIParsers:
    """Test pure parser helpers with reusable fixtures."""

    def test_parse_event_sets_response_valid_data(
        self,
        validated_event_sets_response: StartGGAPIResponse,
    ):
        result = parse_event_sets_response(validated_event_sets_response)

        assert result.event_name == "Test Event"
        assert result.tournament_name == "Test Tournament"
        assert len(result.sets) == 1

        parsed_set = result.sets[0]
        assert parsed_set.displayName == "Winner's Bracket - Winners Round 1"
        assert parsed_set.poolName == "Winner's Bracket - A1"
        assert parsed_set.player1.discord_id == "discord-1"
        assert parsed_set.player2.discord_id == "discord-2"
        assert parsed_set.station == 5
        assert parsed_set.stream == "Main Stream"

    def test_parse_event_sets_response_skips_tbd_vs_tbd(self, event_sets_raw: dict):
        event_sets_raw["data"]["event"]["sets"]["nodes"][0]["slots"] = [
            {"entrant": None},
            {"entrant": None},
        ]

        result = parse_event_sets_response(validate_startgg_response(event_sets_raw))

        assert result.sets == []

    def test_parse_event_sets_response_handles_unknown_state(self, event_sets_raw: dict):
        event_sets_raw["data"]["event"]["sets"]["nodes"][0]["state"] = 99

        result = parse_event_sets_response(validate_startgg_response(event_sets_raw))

        assert result.sets[0].state == 99

    def test_parse_event_sets_response_handles_missing_phase_group(self, event_sets_raw: dict):
        event_sets_raw["data"]["event"]["sets"]["nodes"][0]["phaseGroup"] = None

        result = parse_event_sets_response(validate_startgg_response(event_sets_raw))

        assert result.sets[0].displayName == "Unknown Bracket - Winners Round 1"
        assert result.sets[0].poolName == "Unknown Pool"

    def test_parse_tournament_events_payload(self):
        raw_data = {
            "data": {
                "tournament": {
                    "name": "Weekly",
                    "events": [
                        {"id": 1, "name": "Singles", "slug": "weekly/event/singles"},
                        {"id": 2, "name": "Doubles", "slug": "weekly/event/doubles"},
                    ],
                }
            }
        }

        assert parse_tournament_events_payload(raw_data) == [
            {"id": "1", "name": "Singles", "slug": "weekly/event/singles"},
            {"id": "2", "name": "Doubles", "slug": "weekly/event/doubles"},
        ]

    def test_parse_tournament_events_payload_errors(self):
        assert parse_tournament_events_payload({"errors": [{"message": "boom"}]}) == []

    def test_extract_event_id(self):
        api_response = validate_startgg_response(
            {"data": {"event": {"id": 12345, "name": "Singles"}}}
        )

        assert extract_event_id(api_response) == "12345"

    def test_extract_event_id_missing_event(self):
        api_response = validate_startgg_response({"data": {"event": None}})

        assert extract_event_id(api_response) is None
