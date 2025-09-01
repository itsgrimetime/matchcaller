"""Integration tests for data parsing and model functionality"""

import time
from typing import Any, Optional

import pytest

from matchcaller.matchcaller import MOCK_TOURNAMENT_DATA, MatchRow
from matchcaller.models.match import MatchData, MatchState, PlayerData, SetData


def create_test_match_data(
    id: int = 123,
    displayName: str = "Test Bracket",
    player1: Optional[PlayerData] = None,
    player2: Optional[PlayerData] = None,
    state: int = 2,
    updatedAt: Optional[int] = None,
    startedAt: Optional[int] = None,
    station: Optional[str] = None,
    stream: Optional[str] = None,
    poolName: str = "Test Pool",
    **kwargs: Any
) -> MatchData:
    """Helper function to create test MatchData with sensible defaults"""
    if player1 is None:
        player1 = PlayerData(tag="Alice")
    if player2 is None:
        player2 = PlayerData(tag="Bob")
    if updatedAt is None:
        updatedAt = int(time.time())
        
    return MatchData(
        id=id,
        displayName=displayName,
        player1=player1,
        player2=player2,
        state=state,
        updatedAt=updatedAt,
        startedAt=startedAt,
        station=station,
        stream=stream,
        poolName=poolName,
        **kwargs
    )


@pytest.mark.integration
class TestMatchRow:
    """Test MatchRow data model functionality"""

    def test_match_row_creation_from_valid_data(self):
        """Test creating MatchRow from valid set data"""
        set_data = create_test_match_data(
            displayName="Winners Bracket - Round 1",
            player1=PlayerData(tag="TestPlayer1"),
            player2=PlayerData(tag="TestPlayer2"),
            state=MatchState.READY,
            stream="stream1",
            poolName="Pool 1",
        )

        match = MatchRow(set_data)

        assert match.id == 123
        assert match.bracket == "Winners Bracket - Round 1"
        assert match.player1 == "TestPlayer1"
        assert match.player2 == "TestPlayer2"
        assert match.state == MatchState.READY
        assert match.station is None
        assert match.stream == "stream1"

    def test_match_row_with_missing_players(self):
        """Test MatchRow handles missing player data gracefully"""
        set_data = create_test_match_data(
            displayName="Winners Bracket - Round 1",
            player1=PlayerData(tag="TBD"),
            player2=PlayerData(tag="TBD"),
            state=1,
            poolName="Pool 2",
        )

        match = MatchRow(set_data)

        assert match.player1 == "TBD"
        assert match.player2 == "TBD"

    def test_match_name_property(self):
        """Test match_name property formatting"""
        set_data = create_test_match_data()
        match = MatchRow(set_data)
        assert match.match_name == "Alice vs Bob"

    def test_status_icon_ready_state(self):
        """Test status icon for ready state (state 2, no startedAt)"""
        set_data = create_test_match_data(state=2, startedAt=None)
        match = MatchRow(set_data)
        assert match.status_icon == "[red]🔴[/red]"

    def test_status_icon_in_progress_state_2_with_started_at(self):
        """Test status icon for state 2 with startedAt (actually in progress)"""
        set_data = create_test_match_data(
            state=2,
            startedAt=int(time.time()) - 300,  # Started 5 minutes ago
        )
        match = MatchRow(set_data)
        assert match.status_icon == "[yellow]🟡[/yellow]"

    def test_status_icon_in_progress_state_6(self):
        """Test status icon for explicit in progress state (state 6)"""
        set_data = create_test_match_data(state=6)
        match = MatchRow(set_data)
        assert match.status_icon == "[yellow]🟡[/yellow]"

    def test_status_icon_waiting_state(self):
        """Test status icon for waiting state (state 1)"""
        set_data = create_test_match_data(state=1)
        match = MatchRow(set_data)
        assert match.status_icon == "[dim]⚪[/dim]"

    def test_status_text_with_station(self):
        """Test status text includes station information"""
        set_data = create_test_match_data(state=2, station="3")
        match = MatchRow(set_data)
        assert "Station 3" in match.status_text

    def test_status_text_with_stream(self):
        """Test status text includes stream information"""
        set_data = create_test_match_data(state=6, stream="MainStream")
        match = MatchRow(set_data)
        assert "Stream: MainStream" in match.status_text

    def test_time_since_ready_recent(self):
        """Test time calculation for recently ready match"""
        now = int(time.time())
        set_data = create_test_match_data(
            state=2,
            updatedAt=now - 30,  # 30 seconds ago
        )
        match = MatchRow(set_data)
        assert match.time_since_ready == "30s"

    def test_time_since_ready_minutes(self):
        """Test time calculation for match ready minutes ago"""
        now = int(time.time())
        set_data = create_test_match_data(
            state=2,
            updatedAt=now - 150,  # 2.5 minutes ago
        )
        match = MatchRow(set_data)
        result = match.time_since_ready
        assert result == "2m 30s"

    def test_time_since_started_for_in_progress_match(self):
        """Test time calculation for match that has started"""
        now = int(time.time())
        set_data = create_test_match_data(
            state=6,
            updatedAt=now - 300,
            startedAt=now - 180,  # Started 3 minutes ago
        )
        match = MatchRow(set_data)
        assert match.time_since_ready == "3m"

    def test_time_since_ready_waiting_match_returns_dash(self):
        """Test that waiting matches return dash for time"""
        set_data = create_test_match_data(state=1)
        match = MatchRow(set_data)
        # Waiting matches now show time since updated, not dash
        assert "s" in match.time_since_ready  # Should show seconds since updated


@pytest.mark.integration
class TestMockData:
    """Test that mock data is valid and consistent"""

    def test_mock_tournament_data_structure(self):
        """Test that mock data has expected structure"""
        assert hasattr(MOCK_TOURNAMENT_DATA, "event_name")
        assert hasattr(MOCK_TOURNAMENT_DATA, "sets")
        assert isinstance(MOCK_TOURNAMENT_DATA.sets, list)

    def test_mock_sets_have_required_fields(self):
        """Test that all mock sets have required fields"""
        for set_data in MOCK_TOURNAMENT_DATA.sets:
            required_fields = ["id", "displayName", "player1", "player2", "state", "updatedAt"]
            for field in required_fields:
                assert hasattr(set_data, field), f"Missing required field: {field}"

    def test_mock_sets_create_valid_match_rows(self):
        """Test that all mock sets can be used to create MatchRow objects"""
        for set_data in MOCK_TOURNAMENT_DATA.sets:
            match = MatchRow(set_data)
            assert match.id is not None
            assert match.bracket is not None
            assert match.state in [1, 2, 3, 6, 7]

    def test_mock_data_has_variety_of_states(self):
        """Test that mock data includes different match states"""
        states = {set_data.state for set_data in MOCK_TOURNAMENT_DATA.sets}

        # Should have at least ready (2) and in progress (6) states
        assert 2 in states, "Mock data should include ready matches"
        assert len(states) > 1, "Mock data should include variety of states"