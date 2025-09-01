"""Tests for demo mode functionality"""

from unittest.mock import patch

import pytest

from matchcaller.matchcaller import MOCK_TOURNAMENT_DATA, TournamentDisplay, main


@pytest.mark.integration
class TestDemoMode:
    """Test demo mode functionality"""

    def test_demo_mode_forces_mock_data_parameters(self):
        """Test that demo mode forces None parameters regardless of input"""
        test_args = [
            "--demo",
            "--token",
            "should_be_ignored",
            "--event",
            "should_be_ignored",
        ]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch(
            "matchcaller.__main__.time.sleep"
        ):  # Skip sleep delays in tests

            mock_app = mock_app_class.return_value
            mock_app.run.return_value = None

            main()

            # Should have been called with None values
            mock_app_class.assert_called_once_with(
                api_token=None, event_id=None, event_slug=None
            )

    def test_demo_mode_with_no_arguments(self):
        """Test that missing token/event automatically enables demo mode"""
        test_args: list[str] = []  # No arguments

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch(
            "matchcaller.__main__.time.sleep"
        ):  # Skip sleep delays in tests

            mock_app = mock_app_class.return_value
            mock_app.run.return_value = None

            main()

            # Should have been called with None values (demo mode)
            mock_app_class.assert_called_once_with(
                api_token=None, event_id=None, event_slug=None
            )

    def test_demo_mode_with_partial_arguments(self):
        """Test that missing event ID/slug enables demo mode even with token"""
        test_args = ["--token", "valid_token"]  # Token but no event

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch(
            "matchcaller.__main__.time.sleep"
        ):  # Skip sleep delays in tests

            mock_app = mock_app_class.return_value
            mock_app.run.return_value = None

            main()

            # Should still use demo mode (None values)
            mock_app_class.assert_called_once_with(
                api_token=None, event_id=None, event_slug=None
            )

    def test_real_mode_with_token_and_event_id(self):
        """Test that providing token and event ID enables real mode"""
        test_args = ["--token", "real_token", "--event", "12345"]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch(
            "matchcaller.__main__.time.sleep"
        ):  # Skip sleep delays in tests

            mock_app = mock_app_class.return_value
            mock_app.run.return_value = None

            main()

            # Should have been called with real values
            mock_app_class.assert_called_once_with(
                api_token="real_token", event_id="12345", event_slug=None
            )

    def test_real_mode_with_token_and_slug(self):
        """Test that providing token and slug enables real mode"""
        test_args = ["--token", "real_token", "--slug", "tournament/test/event/singles"]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch(
            "matchcaller.__main__.time.sleep"
        ):  # Skip sleep delays in tests

            mock_app = mock_app_class.return_value
            mock_app.run.return_value = None

            main()

            # Should have been called with real values
            mock_app_class.assert_called_once_with(
                api_token="real_token",
                event_id=None,
                event_slug="tournament/test/event/singles",
            )

    # @pytest.mark.skip("Async TUI tests hanging - needs investigation")
    @pytest.mark.asyncio
    async def test_demo_app_uses_mock_data(self):
        """Test that demo mode app actually uses mock data"""
        app = TournamentDisplay()  # No parameters = demo mode

        async with app.run_test() as pilot:
            await pilot.pause(2.0)  # Wait longer for mock data to load

            # Should have loaded mock data
            assert app.event_name == MOCK_TOURNAMENT_DATA["event_name"]
            assert app.total_sets == len(MOCK_TOURNAMENT_DATA["sets"])
            # The last_update might show timestamp from periodic updates, but data should be mock

    # @pytest.mark.skip("Async TUI tests hanging - needs investigation")
    @pytest.mark.asyncio
    async def test_demo_app_still_responds_to_refresh(self):
        """Test that demo mode still responds to refresh commands"""
        app = TournamentDisplay()  # Demo mode

        async with app.run_test() as pilot:
            await pilot.pause(2.0)  # Wait for initial load

            initial_event_name = app.event_name
            initial_sets = app.total_sets

            # Trigger refresh
            await pilot.press("r")
            await pilot.pause(1.0)

            # Should still have mock data after refresh
            assert app.event_name == initial_event_name
            assert app.total_sets == initial_sets

    def test_keyboard_interrupt_handling(self):
        """Test that KeyboardInterrupt is handled gracefully"""
        test_args = ["--demo"]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch(
            "matchcaller.__main__.time.sleep"
        ):  # Skip sleep delays in tests

            mock_app = mock_app_class.return_value
            mock_app.run.side_effect = KeyboardInterrupt()

            # Should not raise exception, main() should handle it
            main()

            mock_app.run.assert_called_once()

    def test_general_exception_handling(self):
        """Test that general exceptions are handled gracefully"""
        test_args = ["--demo"]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch(
            "matchcaller.__main__.time.sleep"
        ):  # Skip sleep delays in tests

            mock_app = mock_app_class.return_value
            mock_app.run.side_effect = Exception("Test error")

            # Should not raise exception, main() should handle it
            main()

            mock_app.run.assert_called_once()

    def test_argument_parsing_edge_cases(self):
        """Test edge cases in argument parsing"""
        # Test empty string arguments
        test_cases = [
            ["--token", "", "--event", ""],  # Empty strings
            ["--token", "token", "--event", "", "--slug", ""],  # Mixed empty
        ]

        for test_args in test_cases:
            with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
                "matchcaller.__main__.TournamentDisplay"
            ) as mock_app_class, patch(
                "matchcaller.__main__.time.sleep"
            ):  # Skip sleep delays in tests

                mock_app = mock_app_class.return_value
                mock_app.run.return_value = None

                main()

                # Empty strings should trigger demo mode
                args, kwargs = mock_app_class.call_args
                # Either all None (demo) or has real values, not empty strings
                if kwargs["api_token"] is not None:
                    assert kwargs["api_token"] != ""
                if kwargs["event_id"] is not None:
                    assert kwargs["event_id"] != ""
                if kwargs["event_slug"] is not None:
                    assert kwargs["event_slug"] != ""


@pytest.mark.integration
class TestLogging:
    """Test logging functionality in demo and real modes"""

    @patch("matchcaller.__main__.log")
    def test_demo_mode_logging(self, mock_log):
        """Test that demo mode logs appropriate messages"""
        test_args = ["--demo"]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):

            mock_app = mock_app_class.return_value
            mock_app.run.return_value = None

            main()

            # Check that demo mode was logged
            log_calls = [str(call) for call in mock_log.call_args_list]
            assert any("DEMO mode" in call for call in log_calls)

    @patch("matchcaller.__main__.log")
    def test_real_mode_logging(self, mock_log):
        """Test that real mode logs appropriate messages"""
        test_args = ["--token", "real_token", "--event", "12345"]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):

            mock_app = mock_app_class.return_value
            mock_app.run.return_value = None

            main()

            # Check that real mode was logged
            log_calls = [str(call) for call in mock_log.call_args_list]
            assert any("REAL start.gg data" in call for call in log_calls)
