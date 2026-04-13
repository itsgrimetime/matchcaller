"""Unit tests for dashboard mode and ladder helper models."""

import pytest

from matchcaller.models.dashboard import (
    DashboardState,
    LadderDisplayStatus,
    LadderState,
    LadderStanding,
    Station,
    ViewMode,
    derive_ladder_display_status,
    derive_station_state,
    filter_late_bracket_matches,
    resolve_dashboard_view,
)
from matchcaller.models.match import MatchData, MatchRow, PlayerData, TournamentState


def _match(
    match_id: int,
    *,
    display_name: str,
    pool_name: str,
    state: int = 2,
    station: int | None = None,
) -> MatchRow:
    return MatchRow(
        MatchData(
            id=match_id,
            displayName=display_name,
            poolName=pool_name,
            player1=PlayerData(tag=f"Player {match_id}A"),
            player2=PlayerData(tag=f"Player {match_id}B"),
            state=state,
            updatedAt=100 + match_id,
            station=station,
        )
    )


@pytest.mark.unit
class TestDashboardModels:
    def test_ladder_status_not_found_waiting_active_completed(self):
        assert derive_ladder_display_status(
            event_state=None,
            active_set_count=0,
        ) == LadderDisplayStatus.NOT_FOUND
        assert derive_ladder_display_status(
            event_state="CREATED",
            active_set_count=0,
        ) == LadderDisplayStatus.WAITING
        assert derive_ladder_display_status(
            event_state="ACTIVE",
            active_set_count=0,
        ) == LadderDisplayStatus.ACTIVE
        assert derive_ladder_display_status(
            event_state="CREATED",
            active_set_count=2,
        ) == LadderDisplayStatus.ACTIVE
        assert derive_ladder_display_status(
            event_state="COMPLETED",
            active_set_count=2,
        ) == LadderDisplayStatus.COMPLETED
        assert derive_ladder_display_status(
            event_state="INVALID",
            active_set_count=1,
        ) == LadderDisplayStatus.WAITING

    def test_auto_does_not_promote_completed_fresh_launch_but_keeps_visible_ladder(self):
        completed = LadderState(
            display_status=LadderDisplayStatus.COMPLETED,
            event_id="1",
            event_name="Melee Ladder",
            event_slug="tournament/test/event/ladder",
            event_state="COMPLETED",
            start_at=None,
            entrants_count=10,
            sets=[],
            standings=[LadderStanding(placement=1, entrant_name="Snap", wins=8, losses=0)],
            auto_should_show=False,
        )

        assert resolve_dashboard_view(
            requested_view=ViewMode.AUTO,
            ladder=completed,
            ladder_was_visible=False,
        ) == ViewMode.MAIN
        assert resolve_dashboard_view(
            requested_view=ViewMode.AUTO,
            ladder=completed,
            ladder_was_visible=True,
        ) == ViewMode.SPLIT

    def test_explicit_modes_resolve_without_auto_promotion(self):
        waiting = LadderState(
            display_status=LadderDisplayStatus.WAITING,
            event_id="1",
            event_name="Melee Ladder",
            event_slug="tournament/test/event/ladder",
            event_state="CREATED",
            start_at=1776229200,
            entrants_count=0,
            sets=[],
            standings=[],
            auto_should_show=False,
        )

        assert resolve_dashboard_view(ViewMode.MAIN, waiting) == ViewMode.MAIN
        assert resolve_dashboard_view(ViewMode.SPLIT, waiting) == ViewMode.SPLIT
        assert resolve_dashboard_view(ViewMode.LADDER, waiting) == ViewMode.LADDER

    def test_station_availability_uses_active_match_station_numbers(self):
        state = derive_station_state(
            stations=[
                Station(id="s1", number=1),
                Station(id="s2", number=2),
                Station(id="s3", number=3),
            ],
            active_matches=[
                _match(1, display_name="Top 24 - WQ", pool_name="Top 24", station=2),
                _match(2, display_name="Ladder - Round 1", pool_name="Ladder", station=None),
            ],
        )

        assert state.occupied_numbers == {2}
        assert state.available_numbers == [1, 3]

    def test_filter_late_bracket_matches_prefers_top_24_and_top_8(self):
        matches = [
            _match(1, display_name="Pool A - Round 1", pool_name="Bracket - Pool 1"),
            _match(2, display_name="Top 24 - Winners", pool_name="Top 24 - Pool 1"),
            _match(3, display_name="Top 8 - Winners", pool_name="Top 8 - Pool 1"),
        ]

        assert [match.id for match in filter_late_bracket_matches(matches)] == [2, 3]

    def test_filter_late_bracket_matches_falls_back_to_all_matches(self):
        matches = [
            _match(1, display_name="Bracket - Round 1", pool_name="Bracket - Pool 1"),
            _match(2, display_name="Bracket - Round 2", pool_name="Bracket - Pool 2"),
        ]

        assert [match.id for match in filter_late_bracket_matches(matches)] == [1, 2]

    def test_dashboard_state_tracks_ladder_was_visible(self):
        main = TournamentState(event_name="Singles", tournament_name="Weekly", sets=[])
        dashboard = DashboardState(
            tournament_name="Weekly",
            main=main,
            ladder=None,
            stations=None,
            requested_view=ViewMode.AUTO,
            resolved_view=ViewMode.MAIN,
            ladder_was_visible=False,
            last_update="12:00:00",
        )

        assert dashboard.main is main
        assert dashboard.ladder is None
        assert dashboard.resolved_view == ViewMode.MAIN
        assert dashboard.ladder_was_visible is False
