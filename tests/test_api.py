"""Unit tests for TournamentAPI class"""

import pytest
from aioresponses import aioresponses

from matchcaller.matchcaller import MOCK_TOURNAMENT_DATA, TournamentAPI
from matchcaller.models.match import TournamentState


@pytest.mark.unit
class TestTournamentAPI:
    """Test TournamentAPI functionality"""

    def test_init_with_token_and_event_id(self):
        """Test API initialization with token and event ID"""
        api = TournamentAPI(api_token="test_token", event_id="12345")

        assert api.api_token == "test_token"
        assert api.event_id == "12345"
        assert api.event_slug is None
        assert api.base_url == "https://api.start.gg/gql/alpha"

    def test_init_with_slug(self):
        """Test API initialization with event slug"""
        api = TournamentAPI(
            api_token="test_token", event_slug="tournament/test/event/singles"
        )

        assert api.api_token == "test_token"
        assert api.event_id is None
        assert api.event_slug == "tournament/test/event/singles"

    @pytest.mark.asyncio
    async def test_fetch_sets_no_token_returns_mock_data(self):
        """Test that missing API token returns mock data"""
        api = TournamentAPI()

        result = await api.fetch_sets()

        assert result == MOCK_TOURNAMENT_DATA

    @pytest.mark.asyncio
    async def test_fetch_sets_no_event_id_returns_mock_data(self):
        """Test that missing event ID returns mock data"""
        api = TournamentAPI(api_token="test_token")

        result = await api.fetch_sets()

        assert result == MOCK_TOURNAMENT_DATA

    @pytest.mark.asyncio
    async def test_get_event_id_from_slug_success(self):
        """Test successful event ID retrieval from slug"""
        api = TournamentAPI(api_token="test_token")

        mock_response = {"data": {"event": {"id": "67890", "name": "Test Event"}}}

        with aioresponses() as m:
            m.post("https://api.start.gg/gql/alpha", payload=mock_response, status=200)

            result = await api.get_event_id_from_slug("tournament/test/event/singles")

            assert result == "67890"

    @pytest.mark.asyncio
    async def test_get_event_id_from_slug_not_found(self):
        """Test event ID retrieval when event not found"""
        api = TournamentAPI(api_token="test_token")

        mock_response = {"data": {"event": None}}

        with aioresponses() as m:
            m.post("https://api.start.gg/gql/alpha", payload=mock_response, status=200)

            result = await api.get_event_id_from_slug(
                "tournament/nonexistent/event/singles"
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_get_event_id_from_slug_graphql_error(self):
        """Test event ID retrieval with GraphQL errors"""
        api = TournamentAPI(api_token="test_token")

        mock_response = {"errors": [{"message": "Event not found"}]}

        with aioresponses() as m:
            m.post("https://api.start.gg/gql/alpha", payload=mock_response, status=200)

            result = await api.get_event_id_from_slug("tournament/error/event/singles")

            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_sets_successful_api_call(self):
        """Test successful API call for tournament sets"""
        api = TournamentAPI(api_token="test_token", event_id="12345")

        mock_response = {
            "data": {
                "event": {
                    "name": "Test Tournament",
                    "sets": {
                        "nodes": [
                            {
                                "id": 1,
                                "fullRoundText": "Winners Round 1",
                                "identifier": "W1",
                                "state": 2,
                                "updatedAt": 1640995200,
                                "startedAt": None,
                                "completedAt": None,
                                "slots": [
                                    {
                                        "id": 1,
                                        "entrant": {
                                            "id": 1,
                                            "name": "Player 1",
                                            "participants": [
                                                {"id": 1, "gamerTag": "Player1"}
                                            ],
                                        },
                                    },
                                    {
                                        "id": 2,
                                        "entrant": {
                                            "id": 2,
                                            "name": "Player 2",
                                            "participants": [
                                                {"id": 2, "gamerTag": "Player2"}
                                            ],
                                        },
                                    },
                                ],
                                "phaseGroup": {
                                    "id": 1,
                                    "displayIdentifier": "A1",
                                    "phase": {"id": 1, "name": "Winner's Bracket"},
                                },
                                "stream": None,
                                "station": None,
                            }
                        ]
                    },
                }
            }
        }

        with aioresponses() as m:
            m.post("https://api.start.gg/gql/alpha", payload=mock_response, status=200)

            result = await api.fetch_sets()

            assert result["event_name"] == "Test Tournament"
            assert len(result["sets"]) == 1
            assert result["sets"][0]["player1"]["tag"] == "Player1"
            assert result["sets"][0]["player2"]["tag"] == "Player2"
            assert result["sets"][0]["state"] == 2

    @pytest.mark.asyncio
    async def test_fetch_sets_with_slug_resolves_event_id(self):
        """Test that slug gets resolved to event ID before fetching sets"""
        api = TournamentAPI(
            api_token="test_token", event_slug="tournament/test/event/singles"
        )

        # Mock the event ID resolution
        event_id_response = {"data": {"event": {"id": "12345", "name": "Test Event"}}}

        # Mock the sets response
        sets_response = {
            "data": {"event": {"name": "Test Tournament", "sets": {"nodes": []}}}
        }

        with aioresponses() as m:
            # First call for event ID resolution
            m.post(
                "https://api.start.gg/gql/alpha", payload=event_id_response, status=200
            )
            # Second call for sets data
            m.post("https://api.start.gg/gql/alpha", payload=sets_response, status=200)

            result = await api.fetch_sets()

            assert api.event_id == "12345"
            assert result["event_name"] == "Test Tournament"

    @pytest.mark.asyncio
    async def test_fetch_sets_http_error_returns_mock_data(self):
        """Test that HTTP errors fall back to mock data"""
        api = TournamentAPI(api_token="test_token", event_id="12345")

        with aioresponses() as m:
            m.post(
                "https://api.start.gg/gql/alpha",
                status=500,
                payload="Internal Server Error",
            )

            result = await api.fetch_sets()

            assert result == MOCK_TOURNAMENT_DATA

    @pytest.mark.asyncio
    async def test_fetch_sets_graphql_error_returns_mock_data(self):
        """Test that GraphQL errors fall back to mock data"""
        api = TournamentAPI(api_token="test_token", event_id="12345")

        mock_response = {"errors": [{"message": "Invalid event ID"}]}

        with aioresponses() as m:
            m.post("https://api.start.gg/gql/alpha", payload=mock_response, status=200)

            result = await api.fetch_sets()

            assert result == MOCK_TOURNAMENT_DATA

    def test_parse_api_response_valid_data(self) -> None:
        """Test parsing valid API response"""
        api = TournamentAPI()

        mock_data = {
            "data": {
                "event": {
                    "name": "Test Event",
                    "sets": {
                        "nodes": [
                            {
                                "id": 1,
                                "fullRoundText": "Winners Round 1",
                                "identifier": "W1",
                                "state": 2,
                                "updatedAt": 1640995200,
                                "startedAt": None,
                                "completedAt": None,
                                "slots": [
                                    {
                                        "id": 1,
                                        "entrant": {
                                            "id": 1,
                                            "name": "Player 1",
                                            "participants": [
                                                {"id": 1, "gamerTag": "TestPlayer1"}
                                            ],
                                        },
                                    },
                                    {
                                        "id": 2,
                                        "entrant": {
                                            "id": 2,
                                            "name": "Player 2",
                                            "participants": [
                                                {"id": 2, "gamerTag": "TestPlayer2"}
                                            ],
                                        },
                                    },
                                ],
                                "phaseGroup": {
                                    "id": 1,
                                    "displayIdentifier": "A1",
                                    "phase": {"id": 1, "name": "Winner's Bracket"},
                                },
                                "stream": None,
                                "station": {"id": 1, "number": 5},
                            }
                        ]
                    },
                }
            }
        }

        result: TournamentState = api.parse_api_response(mock_data)

        assert result["event_name"] == "Test Event"
        assert len(result["sets"]) == 1

        parsed_set = result["sets"][0]
        assert parsed_set["id"] == 1
        assert parsed_set["player1"]["tag"] == "TestPlayer1"
        assert parsed_set["player2"]["tag"] == "TestPlayer2"
        assert parsed_set["state"] == 2
        assert parsed_set["station"] == 5
        assert parsed_set["stream"] is None
        assert "Winner's Bracket - Winners Round 1" in (parsed_set["displayName"] or "")

    def test_parse_api_response_missing_players(self):
        """Test parsing response with missing player data"""
        api = TournamentAPI()

        mock_data = {
            "data": {
                "event": {
                    "name": "Test Event",
                    "sets": {
                        "nodes": [
                            {
                                "id": 1,
                                "fullRoundText": "Winners Round 1",
                                "identifier": "W1",
                                "state": 1,
                                "updatedAt": 1640995200,
                                "startedAt": None,
                                "completedAt": None,
                                "slots": [
                                    {"id": 1, "entrant": None},
                                    {"id": 2, "entrant": None},
                                ],
                                "phaseGroup": {
                                    "id": 1,
                                    "displayIdentifier": "A1",
                                    "phase": {"id": 1, "name": "Winner's Bracket"},
                                },
                                "stream": None,
                                "station": None,
                            }
                        ]
                    },
                }
            }
        }

        result = api.parse_api_response(mock_data)

        assert result["event_name"] == "Test Event"
        # Matches with TBD players are now filtered out by the API
        assert len(result["sets"]) == 0

    def test_parse_api_response_invalid_data_returns_mock(self):
        """Test parsing invalid data returns mock data"""
        api = TournamentAPI()

        invalid_data = {"invalid": "structure"}

        result = api.parse_api_response(invalid_data)

        assert result == MOCK_TOURNAMENT_DATA
