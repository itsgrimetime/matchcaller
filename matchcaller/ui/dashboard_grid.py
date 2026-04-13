"""Textual helpers for split and ladder dashboard rendering."""

from typing import Sequence

from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Static

from ..api.jsonbin_api import AlertData
from ..models.dashboard import (
    DashboardState,
    LadderState,
    StationState,
    ViewMode,
    filter_late_bracket_matches,
)
from ..models.match import MatchRow
from .presentation import build_match_row, sort_pool_matches


def build_station_summary(stations: StationState | None) -> str:
    if stations is None:
        return "Stations unavailable"
    free = ", ".join(str(number) for number in stations.available_numbers) or "-"
    busy = ", ".join(str(number) for number in sorted(stations.occupied_numbers)) or "-"
    return f"Free: {free} | Busy: {busy}"


def build_ladder_rows(matches: Sequence[MatchRow]) -> list[list[str]]:
    return [
        build_match_row(match, late_arrivals=set(), dqs=set())
        for match in sort_pool_matches(matches)
    ]


def build_standings_rows(ladder: LadderState | None) -> list[list[str]]:
    if ladder is None:
        return []
    return [
        [f"#{standing.placement}", standing.entrant_name, standing.record_text]
        for standing in ladder.standings[:10]
    ]


class DashboardGridManager:
    """Own dashboard-specific Textual layout rendering."""

    def reset(self) -> None:
        """Dashboard renderer has no persistent structure cache yet."""
        pass

    async def rebuild(
        self,
        container: Horizontal,
        dashboard: DashboardState,
        alerts: AlertData,
    ) -> None:
        with container.app.batch_update():
            await container.remove_children()
            await container.mount(self._build_dashboard(dashboard, alerts))

    def _build_dashboard(
        self,
        dashboard: DashboardState,
        alerts: AlertData,
    ) -> Horizontal | Vertical:
        if dashboard.resolved_view == ViewMode.LADDER:
            return self._build_ladder_only(dashboard)
        return self._build_split(dashboard, alerts)

    def _build_split(self, dashboard: DashboardState, alerts: AlertData) -> Horizontal:
        main_table = self._match_table(
            "main-dashboard-table",
            [
                build_match_row(
                    match,
                    late_arrivals=alerts.late_arrivals,
                    dqs=alerts.dqs,
                )
                for match in filter_late_bracket_matches(
                    [
                        MatchRow(set_data)
                        for set_data in (dashboard.main.sets if dashboard.main else [])
                    ]
                )
            ],
        )
        ladder_table = self._match_table(
            "ladder-dashboard-table",
            build_ladder_rows(
                [
                    MatchRow(set_data)
                    for set_data in (dashboard.ladder.sets if dashboard.ladder else [])
                ]
            ),
        )
        standings_table = self._standings_table(dashboard.ladder)
        return Horizontal(
            Vertical(
                Static("Main Bracket", classes="pool-title"),
                main_table,
                classes="pool-column",
            ),
            Vertical(
                Static(_ladder_title(dashboard.ladder), classes="pool-title"),
                Static(build_station_summary(dashboard.stations), id="station-summary"),
                ladder_table,
                standings_table,
                classes="pool-column",
            ),
            id="dashboard-container",
        )

    def _build_ladder_only(self, dashboard: DashboardState) -> Vertical:
        ladder_table = self._match_table(
            "ladder-dashboard-table",
            build_ladder_rows(
                [
                    MatchRow(set_data)
                    for set_data in (dashboard.ladder.sets if dashboard.ladder else [])
                ]
            ),
        )
        return Vertical(
            Static(_ladder_title(dashboard.ladder), classes="pool-title"),
            Static(build_station_summary(dashboard.stations), id="station-summary"),
            ladder_table,
            self._standings_table(dashboard.ladder),
            id="dashboard-container",
        )

    def _match_table(
        self,
        table_id: str,
        rows: Sequence[Sequence[str]],
    ) -> DataTable[str]:
        table: DataTable[str] = DataTable(id=table_id, classes="pool-table")
        table.add_column("Match", key="match", width=26)
        table.add_column("Status", key="status", width=16)
        table.add_column("Time", key="duration", width=10)
        table.cursor_type = "none"
        table.cell_padding = 0
        if rows:
            for index, row in enumerate(rows):
                table.add_row(*row, key=str(index))
        else:
            table.add_row("No matches", "-", "-", key="empty")
        return table

    def _standings_table(self, ladder: LadderState | None) -> DataTable[str]:
        table: DataTable[str] = DataTable(
            id="ladder-standings-table",
            classes="pool-table",
        )
        table.add_column("Rank", key="rank", width=6)
        table.add_column("Player", key="player", width=18)
        table.add_column("Record", key="record", width=8)
        table.cursor_type = "none"
        table.cell_padding = 0
        rows = build_standings_rows(ladder)
        if rows:
            for index, row in enumerate(rows):
                table.add_row(*row, key=str(index))
        else:
            table.add_row("-", "No standings", "-", key="empty")
        return table


def _ladder_title(ladder: LadderState | None) -> str:
    if ladder is None:
        return "Ladder"
    if ladder.event_name:
        return ladder.event_name
    return ladder.waiting_reason or "Ladder"
