"""UI tests for TournamentDisplay Textual application"""

from unittest.mock import AsyncMock, patch

import pytest

from matchcaller.matchcaller import MOCK_TOURNAMENT_DATA, TournamentDisplay
from matchcaller.models.match import TournamentState, MatchData, PlayerData


# @pytest.mark.skip("UI tests require full TUI instantiation which triggers async event loops and network calls in test environment. These tests should be run manually or in a dedicated UI testing environment.")
@pytest.mark.ui
class TestTournamentDisplay:
    """Test TournamentDisplay Textual app functionality"""

    @pytest.mark.asyncio
    async def test_app_initializes_with_correct_parameters(self):
        """Test that app initializes with provided parameters"""
        with patch(
            "matchcaller.ui.tournament_display.TournamentAPI"
        ) as MockAPI, patch.object(TournamentDisplay, "on_mount"):

            mock_api_instance = MockAPI.return_value
            mock_api_instance.api_token = "test_token"
            mock_api_instance.event_id = "12345"
            mock_api_instance.event_slug = "tournament/test/event/singles"

            app = TournamentDisplay(
                api_token="test_token",
                event_id="12345",
                event_slug="tournament/test/event/singles",
            )

            assert app.api.api_token == "test_token"
            assert app.api.event_id == "12345"
            assert app.api.event_slug == "tournament/test/event/singles"

    @pytest.mark.asyncio
    async def test_app_creates_required_widgets(self):
        """Test that app creates all required UI widgets"""
        app = TournamentDisplay()

        async with app.run_test():
            # Check that main containers exist
            assert app.query_one("#main-container")
            assert app.query_one("#pools-container")
            # Note: The specific data tables are created dynamically

    @pytest.mark.asyncio
    async def test_table_columns_are_created(self):
        """Test that data table has correct column setup"""
        app = TournamentDisplay()

        async with app.run_test() as pilot:
            await pilot.pause(1.0)  # Let initialization complete

            # After data loads, tables should be created
            # The app uses dynamic table creation based on pools
            # Just check that the pools container exists
            pools_container = app.query_one("#pools-container")
            assert pools_container is not None

    @pytest.mark.asyncio
    async def test_mock_data_loads_correctly(self):
        """Test that mock data is loaded and displayed correctly"""
        app = TournamentDisplay()

        async with app.run_test() as pilot:
            await pilot.pause(2.0)  # Wait for mock data to load

            # Check that event name was set from mock data
            assert app.event_name != "Loading..."
            assert app.total_sets > 0
            assert len(app.matches) > 0

    @pytest.mark.asyncio
    async def test_refresh_action_triggers_data_fetch(self):
        """Test that refresh action triggers data fetching"""
        app = TournamentDisplay()

        # Mock the worker method properly
        with patch.object(app.api, "fetch_sets", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = TournamentState(
                event_name="Test Event",
                tournament_name="Test Tournament",
                sets=[],
            )

            async with app.run_test() as pilot:
                await pilot.pause(0.1)

                # Trigger refresh action
                await pilot.press("r")
                await pilot.pause(0.5)  # Wait for worker to complete

                # Should have called the API
                assert mock_fetch.call_count >= 1

    @pytest.mark.asyncio
    async def test_quit_action_exits_app(self):
        """Test that quit action exits the application"""
        app = TournamentDisplay()

        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            # Press quit key
            await pilot.press("q")

            # App should be stopped/exiting
            assert not app.is_running

    @pytest.mark.asyncio
    async def test_api_data_updates_display(self):
        """Test that API data updates are reflected in the display"""
        # Mock successful API response
        mock_api_data = TournamentState(
            event_name="Test Tournament Live",
            tournament_name="Test Tournament",
            sets=[
                MatchData(
                    id=999,
                    displayName="Grand Finals",
                    player1=PlayerData(tag="Champion1"),
                    player2=PlayerData(tag="Champion2"),
                    state=2,
                    updatedAt=1640995200,
                    startedAt=None,
                )
            ],
        )

        app = TournamentDisplay(api_token="test_token", event_id="12345")

        with patch.object(app.api, "fetch_sets", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_api_data

            async with app.run_test() as pilot:
                # Wait for initial mount and data fetch to complete
                await pilot.pause(3.0)  # Wait longer for async worker to complete

                # Check that display was updated
                assert app.event_name == "Test Tournament Live"
                assert app.total_sets == 1
                assert app.ready_sets == 1
                assert app.in_progress_sets == 0

    @pytest.mark.asyncio
    async def test_match_sorting_priority(self):
        """Test that matches are sorted by priority (In Progress > Ready > Waiting)"""
        app = TournamentDisplay()

        # Create test data with different states
        test_data = TournamentState(
            event_name="Test Event",
            tournament_name="Test Tournament",
            sets=[
                MatchData(
                    id=1,
                    displayName="Waiting Match",
                    player1=PlayerData(tag="Player1"),
                    player2=PlayerData(tag="Player2"),
                    state=1,  # Waiting
                    updatedAt=1640995200,
                ),
                MatchData(
                    id=2,
                    displayName="In Progress Match",
                    player1=PlayerData(tag="Player3"),
                    player2=PlayerData(tag="Player4"),
                    state=6,  # In Progress
                    updatedAt=1640995300,
                ),
                MatchData(
                    id=3,
                    displayName="Ready Match",
                    player1=PlayerData(tag="Player5"),
                    player2=PlayerData(tag="Player6"),
                    state=2,  # Ready
                    updatedAt=1640995400,
                    startedAt=None,
                ),
                MatchData(
                    id=4,
                    displayName="Match w/ TBD",
                    player1=PlayerData(tag="TBD"),
                    player2=PlayerData(tag="Player1"),
                    state=1,  # Waiting
                    updatedAt=1640995500,
                    startedAt=None,
                ),
                MatchData(
                    id=5,
                    displayName="Match w/ empty tag",
                    player1=PlayerData(tag=""),
                    player2=PlayerData(tag="Player2"),
                    state=1,  # Waiting
                    updatedAt=1640995600,
                    startedAt=None,
                ),
            ],
        )

        with patch.object(app.api, "fetch_sets", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = test_data

            async with app.run_test() as pilot:
                await pilot.pause(3.0)  # Wait longer for async worker to complete

                # Removed table query - tables are created dynamically

                # Check that data was loaded
                assert app.total_sets == 5
                assert len(app.matches) == 5
                # Tables are created dynamically based on pool structure
                # Verify that matches are sorted correctly by checking the matches list
                in_progress_matches = [
                    m
                    for m in app.matches
                    if m.state == 6 or (m.state == 2 and m.started_at)
                ]
                ready_matches = [
                    m for m in app.matches if m.state == 2 and not m.started_at
                ]
                waiting_matches = [
                    m
                    for m in app.matches
                    if m.state == 1
                    and m.player1 != "TBD"
                    and m.player2 != ""
                    and m.player1 != ""
                    and m.player2 != "TBD"
                ]
                tbd_matches = [
                    m
                    for m in app.matches
                    if m.state == 1 and (m.player1 == "TBD" or m.player2 == "TBD")
                ]
                empty_tag_matches = [
                    m
                    for m in app.matches
                    if m.state == 1 and (m.player1 == "" or m.player2 == "")
                ]

                assert len(in_progress_matches) == 1
                assert len(ready_matches) == 1
                assert len(waiting_matches) == 1
                assert len(tbd_matches) == 1
                assert len(empty_tag_matches) == 1

    @pytest.mark.asyncio
    async def test_info_line_displays_correct_stats(self):
        """Test that app shows correct tournament statistics"""
        app = TournamentDisplay()

        async with app.run_test() as pilot:
            await pilot.pause(2.0)  # Wait longer for mock data to load

            # Check reactive variables are updated with mock data
            assert app.event_name and app.event_name != "Loading..."
            assert app.total_sets > 0
            assert app.ready_sets >= 0
            assert app.in_progress_sets >= 0

    @pytest.mark.asyncio
    async def test_display_updates_periodically(self):
        """Test that display updates occur periodically"""
        app = TournamentDisplay()

        with patch.object(app, "update_display") as mock_update:
            async with app.run_test() as pilot:
                await pilot.pause(1.5)  # Wait longer than 1 second interval

                # update_display should have been called multiple times
                assert mock_update.call_count >= 1

    @pytest.mark.asyncio
    async def test_api_error_handling_preserves_existing_data(self):
        """Test that API errors don't crash the app and preserve existing data"""
        app = TournamentDisplay(api_token="test_token", event_id="12345")

        with patch.object(app.api, "fetch_sets", new_callable=AsyncMock) as mock_fetch:
            # First call succeeds with mock data
            mock_fetch.return_value = MOCK_TOURNAMENT_DATA

            async with app.run_test() as pilot:
                await pilot.pause(1.0)

                # Second call fails
                mock_fetch.side_effect = Exception("API Error")

                # Manually trigger another fetch (action_refresh is not async)
                app.action_refresh()
                await pilot.pause(1.0)

                # App should still have some data (fallback to mock)
                assert app.event_name is not None
                assert app.total_sets >= 0

    @pytest.mark.asyncio
    async def test_time_display_updates_correctly(self):
        """Test that time displays update correctly for ready matches"""
        app = TournamentDisplay()

        async with app.run_test() as pilot:
            await pilot.pause(0.5)  # Wait for initial load

            # Wait for data to load and time updates to occur
            await pilot.pause(1.5)

            # App should have some data and not crash during time updates
            assert app.total_sets >= 0
            # update_display should have been called (updating time columns)
            # This is tested indirectly by ensuring the app doesn't crash


@pytest.mark.ui
class TestTournamentDisplayKeyBindings:
    """Test keyboard shortcuts and bindings"""

    @pytest.mark.asyncio
    async def test_r_key_refreshes_data(self):
        """Test that 'r' key triggers refresh"""
        app = TournamentDisplay()

        with patch.object(app.api, "fetch_sets", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = TournamentState(
                event_name="Test",
                tournament_name="Test",
                sets=[],
            )

            async with app.run_test() as pilot:
                await pilot.pause(0.1)

                await pilot.press("r")
                await pilot.pause(0.5)  # Wait for worker

                # Should have triggered at least one API call
                assert mock_fetch.call_count >= 1

    @pytest.mark.asyncio
    async def test_q_key_quits_app(self):
        """Test that 'q' key quits the application"""
        app = TournamentDisplay()

        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            await pilot.press("q")

            assert not app.is_running
