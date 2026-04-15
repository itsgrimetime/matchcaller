"""Pure presentation helpers for tournament display layout and rows."""

from collections import defaultdict
from typing import Iterable, Sequence

from ..models import MatchRow

ColumnWidths = tuple[int, int, int]

MATCH_TABLE_SEPARATOR_KEY = "__match_table_separator__"
MATCH_TABLE_SEPARATOR_WIDTH = 80


def group_matches_by_pool(matches: Sequence[MatchRow]) -> dict[str, list[MatchRow]]:
    """Group matches by pool name."""
    pools: defaultdict[str, list[MatchRow]] = defaultdict(list)
    for match in matches:
        pools[match.pool].append(match)
    return dict(pools)


def sort_pool_names(pool_names: Iterable[str]) -> list[str]:
    """Sort pool names for stable display ordering."""
    return sorted(pool_names)


def sort_pool_matches(pool_matches: Sequence[MatchRow]) -> list[MatchRow]:
    """Sort matches within a pool: known-player matches first, then TBD."""
    return sorted(
        pool_matches,
        key=lambda match: (
            match.has_tbd_player,
            match.sort_priority,
            -(match.updated_at or 0),
        ),
    )


def calculate_num_columns(num_pools: int) -> int:
    """Pick the number of pool columns for the current number of pools."""
    if num_pools <= 1:
        return 1
    if num_pools <= 4:
        return 2
    if num_pools <= 6:
        return 3
    return 4


def calculate_column_widths(
    container_width: int,
    num_columns: int,
) -> ColumnWidths:
    """Fit table columns to the available terminal width."""
    column_width = max(24, container_width // max(1, num_columns) - 4)

    if column_width >= 50:
        return (26, 14, 10)
    if column_width >= 44:
        return (22, 14, 8)
    if column_width >= 38:
        return (18, 12, 7)
    return (14, 10, 6)


def build_alert_tags(
    match: MatchRow,
    *,
    late_arrivals: set[str],
    dqs: set[str],
) -> list[str]:
    """Build alert tags for a match from Discord-linked player IDs."""
    discord_ids = {match.player1_discord_id, match.player2_discord_id} - {None}
    tags: list[str] = []
    if discord_ids & dqs:
        tags.append("[bold red]DQ[/bold red]")
    if discord_ids & late_arrivals:
        tags.append("[bold yellow]LATE[/bold yellow]")
    return tags


def build_match_row(
    match: MatchRow,
    *,
    late_arrivals: set[str],
    dqs: set[str],
) -> list[str]:
    """Build the display row for a match."""
    name = match.match_name
    tags = build_alert_tags(
        match,
        late_arrivals=late_arrivals,
        dqs=dqs,
    )
    if tags:
        name = f"{name} {' '.join(tags)}"

    return [
        name,
        f"{match.status_icon} {match.status_text}",
        match.time_since_ready,
    ]


def build_match_table_separator_row() -> list[str]:
    """Build a visual divider row between table headers and match rows."""
    cell = "-" * MATCH_TABLE_SEPARATOR_WIDTH
    return [cell, cell, cell]
