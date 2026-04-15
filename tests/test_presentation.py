"""Unit tests for pure UI presentation helpers."""

import pytest

from matchcaller.models.match import MatchData, MatchRow, PlayerData
from matchcaller.ui.presentation import (
    MATCH_TABLE_SEPARATOR_WIDTH,
    build_alert_tags,
    build_match_row,
    build_match_table_separator_row,
    calculate_column_widths,
    calculate_num_columns,
    group_matches_by_pool,
    sort_pool_matches,
    sort_pool_names,
)


def make_match(
    match_id: int,
    *,
    pool_name: str = "Pool A",
    state: int = 1,
    updated_at: int = 100,
    started_at: int | None = None,
    player1: str = "Alice",
    player2: str = "Bob",
    player1_discord_id: str | None = None,
    player2_discord_id: str | None = None,
) -> MatchRow:
    """Create a MatchRow with deterministic defaults for presentation tests."""
    return MatchRow(
        MatchData(
            id=match_id,
            displayName=f"Match {match_id}",
            player1=PlayerData(tag=player1, discord_id=player1_discord_id),
            player2=PlayerData(tag=player2, discord_id=player2_discord_id),
            state=state,
            updatedAt=updated_at,
            startedAt=started_at,
            poolName=pool_name,
        )
    )


@pytest.mark.unit
class TestPresentationHelpers:
    """Test pure presentation/layout helpers."""

    def test_group_matches_by_pool(self):
        matches = [
            make_match(1, pool_name="Pool B"),
            make_match(2, pool_name="Pool A"),
            make_match(3, pool_name="Pool B"),
        ]

        grouped = group_matches_by_pool(matches)

        assert list(grouped) == ["Pool B", "Pool A"]
        assert [match.id for match in grouped["Pool B"]] == [1, 3]
        assert [match.id for match in grouped["Pool A"]] == [2]

    def test_sort_pool_names(self):
        assert sort_pool_names(["Pool C", "Pool A", "Pool B"]) == [
            "Pool A",
            "Pool B",
            "Pool C",
        ]

    def test_sort_pool_matches_prioritizes_active_known_player_matches(self):
        sorted_matches = sort_pool_matches(
            [
                make_match(1, state=1, updated_at=100),
                make_match(2, state=2, started_at=300, updated_at=300),
                make_match(3, state=6, started_at=250, updated_at=250),
                make_match(4, state=2, updated_at=200),
                make_match(
                    5,
                    state=1,
                    updated_at=400,
                    player1="TBD",
                    player2="Carol",
                ),
            ]
        )

        assert [match.id for match in sorted_matches] == [2, 3, 4, 1, 5]

    def test_calculate_num_columns(self):
        assert calculate_num_columns(0) == 1
        assert calculate_num_columns(1) == 1
        assert calculate_num_columns(4) == 2
        assert calculate_num_columns(6) == 3
        assert calculate_num_columns(7) == 4

    def test_calculate_column_widths(self):
        assert calculate_column_widths(120, 2) == (26, 14, 10)
        assert calculate_column_widths(96, 2) == (22, 14, 8)
        assert calculate_column_widths(84, 2) == (18, 12, 7)
        assert calculate_column_widths(60, 2) == (14, 10, 6)

    def test_build_alert_tags(self):
        match = make_match(
            1,
            player1_discord_id="late-id",
            player2_discord_id="dq-id",
        )

        assert build_alert_tags(
            match,
            late_arrivals={"late-id"},
            dqs={"dq-id"},
        ) == ["[bold red]DQ[/bold red]", "[bold yellow]LATE[/bold yellow]"]

    def test_build_match_row_appends_alerts(self):
        match = make_match(
            1,
            state=2,
            updated_at=10,
            player1_discord_id="late-id",
        )

        row = build_match_row(
            match,
            late_arrivals={"late-id"},
            dqs=set(),
        )

        assert row[0].endswith("[bold yellow]LATE[/bold yellow]")
        assert row[1] == "[red]![/red] Ready"
        assert row[2] != "-"

    def test_build_match_row_greys_tbd_waiting_rows_more_strongly(self):
        match = make_match(
            1,
            player1="Alice",
            player2="TBD",
            state=1,
        )

        row = build_match_row(match, late_arrivals=set(), dqs=set())

        assert row[0].startswith("[dim bright_black]")
        assert "[dim bright_black]Waiting[/]" in row[1]
        assert row[2].startswith("[dim bright_black]")

    def test_build_match_table_separator_row(self):
        row = build_match_table_separator_row()

        assert row == ["-" * MATCH_TABLE_SEPARATOR_WIDTH] * 3
