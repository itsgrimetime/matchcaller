"""Build a full-width match call board for round-robin events."""

from collections import Counter
from collections.abc import Sequence

from rich.console import Group
from rich.table import Table
from rich.text import Text

from ..api.jsonbin_api import AlertData
from ..models.match import MatchRow, MatchState
from .presentation import build_alert_tags


def uses_call_board(matches: Sequence[MatchRow], *, finals_pending: bool) -> bool:
    """Select the call board for round robin and the elimination stage it feeds."""
    return finals_pending or any(
        match.is_round_robin or match.is_seeded_elimination for match in matches
    )


def build_call_board(
    matches: Sequence[MatchRow],
    alerts: AlertData,
    *,
    finals_pending: bool,
) -> Group:
    """Show actionable sets, one upcoming set per pool, and the stage handoff."""
    pool_counts = Counter(_pool_name(match) for match in matches if match.is_round_robin)
    has_finals = any(match.is_seeded_elimination and not match.has_tbd_player for match in matches)
    if pool_counts:
        stage = "ROUND ROBIN + FINALS" if has_finals else "ROUND ROBIN"
    else:
        stage = "DOUBLE-ELIMINATION FINALS"

    summary = Text()
    summary.append(stage, style="bold")
    for pool, count in sorted(pool_counts.items()):
        sets_label = "set" if count == 1 else "sets"
        summary.append(f"    {pool} · {count} {sets_label} left")

    assigned = [match for match in matches if not match.has_tbd_player]
    playing = sorted(
        (match for match in assigned if match.is_in_progress),
        key=lambda match: (match.station is None, match.station or 0),
    )
    ready = [match for match in assigned if match.is_ready]
    next_by_pool: dict[str, MatchRow] = {}
    waiting = [match for match in assigned if match.effective_state == MatchState.WAITING]
    for match in sorted(
        waiting, key=lambda match: (match.round_number or 0) if match.is_round_robin else 0
    ):
        next_by_pool.setdefault(match.pool, match)

    up_next = list(next_by_pool.values())
    sections = [
        summary,
        Text(),
        Text(" PLAYING NOW ", style="bold black on bright_cyan"),
        _match_rows(playing, alerts) if playing else Text(" No sets in progress", style="dim"),
        Text(),
        Text(" READY TO CALL ", style="bold black on bright_yellow"),
        _match_rows(ready, alerts) if ready else Text(" No sets marked ready", style="dim"),
    ]
    if up_next:
        sections.extend([
            Text(),
            Text(" UP NEXT · WAITING ", style="bold"),
            _match_rows(up_next, alerts),
        ])
    if finals_pending:
        label = "NEXT STAGE  " if pool_counts else ""
        sections.extend([
            Text(),
            Text(f"{label}Double-elimination finals · awaiting seeds", style="bold"),
        ])
    return Group(*sections)


def _pool_name(match: MatchRow) -> str:
    return (match.pool_label or match.pool).removeprefix("Round Robin - ")


def _match_rows(matches: Sequence[MatchRow], alerts: AlertData) -> Table:
    table = Table.grid(expand=True, padding=(0, 1))
    table.add_column(width=18, style="bold cyan", overflow="fold")
    table.add_column(ratio=1, overflow="fold")
    table.add_column(max_width=28, justify="right", overflow="fold")
    for match in matches:
        location = ""
        if match.station is not None:
            location = f"Station {match.station}"
        elif match.stream:
            location = f"Stream {match.stream}"

        teams = Text(f"{match.player1}  vs  {match.player2}", style="bold" if match.is_ready else "")
        for tag in build_alert_tags(match, late_arrivals=alerts.late_arrivals, dqs=alerts.dqs):
            teams.append(" ")
            teams.append_text(Text.from_markup(tag))

        detail = _pool_name(match)
        if match.is_round_robin and match.round_number:
            detail = f"{detail} · R{match.round_number}"
        elif match.is_seeded_elimination:
            round_label = match.bracket.rsplit(" - ", 1)[-1]
            detail = f"Finals · {round_label}"
        table.add_row(Text(location), teams, Text(detail))
    return table
