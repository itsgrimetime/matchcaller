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
from .presentation import build_match_row, calculate_column_widths, sort_pool_matches

DashboardMatchWidths = tuple[int, int, int]


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


def calculate_dashboard_match_widths(
    *,
    container_width: int,
    split_tables: int,
) -> DashboardMatchWidths:
    return calculate_column_widths(container_width, split_tables)


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
        split_tables = 2 if dashboard.resolved_view == ViewMode.SPLIT else 1
        column_widths = calculate_dashboard_match_widths(
            container_width=container.size.width or 80,
            split_tables=split_tables,
        )
        with container.app.batch_update():
            await container.remove_children()
            await container.mount(
                self._build_dashboard(dashboard, alerts, column_widths)
            )

    def _build_dashboard(
        self,
        dashboard: DashboardState,
        alerts: AlertData,
        column_widths: DashboardMatchWidths,
    ) -> Horizontal | Vertical:
        if dashboard.resolved_view == ViewMode.LADDER:
            return self._build_ladder_only(dashboard, column_widths)
        return self._build_split(dashboard, alerts, column_widths)

    def _build_split(
        self,
        dashboard: DashboardState,
        alerts: AlertData,
        column_widths: DashboardMatchWidths,
    ) -> Horizontal:
        main_matches = _main_dashboard_matches(dashboard)
        ladder_matches = _ladder_dashboard_matches(dashboard)
        main_table = self._match_table(
            "main-dashboard-table",
            [
                build_match_row(
                    match,
                    late_arrivals=alerts.late_arrivals,
                    dqs=alerts.dqs,
                )
                for match in main_matches
            ],
            column_widths,
        )
        ladder_table = self._match_table(
            "ladder-dashboard-table",
            build_ladder_rows(ladder_matches),
            column_widths,
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

    def _build_ladder_only(
        self,
        dashboard: DashboardState,
        column_widths: DashboardMatchWidths,
    ) -> Vertical:
        ladder_matches = _ladder_dashboard_matches(dashboard)
        ladder_table = self._match_table(
            "ladder-dashboard-table",
            build_ladder_rows(ladder_matches),
            column_widths,
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
        column_widths: DashboardMatchWidths,
    ) -> DataTable[str]:
        match_width, status_width, duration_width = column_widths
        table: DataTable[str] = DataTable(id=table_id, classes="pool-table")
        table.add_column("Match", key="match", width=match_width)
        table.add_column("Status", key="status", width=status_width)
        table.add_column("Time", key="duration", width=duration_width)
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

    def update_durations(
        self,
        container: Horizontal,
        dashboard: DashboardState,
    ) -> None:
        """Update only dashboard match-table duration cells."""
        if dashboard.resolved_view == ViewMode.SPLIT:
            self._update_table_durations(
                container,
                "#main-dashboard-table",
                _main_dashboard_matches(dashboard),
            )
            self._update_table_durations(
                container,
                "#ladder-dashboard-table",
                _ladder_dashboard_matches(dashboard),
            )
        elif dashboard.resolved_view == ViewMode.LADDER:
            self._update_table_durations(
                container,
                "#ladder-dashboard-table",
                _ladder_dashboard_matches(dashboard),
            )

    def _update_table_durations(
        self,
        container: Horizontal,
        table_selector: str,
        matches: Sequence[MatchRow],
    ) -> None:
        try:
            table = container.query_one(table_selector, DataTable)
        except Exception:
            return

        for index, match in enumerate(matches):
            try:
                table.update_cell(str(index), "duration", match.time_since_ready)
            except Exception:
                pass


def _ladder_title(ladder: LadderState | None) -> str:
    if ladder is None:
        return "Ladder"
    if ladder.event_name:
        return ladder.event_name
    return ladder.waiting_reason or "Ladder"


def _main_dashboard_matches(dashboard: DashboardState) -> list[MatchRow]:
    if dashboard.main is None:
        return []
    return filter_late_bracket_matches(
        [MatchRow(set_data) for set_data in dashboard.main.sets]
    )


def _ladder_dashboard_matches(dashboard: DashboardState) -> list[MatchRow]:
    if dashboard.ladder is None:
        return []
    return sort_pool_matches([MatchRow(set_data) for set_data in dashboard.ladder.sets])
