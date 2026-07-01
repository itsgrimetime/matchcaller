"""Stateful helpers for pool grid rendering and synchronization."""

from dataclasses import dataclass
import re
from typing import Callable, Sequence

from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Static

from ..api.jsonbin_api import AlertData
from ..models import MatchRow
from .presentation import (
    MATCH_TABLE_SEPARATOR_KEY,
    build_match_row,
    build_match_table_separator_row,
    calculate_column_widths,
    calculate_num_columns,
    calculate_single_pool_lanes,
    group_matches_by_pool,
    sort_pool_matches,
    sort_pool_names,
    split_matches_into_lanes,
)


@dataclass(frozen=True)
class PoolGridSectionPlan:
    """One rendered table section within the pool grid."""

    pool_name: str
    title: str
    section_id: str
    matches: tuple[MatchRow, ...]
    column_index: int
    lane_index: int


@dataclass(frozen=True)
class PoolGridPlan:
    """Planned pool grid update for the current match set and terminal width."""

    pools: dict[str, list[MatchRow]]
    sorted_pools: list[str]
    sections: tuple[PoolGridSectionPlan, ...]
    num_columns: int
    column_widths: tuple[int, int, int]
    layout_signature: tuple[int, int, int, int]
    structure_changed: bool
    layout_changed: bool
    dom_in_sync: bool
    rebuild_needed: bool


