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
