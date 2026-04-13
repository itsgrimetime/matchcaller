"""Unit tests for dashboard grid helpers."""

import pytest

from matchcaller.models.dashboard import (
    LadderDisplayStatus,
    LadderState,
    LadderStanding,
    Station,
    StationState,
)
from matchcaller.models.match import MatchData, MatchRow, PlayerData
from matchcaller.ui.dashboard_grid import (
    build_ladder_rows,
    build_station_summary,
    build_standings_rows,
)


def _row(match_id: int, *, station: int | None = None) -> MatchRow:
    return MatchRow(
        MatchData(
            id=match_id,
            displayName=f"Ladder - Round {match_id}",
            poolName="Ladder",
            player1=PlayerData(tag="Snap"),
            player2=PlayerData(tag="Chetter"),
            state=2,
            startedAt=100,
            updatedAt=100,
            station=station,
        )
    )


@pytest.mark.unit
class TestDashboardGridHelpers:
    def test_build_station_summary(self):
        state = StationState(
            stations=[Station(id="1", number=1), Station(id="2", number=2)],
            occupied_numbers={2},
            available_numbers=[1],
        )

        assert build_station_summary(state) == "Free: 1 | Busy: 2"

    def test_build_station_summary_handles_missing_state(self):
        assert build_station_summary(None) == "Stations unavailable"

    def test_build_ladder_rows_uses_existing_match_row_format(self):
        rows = build_ladder_rows([_row(1, station=3)])

        assert rows[0][0].startswith("Snap vs Chetter")
        assert "Station 3" in rows[0][1]

    def test_build_standings_rows(self):
        ladder = LadderState(
            display_status=LadderDisplayStatus.ACTIVE,
            event_name="Melee Ladder",
            standings=[
                LadderStanding(placement=1, entrant_name="Snap", wins=8, losses=0),
                LadderStanding(placement=2, entrant_name="Chetter", wins=9, losses=1),
            ],
        )

        assert build_standings_rows(ladder) == [
            ["#1", "Snap", "8-0"],
            ["#2", "Chetter", "9-1"],
        ]