class PoolGridManager:
    """Own Textual-specific pool grid layout and table synchronization."""

    def __init__(self) -> None:
        self.current_pool_names: set[str] = set()
        self.current_layout_signature: tuple[int, int, int, int] | None = None
        self.current_sections: tuple[PoolGridSectionPlan, ...] = ()
        self.rebuild_counter: int = 0

    @staticmethod
    def pool_id(pool_name: str) -> str:
        """Generate a stable DOM element ID for a pool name."""
        normalized = (pool_name or "unknown").lower()
        slug = re.sub(r"[^a-z0-9_-]+", "-", normalized)
        slug = re.sub(r"-{2,}", "-", slug).strip("-")
        return f"pool-{slug or 'unknown'}"

    @classmethod
    def section_id(cls, pool_name: str, lane_index: int) -> str:
        """Generate a stable DOM element ID for a rendered pool lane."""
        base_id = cls.pool_id(pool_name)
        if lane_index == 0:
            return base_id
        return f"{base_id}--{lane_index + 1}"

    @staticmethod
    def layout_signature(
        num_columns: int,
        column_widths: tuple[int, int, int],
    ) -> tuple[int, int, int, int]:
        """Capture the current pool layout in a stable comparable form."""
        return (num_columns, *column_widths)

    def reset(self) -> None:
        """Reset tracked layout state so the next update rebuilds the grid."""
        self.current_pool_names = set()
        self.current_layout_signature = None
        self.current_sections = ()

    def plan(
        self,
        matches: Sequence[MatchRow],
        *,
        container_width: int,
        dom_has_pool: Callable[[str], bool],
        dom_has_section: Callable[[str], bool] | None = None,
    ) -> PoolGridPlan:
        """Build a pool grid plan from the current matches and DOM state."""
        pools = group_matches_by_pool(matches)
        new_pool_names = set(pools.keys())
        sorted_pools = sort_pool_names(pools.keys())
        num_columns = calculate_num_columns(
            len(sorted_pools),
            total_matches=len(matches),
            container_width=container_width,
        )
        column_widths = calculate_column_widths(container_width, num_columns)
        layout_signature = self.layout_signature(num_columns, column_widths)
        sections = self._build_sections(
            pools,
            sorted_pools,
            num_columns=num_columns,
            container_width=container_width,
            total_matches=len(matches),
        )
        if dom_has_section is None:
            dom_in_sync = all(dom_has_pool(pool_name) for pool_name in new_pool_names)
        else:
            dom_in_sync = all(
                dom_has_section(section.section_id) for section in sections
            )
        structure_changed = new_pool_names != self.current_pool_names or not dom_in_sync
        layout_changed = layout_signature != self.current_layout_signature

        return PoolGridPlan(
            pools={
                pool_name: list(pool_matches)
                for pool_name, pool_matches in pools.items()
            },
            sorted_pools=sorted_pools,
            sections=sections,
            num_columns=num_columns,
            column_widths=column_widths,
            layout_signature=layout_signature,
            structure_changed=structure_changed,
            layout_changed=layout_changed,
            dom_in_sync=dom_in_sync,
            rebuild_needed=structure_changed or layout_changed,
        )

    def _build_sections(
        self,
        pools: dict[str, list[MatchRow]],
        sorted_pools: Sequence[str],
        *,
        num_columns: int,
        container_width: int,
        total_matches: int,
    ) -> tuple[PoolGridSectionPlan, ...]:
        """Build concrete table sections from pool data and layout rules."""
        sections: list[PoolGridSectionPlan] = []
        single_pool_lane_count = calculate_single_pool_lanes(
            num_pools=len(sorted_pools),
            total_matches=total_matches,
            container_width=container_width,
        )

        for pool_index, pool_name in enumerate(sorted_pools):
            sorted_matches = sort_pool_matches(pools[pool_name])
            lane_count = single_pool_lane_count if len(sorted_pools) == 1 else 1
            lanes = split_matches_into_lanes(sorted_matches, lane_count)

            for lane_index, lane_matches in enumerate(lanes):
                title = pool_name or "Unknown Pool"
                if len(lanes) > 1 and lane_index > 0:
                    title = f"{title} (cont.)"

                column_index = (
                    lane_index if len(sorted_pools) == 1 else pool_index % num_columns
                )
                sections.append(
                    PoolGridSectionPlan(
                        pool_name=pool_name,
                        title=title,
                        section_id=self.section_id(pool_name, lane_index),
                        matches=tuple(lane_matches),
                        column_index=column_index,
                        lane_index=lane_index,
                    )
                )

        return tuple(sections)

    def create_pool_table(
        self,
        column_widths: tuple[int, int, int],
        *,
        match_column_key: str,
        status_column_key: str,
        duration_column_key: str,
    ) -> DataTable[str]:
        """Create a pool table configured for stable updates on narrow terminals."""
        match_width, status_width, duration_width = column_widths
        pool_table: DataTable[str] = DataTable(classes="pool-table")
        pool_table.add_column("Match", key=match_column_key, width=match_width)
        pool_table.add_column("Status", key=status_column_key, width=status_width)
        pool_table.add_column("Duration", key=duration_column_key, width=duration_width)
        pool_table.cursor_type = "none"
        pool_table.cell_padding = 0
        return pool_table

    def sync_pool_table(
        self,
        pool_table: DataTable[str],
        matches: Sequence[MatchRow],
        alerts: AlertData,
        *,
        match_column_key: str,
        status_column_key: str,
        duration_column_key: str,
    ) -> None:
        """Update a table in place unless the row order has changed."""
        column_widths = (
            pool_table.columns[match_column_key].width,
            pool_table.columns[status_column_key].width,
            pool_table.columns[duration_column_key].width,
        )
        desired_rows = [
            (MATCH_TABLE_SEPARATOR_KEY, build_match_table_separator_row(column_widths)),
            *[
                (
                    str(match.id),
                    build_match_row(
                        match,
                        late_arrivals=alerts.late_arrivals,
                        dqs=alerts.dqs,
                    ),
                )
                for match in matches
            ],
        ]
        desired_keys = [row_key for row_key, _ in desired_rows]
        existing_keys = [row.key.value or "" for row in pool_table.ordered_rows]

        if existing_keys != desired_keys:
            pool_table.clear()
            for row_key, cells in desired_rows:
                pool_table.add_row(*cells, key=row_key)
            return

        for row_key, cells in desired_rows:
            pool_table.update_cell(row_key, match_column_key, cells[0])
            pool_table.update_cell(row_key, status_column_key, cells[1])
            pool_table.update_cell(row_key, duration_column_key, cells[2])

    async def replace_with_message(
        self,
        pools_container: Horizontal,
        *,
        title: str,
        body: str,
        message_id: str,
    ) -> None:
        """Replace the pool grid with a single message panel."""
        with pools_container.app.batch_update():
            await pools_container.remove_children()
            await pools_container.mount(
                Vertical(
                    Static(title, classes="pool-title"),
                    Static(body, id=message_id),
                    classes="pool-section",
                )
            )

    async def rebuild(
        self,
        pools_container: Horizontal,
        plan: PoolGridPlan,
        alerts: AlertData,
        *,
        match_column_key: str,
        status_column_key: str,
        duration_column_key: str,
        log_fn: Callable[[str], None],
    ) -> None:
        """Rebuild the pool grid layout from scratch."""
        with pools_container.app.batch_update():
            await pools_container.remove_children()

            self.rebuild_counter += 1
            columns = [
                Vertical(
                    classes="pool-column",
                    id=f"col-{self.rebuild_counter}-{index}",
                )
                for index in range(plan.num_columns)
            ]
            if columns:
                await pools_container.mount(*columns)

            sections_by_column: list[list[Vertical]] = [
                [] for _ in range(plan.num_columns)
            ]
            for section in plan.sections:
                pool_table = self.create_pool_table(
                    plan.column_widths,
                    match_column_key=match_column_key,
                    status_column_key=status_column_key,
                    duration_column_key=duration_column_key,
                )
                self.sync_pool_table(
                    pool_table,
                    section.matches,
                    alerts,
                    match_column_key=match_column_key,
                    status_column_key=status_column_key,
                    duration_column_key=duration_column_key,
                )

                sections_by_column[section.column_index].append(
                    Vertical(
                        Static(section.title, classes="pool-title"),
                        pool_table,
                        classes="pool-section",
                        id=section.section_id,
                    )
                )
                log_fn(
                    "🔄 Added pool section: "
                    f"{section.title} to column {section.column_index} "
                    f"with {len(section.matches)} matches"
                )

            for column, sections in zip(columns, sections_by_column):
                if sections:
                    await column.mount(*sections)

        self.current_pool_names = set(plan.sorted_pools)
        self.current_layout_signature = plan.layout_signature
        self.current_sections = plan.sections

    def sync_existing(
        self,
        pools_container: Horizontal,
        plan: PoolGridPlan,
        alerts: AlertData,
        *,
        match_column_key: str,
        status_column_key: str,
        duration_column_key: str,
        log_fn: Callable[[str], None],
    ) -> None:
        """Update existing pool tables in place without rebuilding the layout."""
        with pools_container.app.batch_update():
            for section in plan.sections:
                pool_section = pools_container.query_one(f"#{section.section_id}")
                pool_table = pool_section.query_one(DataTable)
                self.sync_pool_table(
                    pool_table,
                    section.matches,
                    alerts,
                    match_column_key=match_column_key,
                    status_column_key=status_column_key,
                    duration_column_key=duration_column_key,
                )
                log_fn(
                    "🔄 Updated existing pool section: "
                    f"{section.title} with {len(section.matches)} matches"
                )

        self.current_pool_names = set(plan.sorted_pools)
        self.current_layout_signature = plan.layout_signature
        self.current_sections = plan.sections

    def update_durations(
        self,
        pools_container: Horizontal,
        matches: Sequence[MatchRow],
        *,
        duration_column_key: str,
    ) -> None:
        """Update only the duration column for the current pool grid."""
        sections = self.current_sections
        if not sections:
            pools = group_matches_by_pool(matches)
            sections = tuple(
                PoolGridSectionPlan(
                    pool_name=pool_name,
                    title=pool_name or "Unknown Pool",
                    section_id=self.pool_id(pool_name),
                    matches=tuple(sort_pool_matches(pools[pool_name])),
                    column_index=0,
                    lane_index=0,
                )
                for pool_name in sort_pool_names(
                    key for key in pools.keys() if key is not None
                )
            )

        for section in sections:
            pool_section = pools_container.query_one(f"#{section.section_id}")
            pools_table = pool_section.query_one(DataTable)

            for match in section.matches:
                try:
                    pools_table.update_cell(
                        str(match.id),
                        duration_column_key,
                        match.time_since_ready,
                    )
                except Exception:
                    pass
