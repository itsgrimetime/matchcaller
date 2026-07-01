"""Unit tests for pool grid planning helpers."""

import pytest

from matchcaller.models.match import MatchData, MatchRow, PlayerData
from matchcaller.ui.pool_grid import PoolGridManager


def make_match(
    match_id: int,
    *,
    pool_name: str = "Pool A",
    state: int = 1,
    updated_at: int = 100,
    started_at: int | None = None,
) -> MatchRow:
    """Create a MatchRow for pool-grid planning tests."""
    return MatchRow(
        MatchData(
            id=match_id,
            displayName=f"Match {match_id}",
            player1=PlayerData(tag="Alice"),
            player2=PlayerData(tag="Bob"),
            state=state,
            updatedAt=updated_at,
            startedAt=started_at,
            poolName=pool_name,
        )
    )


@pytest.mark.unit
class TestPoolGridManager:
    """Test pool-grid planning state without a running Textual app."""

    def test_plan_detects_structure_changes(self):
        manager = PoolGridManager()
        plan = manager.plan(
            [make_match(1)],
            container_width=120,
            dom_has_pool=lambda _pool_name: False,
        )

        assert plan.rebuild_needed
        assert plan.structure_changed
        assert not plan.dom_in_sync
        assert plan.sorted_pools == ["Pool A"]

    def test_plan_splits_large_single_pool_across_two_lanes(self):
        manager = PoolGridManager()
        matches = [make_match(match_id) for match_id in range(1, 8)]

        plan = manager.plan(
            matches,
            container_width=120,
            dom_has_pool=lambda _pool_name: False,
            dom_has_section=lambda _section_id: False,
        )

        assert plan.num_columns == 2
        assert [section.title for section in plan.sections] == [
            "Pool A",
            "Pool A (cont.)",
        ]
        assert [section.section_id for section in plan.sections] == [
            "pool-pool-a",
            "pool-pool-a--2",
        ]
        assert [section.column_index for section in plan.sections] == [0, 1]
        section_match_ids = [
            [match.id for match in section.matches] for section in plan.sections
        ]
        assert section_match_ids == [
            [1, 2, 3, 4],
            [5, 6, 7],
        ]

    def test_plan_keeps_small_single_pool_in_one_lane(self):
        manager = PoolGridManager()

        plan = manager.plan(
            [make_match(match_id) for match_id in range(1, 5)],
            container_width=120,
            dom_has_pool=lambda _pool_name: False,
            dom_has_section=lambda _section_id: False,
        )

        assert plan.num_columns == 1
        assert [section.title for section in plan.sections] == ["Pool A"]
        assert [section.section_id for section in plan.sections] == ["pool-pool-a"]

    def test_plan_keeps_two_pools_as_two_pool_sections(self):
        manager = PoolGridManager()
        matches = [
            make_match(1, pool_name="Pool A"),
            make_match(2, pool_name="Pool A"),
            make_match(3, pool_name="Pool B"),
            make_match(4, pool_name="Pool B"),
            make_match(5, pool_name="Pool B"),
            make_match(6, pool_name="Pool B"),
        ]

        plan = manager.plan(
            matches,
            container_width=120,
            dom_has_pool=lambda _pool_name: False,
            dom_has_section=lambda _section_id: False,
        )

        assert plan.num_columns == 2
        assert [section.title for section in plan.sections] == ["Pool A", "Pool B"]
        assert [section.section_id for section in plan.sections] == [
            "pool-pool-a",
            "pool-pool-b",
        ]
        assert [section.column_index for section in plan.sections] == [0, 1]

    def test_pool_ids_are_safe_for_event_prefixed_pool_names(self):
        manager = PoolGridManager()

        assert manager.pool_id("Melee Singles! (7:30 Start) - Bracket - Pool A") == (
            "pool-melee-singles-7-30-start-bracket-pool-a"
        )

        plan = manager.plan(
            [
                make_match(
                    1,
                    pool_name="Melee Singles! (7:30 Start) - Bracket - Pool A",
                ),
                make_match(2, pool_name="Melee Doubles - Bracket - Pool A"),
            ],
            container_width=120,
            dom_has_pool=lambda _pool_name: False,
            dom_has_section=lambda _section_id: False,
        )

        assert [section.section_id for section in plan.sections] == [
            "pool-melee-doubles-bracket-pool-a",
            "pool-melee-singles-7-30-start-bracket-pool-a",
        ]

    def test_plan_detects_missing_split_lane_dom(self):
        manager = PoolGridManager()
        matches = [make_match(match_id) for match_id in range(1, 8)]
        initial_plan = manager.plan(
            matches,
            container_width=120,
            dom_has_pool=lambda _pool_name: True,
            dom_has_section=lambda _section_id: True,
        )
        manager.current_pool_names = {"Pool A"}
        manager.current_layout_signature = initial_plan.layout_signature

        plan = manager.plan(
            matches,
            container_width=120,
            dom_has_pool=lambda _pool_name: True,
            dom_has_section=lambda section_id: section_id == "pool-pool-a",
        )

        assert plan.rebuild_needed
        assert plan.structure_changed
        assert not plan.dom_in_sync
        assert not plan.layout_changed

    def test_plan_skips_rebuild_when_layout_and_dom_match(self):
        manager = PoolGridManager()
        initial_plan = manager.plan(
            [make_match(1)],
            container_width=120,
            dom_has_pool=lambda _pool_name: False,
        )
        manager.current_pool_names = {"Pool A"}
        manager.current_layout_signature = initial_plan.layout_signature

        stable_plan = manager.plan(
            [make_match(1)],
            container_width=120,
            dom_has_pool=lambda _pool_name: True,
        )

        assert not stable_plan.rebuild_needed
        assert not stable_plan.structure_changed
        assert not stable_plan.layout_changed

    def test_plan_detects_layout_width_changes(self):
        manager = PoolGridManager()
        manager.current_pool_names = {"Pool A"}
        manager.current_layout_signature = manager.layout_signature(1, (26, 14, 10))

        plan = manager.plan(
            [make_match(1)],
            container_width=24,
            dom_has_pool=lambda _pool_name: True,
        )

        assert plan.rebuild_needed
        assert not plan.structure_changed
        assert plan.layout_changed

    def test_reset_clears_layout_tracking(self):
        manager = PoolGridManager()
        manager.current_pool_names = {"Pool A"}
        manager.current_layout_signature = (1, 26, 14, 10)

        manager.reset()

        assert manager.current_pool_names == set()
        assert manager.current_layout_signature is None
        assert manager.current_sections == ()
