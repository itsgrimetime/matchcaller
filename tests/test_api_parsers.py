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

    def test_parse_event_sets_response_joins_doubles_team_participants(
        self,
        event_sets_raw: dict,
    ):
        event_sets_raw["data"]["event"]["sets"]["nodes"][0]["slots"][0]["entrant"][
            "participants"
        ].append({"gamerTag": "Player1Partner"})
        event_sets_raw["data"]["event"]["sets"]["nodes"][0]["slots"][1]["entrant"][
            "participants"
        ].append({"gamerTag": "Player2Partner"})

        result = parse_event_sets_response(validate_startgg_response(event_sets_raw))

        assert result.sets[0].player1.tag == "Player1 / Player1Partner"
        assert result.sets[0].player1.team_tags == ["Player1", "Player1Partner"]
        assert result.sets[0].player2.tag == "Player2 / Player2Partner"

    def test_parse_event_sets_response_handles_missing_phase_group(self, event_sets_raw: dict):
        event_sets_raw["data"]["event"]["sets"]["nodes"][0]["phaseGroup"] = None

        result = parse_event_sets_response(validate_startgg_response(event_sets_raw))

        assert result.sets[0].displayName == "Unknown Bracket - Winners Round 1"
        assert result.sets[0].poolName == "Unknown Pool"

    @pytest.mark.parametrize("has_round_robin", [True, False])
    def test_elimination_label_depends_on_event_phases(self, event_sets_raw, has_round_robin):
        event = event_sets_raw["data"]["event"]
        event["phases"] = [{"bracketType": "DOUBLE_ELIMINATION"}]
        if has_round_robin:
            event["phases"].insert(0, {"bracketType": "ROUND_ROBIN"})
        event["sets"]["nodes"][0]["phaseGroup"] = {
            "displayIdentifier": "1",
            "bracketType": "DOUBLE_ELIMINATION",
            "phase": {"name": "Elimination Bracket"},
        }

        result = parse_event_sets_response(validate_startgg_response(event_sets_raw))

        assert result.sets[0].poolName == "Elimination Bracket - Pool 1"
        assert not result.finals_pending
        expected_label = "Double Elim - Bracket 1" if has_round_robin else None
        assert result.sets[0].pool_label == expected_label

    def test_unseeded_finals_keep_stage_handoff_visible(self, event_sets_raw):
        event = event_sets_raw["data"]["event"]
        event["phases"] = [
            {"bracketType": "ROUND_ROBIN"}, {"bracketType": "DOUBLE_ELIMINATION"},
        ]
        node = event["sets"]["nodes"][0]
        node["phaseGroup"]["bracketType"] = "DOUBLE_ELIMINATION"
        node["slots"] = [{"entrant": None}, {"entrant": None}]

        result = parse_event_sets_response(validate_startgg_response(event_sets_raw))

        assert not result.sets
        assert result.finals_pending

    def test_round_robin_retains_round_number_and_names_generic_pool(self, event_sets_raw):
        node = event_sets_raw["data"]["event"]["sets"]["nodes"][0]
        node["round"] = 4
        node["phaseGroup"] = {
            "displayIdentifier": "2",
            "bracketType": "ROUND_ROBIN",
            "phase": {"name": "Bracket"},
        }

        result = parse_event_sets_response(validate_startgg_response(event_sets_raw))

        assert result.sets[0].pool_label == "Round Robin - Pool 2"
        assert result.sets[0].bracket_type == "ROUND_ROBIN"
        assert result.sets[0].round_number == 4

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
