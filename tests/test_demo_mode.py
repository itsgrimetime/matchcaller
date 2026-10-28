"""Tests for demo mode functionality"""

from unittest.mock import patch

import pytest

from matchcaller.matchcaller import MOCK_TOURNAMENT_DATA, TournamentDisplay, main


@pytest.fixture(autouse=True)
def _clear_event_filter_env(monkeypatch):
    """Keep CLI tests independent from the developer shell environment."""
    monkeypatch.delenv("EVENT_FILTER", raising=False)


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
                api_token=None,
                event_id=None,
                event_slug=None,
                tournament_slug=None,
                view_mode="main",
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
                api_token=None,
                event_id=None,
                event_slug=None,
                tournament_slug=None,
                view_mode="main",
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
                api_token=None,
                event_id=None,
                event_slug=None,
                tournament_slug=None,
                view_mode="main",
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
                api_token="real_token",
                event_id="12345",
                event_slug=None,
                tournament_slug=None,
                view_mode="auto",
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
                tournament_slug="test",
                view_mode="auto",
            )

    def test_real_mode_with_tournament_and_doubles_filter(self):
        from unittest.mock import AsyncMock

        test_args = [
            "--token",
            "real_token",
            "--tournament",
            "tournament/test-weekly",
            "--event-filter",
            "doubles",
        ]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.api.TournamentAPI"
        ) as mock_api_class, patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):
            mock_api = mock_api_class.return_value
            mock_api.get_events_for_tournament = AsyncMock(
                return_value=[
                    {
                        "id": "1",
                        "name": "Melee Singles",
                        "slug": "tournament/test-weekly/event/melee-singles",
                    },
                    {
                        "id": "2",
                        "name": "Melee Doubles",
                        "slug": "tournament/test-weekly/event/melee-doubles",
                    },
                ]
            )
            mock_app_class.return_value.run.return_value = None

            main()

            mock_api.get_events_for_tournament.assert_awaited_once_with(
                "tournament/test-weekly"
            )
            kwargs = mock_app_class.call_args.kwargs
            assert kwargs["event_slug"] == "tournament/test-weekly/event/melee-doubles"
            assert kwargs["tournament_slug"] == "test-weekly"
            assert kwargs["view_mode"] == "auto"

    def test_real_mode_auto_filter_uses_multi_event_source_for_tournament(self):
        test_args = [
            "--token",
            "real_token",
            "--tournament",
            "tournament/test-weekly",
            "--event-filter",
            "auto",
        ]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.api.MultiEventTournamentAPI"
        ) as mock_multi_api_class, patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):
            mock_app_class.return_value.run.return_value = None

            main()

            mock_multi_api_class.assert_called_once_with(
                api_token="real_token",
                tournament_slug="test-weekly",
            )
            kwargs = mock_app_class.call_args.kwargs
            assert kwargs["event_slug"] is None
            assert kwargs["tournament_slug"] == "test-weekly"
            assert kwargs["api"] is mock_multi_api_class.return_value

    def test_short_url_auto_filter_uses_multi_event_source(self):
        from unittest.mock import AsyncMock

        test_args = [
            "--token",
            "real_token",
            "--short-url",
            "mtf",
            "--event-filter",
            "auto",
        ]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.api.TournamentAPI"
        ) as mock_api_class, patch(
            "matchcaller.api.MultiEventTournamentAPI"
        ) as mock_multi_api_class, patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):
            mock_api = mock_api_class.return_value
            mock_api.get_events_for_tournament = AsyncMock(
                return_value=[
                    {
                        "id": "1",
                        "name": "Melee Singles",
                        "slug": "tournament/more-than-friendlies-285/event/melee-singles",
                    },
                ]
            )
            mock_app_class.return_value.run.return_value = None

            main()

            mock_api.get_events_for_tournament.assert_awaited_once_with("mtf")
            mock_multi_api_class.assert_called_once_with(
                api_token="real_token",
                tournament_slug="more-than-friendlies-285",
            )
            kwargs = mock_app_class.call_args.kwargs
            assert kwargs["event_slug"] is None
            assert kwargs["tournament_slug"] == "more-than-friendlies-285"
            assert kwargs["api"] is mock_multi_api_class.return_value

    def test_short_url_env_auto_filter_uses_multi_event_source(self, monkeypatch):
        from unittest.mock import AsyncMock

        monkeypatch.setenv("EVENT_FILTER", "auto")
        test_args = [
            "--token",
            "real_token",
            "--short-url",
            "mtf",
        ]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.api.TournamentAPI"
        ) as mock_api_class, patch(
            "matchcaller.api.MultiEventTournamentAPI"
        ) as mock_multi_api_class, patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):
            mock_api = mock_api_class.return_value
            mock_api.get_events_for_tournament = AsyncMock(
                return_value=[
                    {
                        "id": "1",
                        "name": "Melee Singles",
                        "slug": "tournament/more-than-friendlies-285/event/melee-singles",
                    },
                ]
            )
            mock_app_class.return_value.run.return_value = None

            main()

            mock_api.get_events_for_tournament.assert_awaited_once_with("mtf")
            mock_multi_api_class.assert_called_once_with(
                api_token="real_token",
                tournament_slug="more-than-friendlies-285",
            )
            kwargs = mock_app_class.call_args.kwargs
            assert kwargs["event_slug"] is None
            assert kwargs["tournament_slug"] == "more-than-friendlies-285"
            assert kwargs["api"] is mock_multi_api_class.return_value

    def test_event_filter_cli_overrides_auto_environment(self, monkeypatch):
        from unittest.mock import AsyncMock

        monkeypatch.setenv("EVENT_FILTER", "auto")
        test_args = [
            "--token",
            "real_token",
            "--short-url",
            "mtf",
            "--event-filter",
            "singles",
        ]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.api.TournamentAPI"
        ) as mock_api_class, patch(
            "matchcaller.api.MultiEventTournamentAPI"
        ) as mock_multi_api_class, patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):
            mock_api = mock_api_class.return_value
            mock_api.get_events_for_tournament = AsyncMock(
                return_value=[
                    {
                        "id": "1",
                        "name": "Melee Singles",
                        "slug": "tournament/more-than-friendlies-285/event/melee-singles",
                    },
                    {
                        "id": "2",
                        "name": "Melee Doubles",
                        "slug": "tournament/more-than-friendlies-285/event/melee-doubles",
                    },
                ]
            )
            mock_app_class.return_value.run.return_value = None

            main()

            mock_multi_api_class.assert_not_called()
            kwargs = mock_app_class.call_args.kwargs
            assert kwargs["event_slug"] == (
                "tournament/more-than-friendlies-285/event/melee-singles"
            )
            assert kwargs["tournament_slug"] == "more-than-friendlies-285"

    def test_real_mode_accepts_tournament_page_as_slug_with_event_filter(self):
        from unittest.mock import AsyncMock

        test_args = [
            "--token",
            "real_token",
            "--slug",
            "https://www.start.gg/tournament/test-weekly/details",
            "--event-filter",
            "doubles",
        ]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.api.TournamentAPI"
        ) as mock_api_class, patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):
            mock_api = mock_api_class.return_value
            mock_api.get_events_for_tournament = AsyncMock(
                return_value=[
                    {
                        "id": "1",
                        "name": "Melee Singles",
                        "slug": "tournament/test-weekly/event/melee-singles",
                    },
                    {
                        "id": "2",
                        "name": "Melee Doubles",
                        "slug": "tournament/test-weekly/event/melee-doubles",
                    },
                ]
            )
            mock_app_class.return_value.run.return_value = None

            main()

            mock_api.get_events_for_tournament.assert_awaited_once_with(
                "tournament/test-weekly"
            )
            kwargs = mock_app_class.call_args.kwargs
            assert kwargs["event_slug"] == "tournament/test-weekly/event/melee-doubles"
            assert kwargs["tournament_slug"] == "test-weekly"

    def test_real_mode_normalizes_direct_event_url_slug(self):
        test_args = [
            "--token",
            "real_token",
            "--slug",
            "https://www.start.gg/tournament/test-weekly/event/melee-doubles",
        ]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.api.TournamentAPI"
        ) as mock_api_class, patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):
            mock_app_class.return_value.run.return_value = None

            main()

            mock_api_class.assert_not_called()
            kwargs = mock_app_class.call_args.kwargs
            assert kwargs["event_slug"] == "tournament/test-weekly/event/melee-doubles"
            assert kwargs["tournament_slug"] == "test-weekly"

    def test_event_id_real_mode_defaults_auto_without_tournament_slug(self):
        test_args = ["--token", "real_token", "--event", "12345"]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):
            mock_app_class.return_value.run.return_value = None

            main()

            kwargs = mock_app_class.call_args.kwargs
            assert kwargs["view_mode"] == "auto"
            assert kwargs["tournament_slug"] is None

    def test_real_mode_defaults_to_auto_view(self):
        test_args = ["--token", "real_token", "--slug", "tournament/test/event/singles"]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):
            mock_app_class.return_value.run.return_value = None

            main()

            kwargs = mock_app_class.call_args.kwargs
            assert kwargs["view_mode"] == "auto"
            assert kwargs["tournament_slug"] == "test"

    def test_real_mode_accepts_explicit_ladder_view(self):
        test_args = [
            "--token",
            "real_token",
            "--slug",
            "tournament/test/event/singles",
            "--view",
            "ladder",
        ]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):
            mock_app_class.return_value.run.return_value = None

            main()

            kwargs = mock_app_class.call_args.kwargs
            assert kwargs["view_mode"] == "ladder"

    def test_demo_mode_falls_back_to_main_view_when_ladder_requested(self):
        test_args = ["--demo", "--view", "ladder"]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):
            mock_app_class.return_value.run.return_value = None

            main()

            kwargs = mock_app_class.call_args.kwargs
            assert kwargs["api_token"] is None
            assert kwargs["view_mode"] == "main"

    def test_short_url_passes_resolved_tournament_slug(self):
        from unittest.mock import AsyncMock

        test_args = [
            "--token",
            "real_token",
            "--short-url",
            "weekly",
            "--event-filter",
            "singles",
        ]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.utils.resolve.resolve_tournament_slug_from_unique_string",
            return_value="melee-abbey-tavern-137",
        ), patch("matchcaller.api.TournamentAPI") as mock_api_class, patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):
            mock_api = mock_api_class.return_value
            events = [
                {
                    "id": "1",
                    "name": "Melee Singles",
                    "slug": "tournament/melee-abbey-tavern-137/event/melee-singles",
                },
                {
                    "id": "2",
                    "name": "Melee Ladder",
                    "slug": "tournament/melee-abbey-tavern-137/event/melee-ladder",
                },
            ]
            mock_api.get_events_for_tournament = AsyncMock(
                side_effect=[
                    [],
                    events,
                ]
            )
            mock_app_class.return_value.run.return_value = None

            main()

            mock_api_class.return_value.find_nearest_abbey_tournament_slug.assert_not_called()
            mock_api.get_events_for_tournament.assert_any_await("weekly")
            mock_api.get_events_for_tournament.assert_any_await("melee-abbey-tavern-137")
            kwargs = mock_app_class.call_args.kwargs
            assert kwargs["event_slug"] == "tournament/melee-abbey-tavern-137/event/melee-singles"
            assert kwargs["tournament_slug"] == "melee-abbey-tavern-137"
            assert kwargs["view_mode"] == "auto"

    def test_short_url_uses_api_alias_before_redirect_resolution(self):
        from unittest.mock import AsyncMock

        test_args = [
            "--token",
            "real_token",
            "--short-url",
            "mtf",
            "--event-filter",
            "ult",
        ]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.utils.resolve.resolve_tournament_slug_from_unique_string",
            side_effect=AssertionError("redirect resolver should not be called"),
        ), patch("matchcaller.api.TournamentAPI") as mock_api_class, patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):
            mock_api = mock_api_class.return_value
            mock_api.get_events_for_tournament = AsyncMock(
                return_value=[
                    {
                        "id": "1",
                        "name": "Ult. Singles - Bracket",
                        "slug": "tournament/more-than-friendlies-285/event/ult-singles-bracket",
                    },
                    {
                        "id": "2",
                        "name": "Redemption Bracket - Ult. Singles",
                        "slug": "tournament/more-than-friendlies-285/event/redemption-bracket-ult-singles",
                    },
                ]
            )
            mock_app_class.return_value.run.return_value = None

            main()

            mock_api.get_events_for_tournament.assert_awaited_once_with("mtf")
            kwargs = mock_app_class.call_args.kwargs
            assert kwargs["event_slug"] == "tournament/more-than-friendlies-285/event/ult-singles-bracket"
            assert kwargs["tournament_slug"] == "more-than-friendlies-285"
            assert kwargs["view_mode"] == "auto"

    def test_full_short_url_uses_normalized_api_alias(self):
        from unittest.mock import AsyncMock

        test_args = [
            "--token",
            "real_token",
            "--short-url",
            "https://www.start.gg/mtf/",
            "--event-filter",
            "ult",
        ]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.utils.resolve.resolve_tournament_slug_from_unique_string",
            side_effect=AssertionError("redirect resolver should not be called"),
        ), patch("matchcaller.api.TournamentAPI") as mock_api_class, patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):
            mock_api = mock_api_class.return_value
            mock_api.get_events_for_tournament = AsyncMock(
                return_value=[
                    {
                        "id": "1",
                        "name": "Ult. Singles - Bracket",
                        "slug": "tournament/more-than-friendlies-285/event/ult-singles-bracket",
                    },
                    {
                        "id": "2",
                        "name": "Redemption Bracket - Ult. Singles",
                        "slug": "tournament/more-than-friendlies-285/event/redemption-bracket-ult-singles",
                    },
                ]
            )
            mock_app_class.return_value.run.return_value = None

            main()

            mock_api.get_events_for_tournament.assert_awaited_once_with("mtf")
            kwargs = mock_app_class.call_args.kwargs
            assert kwargs["event_slug"] == "tournament/more-than-friendlies-285/event/ult-singles-bracket"
            assert kwargs["tournament_slug"] == "more-than-friendlies-285"
            assert kwargs["view_mode"] == "auto"

    def test_short_url_falls_back_to_abbey_search_when_redirect_is_blocked(self):
        from unittest.mock import AsyncMock

        test_args = [
            "--token",
            "real_token",
            "--short-url",
            "abbey",
            "--event-filter",
            "melee-singles",
        ]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.utils.resolve.resolve_tournament_slug_from_unique_string",
            side_effect=RuntimeError("Cloudflare challenge"),
        ), patch("matchcaller.api.TournamentAPI") as mock_api_class, patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):
            mock_api = mock_api_class.return_value
            mock_api.find_nearest_abbey_tournament_slug = AsyncMock(
                return_value="melee-abbey-tavern-137"
            )
            mock_api.get_events_for_tournament = AsyncMock(
                side_effect=[
                    [],
                    [
                        {
                            "id": "1",
                            "name": "Melee Singles",
                            "slug": "tournament/melee-abbey-tavern-137/event/melee-singles",
                        }
                    ],
                ]
            )
            mock_app_class.return_value.run.return_value = None

            main()

            mock_api.find_nearest_abbey_tournament_slug.assert_awaited_once()
            mock_api.get_events_for_tournament.assert_any_await("abbey")
            mock_api.get_events_for_tournament.assert_any_await("melee-abbey-tavern-137")
            kwargs = mock_app_class.call_args.kwargs
            assert kwargs["event_slug"] == "tournament/melee-abbey-tavern-137/event/melee-singles"
            assert kwargs["tournament_slug"] == "melee-abbey-tavern-137"
            assert kwargs["view_mode"] == "auto"

    def test_abbey_short_url_uses_api_search_before_redirect_resolution(self):
        from unittest.mock import AsyncMock

        test_args = [
            "--token",
            "real_token",
            "--short-url",
            "abbey",
            "--event-filter",
            "melee-singles",
        ]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.utils.resolve.resolve_tournament_slug_from_unique_string"
        ) as mock_resolver, patch("matchcaller.api.TournamentAPI") as mock_api_class, patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):
            mock_api = mock_api_class.return_value
            mock_api.find_nearest_abbey_tournament_slug = AsyncMock(
                return_value="melee-abbey-tavern-137"
            )
            mock_api.get_events_for_tournament = AsyncMock(
                side_effect=[
                    [],
                    [
                        {
                            "id": "1",
                            "name": "Melee Singles",
                            "slug": "tournament/melee-abbey-tavern-137/event/melee-singles",
                        }
                    ],
                ]
            )
            mock_app_class.return_value.run.return_value = None

            main()

            mock_resolver.assert_not_called()
            mock_api.find_nearest_abbey_tournament_slug.assert_awaited_once()
            kwargs = mock_app_class.call_args.kwargs
            assert kwargs["event_slug"] == "tournament/melee-abbey-tavern-137/event/melee-singles"
            assert kwargs["tournament_slug"] == "melee-abbey-tavern-137"

    @pytest.mark.parametrize("event_filter", ["auto", "doubles", "singles"])
    def test_abbey_halloween_startup_preserves_event_selection(self, event_filter):
        from unittest.mock import AsyncMock

        tournament_slug = "melee-abbey-tavern-164-halloween-edition"
        events = [
            {
                "id": str(index),
                "name": f"Melee {name.title()}",
                "slug": f"tournament/{tournament_slug}/event/melee-{name}",
            }
            for index, name in enumerate(("singles", "doubles"), start=1)
        ]
        test_args = [
            "--token",
            "real_token",
            "--short-url",
            "abbey",
            "--event-filter",
            event_filter,
        ]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.api.TournamentAPI"
        ) as mock_api_class, patch(
            "matchcaller.api.MultiEventTournamentAPI"
        ) as mock_multi_api_class, patch(
            "matchcaller.utils.resolve.resolve_tournament_slug_from_unique_string"
        ) as mock_resolver, patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):
            mock_api = mock_api_class.return_value
            mock_api.get_events_for_tournament = AsyncMock(side_effect=[[], events])
            mock_api.find_nearest_abbey_tournament_slug = AsyncMock(
                return_value=tournament_slug
            )

            main()

            mock_resolver.assert_not_called()
            mock_api.find_nearest_abbey_tournament_slug.assert_awaited_once()
            mock_api.get_events_for_tournament.assert_any_await(tournament_slug)
            kwargs = mock_app_class.call_args.kwargs
            assert kwargs["tournament_slug"] == tournament_slug
            if event_filter == "auto":
                mock_multi_api_class.assert_called_once_with(
                    api_token="real_token", tournament_slug=tournament_slug
                )
                assert kwargs["api"] is mock_multi_api_class.return_value
                assert kwargs["event_slug"] is None
            else:
                mock_multi_api_class.assert_not_called()
                assert kwargs["event_slug"] == (
                    f"tournament/{tournament_slug}/event/melee-{event_filter}"
                )

    def test_simulate_mode_falls_back_to_main_view_when_ladder_requested(self):
        test_args = ["--simulate", "simulator_data/fake.json", "--view", "ladder"]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.simulator.bracket_simulator.BracketSimulator"
        ) as mock_simulator_class, patch(
            "matchcaller.simulator.bracket_simulator.SimulatedTournamentAPI"
        ) as mock_sim_api_class, patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):
            mock_simulator_class.return_value.load_tournament.return_value = True
            mock_app_class.return_value.run.return_value = None

            main()

            kwargs = mock_app_class.call_args.kwargs
            assert kwargs["view_mode"] == "main"
            assert kwargs["tournament_slug"] is None
            assert kwargs["api"] is mock_sim_api_class.return_value

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

    @patch("matchcaller.__main__.log")
    def test_real_mode_logging_never_includes_raw_token(self, mock_log):
        """Real startup logs must not expose the raw start.gg token."""
        raw_token = "real_token_that_must_not_be_logged"
        test_args = ["--token", raw_token, "--event", "12345"]

        with patch("sys.argv", ["matchcaller.py"] + test_args), patch(
            "matchcaller.__main__.TournamentDisplay"
        ) as mock_app_class, patch("matchcaller.__main__.time.sleep"):

            mock_app = mock_app_class.return_value
            mock_app.run.return_value = None

            main()

            log_calls = [str(call) for call in mock_log.call_args_list]
            assert all(raw_token not in call for call in log_calls)
