"""Main tournament display TUI application."""

import time
from dataclasses import replace
from typing import ClassVar

from textual.binding import BindingType

try:
    from textual import work
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal, ScrollableContainer, Vertical
    from textual.reactive import reactive
    from textual.widgets import Footer, Header, Static
except ImportError:
    raise ImportError(
        "Missing required dependencies. Please install with: pip install textual aiohttp"
    )

from ..api import TournamentAPI, TournamentDashboardAPI
from ..api.jsonbin_api import AlertData, JsonBinAPI
from ..models import MatchRow
from ..models.dashboard import DashboardState, ViewMode
from .dependencies import (
    AlertSource,
    DashboardDataSource,
    RefreshControllerFactory,
    TournamentDataSource,
)
from .dashboard_grid import DashboardGridManager
from .pool_grid import PoolGridManager
from .refresh_controller import (
    DisplaySnapshot,
    RefreshController,
    build_display_snapshot,
    build_error_timestamp,
)
from ..utils.logging import log, set_console_logging

from textual.theme import Theme

halloween_theme = Theme(
    name="halloween",
    primary="#ff6b35",
    secondary="#8b5cf6",
    accent="#10b981",
    foreground="#f5f5dc",
    background="#1a0f1f",
    success="#10b981",
    warning="#f59e0b",
    error="#dc2626",
    surface="#2d1b3d",
    panel="#3d2750",
    dark=True,
)

# Register in your App's on_mount method:
# def on_mount(self) -> None:
#     self.register_theme(halloween_theme)
#     self.theme = "halloween"


def _default_refresh_controller_factory(
    app: App[None],
    poll_interval: float,
) -> RefreshController:
    """Build the default refresh controller for the app."""
    return RefreshController(app, poll_interval=poll_interval)

class TournamentDisplay(App[None]):
    """Main tournament display application"""

    MATCH_COLUMN_KEY: ClassVar[str] = "match"
    STATUS_COLUMN_KEY: ClassVar[str] = "status"
    DURATION_COLUMN_KEY: ClassVar[str] = "duration"

    CSS: ClassVar[
        str
    ] = """
    Screen {
        layout: vertical;
    }

    Header {
        dock: top;
        height: 1;
        background: $primary;
        color: $text;
    }

    Footer {
        dock: bottom;
        height: 1;
        background: $primary-darken-1;
    }

    #main-container {
        height: 1fr;
        overflow-y: auto;
    }

    #pools-container {
        width: 1fr;
        height: 1fr;
    }

    .pool-column {
        width: 1fr;
        padding: 0 1;
        overflow-y: auto;
    }

    .pool-section {
        margin: 0 0 1 0;
        padding: 0;
        border: ascii $primary;
        height: auto;
        width: 1fr;
    }

    .pool-title {
        background: $primary;
        color: $text;
        padding: 0 1;
        text-align: center;
        height: 1;
    }

    .pool-table {
        height: auto;
        min-height: 3;
        border: none;
        margin: 0;
    }

    .highlight {
        background: $warning 20%;
    }

    .ready-row {
        background: $error 20%;
        color: $error-lighten-2;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        ("r", "refresh", "Refresh"),
        ("q", "quit", "Quit"),
    ]

    # Reactive variables
    event_name: reactive[str] = reactive("Loading...")
    total_sets: reactive[int] = reactive(0)
    ready_sets: reactive[int] = reactive(0)
    in_progress_sets: reactive[int] = reactive(0)
    last_update: reactive[str] = reactive("")

    def __init__(
        self,
        api_token: str | None = None,
        event_id: str | None = None,
        event_slug: str | None = None,
        poll_interval: float = 30.0,
        jsonbin_id: str | None = None,
        jsonbin_key: str | None = None,
        api: TournamentDataSource | None = None,
        alert_source: AlertSource | None = None,
        pool_grid: PoolGridManager | None = None,
        dashboard_grid: DashboardGridManager | None = None,
        refresh_controller_factory: RefreshControllerFactory | None = None,
        tournament_slug: str | None = None,
        view_mode: str | ViewMode = ViewMode.MAIN,
        dashboard_source: DashboardDataSource | None = None,
    ):
        super().__init__()
        self.view_mode = ViewMode(view_mode)
        self.tournament_slug = tournament_slug
        self.dashboard_state: DashboardState | None = None
        self.dashboard_source: DashboardDataSource | None = dashboard_source
        if (
            self.dashboard_source is None
            and self.view_mode != ViewMode.MAIN
            and api is None
            and api_token
        ):
            self.dashboard_source = TournamentDashboardAPI(
                api_token=api_token,
                event_id=event_id,
                event_slug=event_slug,
                tournament_slug=self.tournament_slug,
                requested_view=self.view_mode,
            )
        self.api: TournamentDataSource = api or TournamentAPI(
            api_token,
            event_id,
            event_slug,
        )
        controller_factory = (
            refresh_controller_factory or _default_refresh_controller_factory
        )
        self.refresh_controller: RefreshController = controller_factory(
            self,
            poll_interval,
        )
        self.pool_grid: PoolGridManager = pool_grid or PoolGridManager()
        self.dashboard_grid: DashboardGridManager = (
            dashboard_grid or DashboardGridManager()
        )
        self.matches: list[MatchRow] = []
        # Set initial title - will be updated when tournament data is loaded
        self.title = "Loading Tournament..."
        self.poll_interval: float = poll_interval

        # JsonBin alert integration
        self.alert_source: AlertSource | None = alert_source
        if self.alert_source is None and jsonbin_id:
            self.alert_source = JsonBinAPI(jsonbin_id, jsonbin_key)
        self.alerts: AlertData = AlertData({})

        log(
            "🎯 TournamentDisplay initialized with token: "
            f"{'***' + api_token[-4:] if api_token else 'None'}, "
            f"event: {event_id}, slug: {event_slug}, poll_interval: {poll_interval}, "
            f"jsonbin: {jsonbin_id or 'None'}, "
            f"api_source: {type(self.api).__name__}, "
            "dashboard_source: "
            f"{type(self.dashboard_source).__name__ if self.dashboard_source else 'None'}, "
            f"view_mode: {self.view_mode.value}, "
            f"tournament_slug: {self.tournament_slug or 'None'}, "
            f"alert_source: {type(self.alert_source).__name__ if self.alert_source else 'None'}"
        )

    def compose(self) -> ComposeResult:
        """Create the UI layout"""
        yield Header()
        yield ScrollableContainer(Horizontal(id="pools-container"), id="main-container")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the app"""
        # Disable console logging when TUI starts

        # self.register_theme(halloween_theme)
        # self.theme = "halloween"

        set_console_logging(False)

        log("🏁 on_mount() called")

        # Show loading state
        log("📡 Showing loading state...")
        self.show_loading_state()

        self.refresh_controller.start(
            update_display=self.update_display,
            fetch_tournament_data=self.fetch_tournament_data,
            fetch_alerts=self.fetch_alerts if self.alert_source else None,
        )

        log("🚀 Starting initial data fetch...")
        # Initial fetch - run immediately
        self.fetch_tournament_data()
        log("🚀 Initial fetch started")

    def show_loading_state(self) -> None:
        """Show loading message while fetching data"""
        self.event_name = "Fetching tournament data from start.gg..."
        self.matches = []
        self.total_sets = 0
        self.ready_sets = 0
        self.in_progress_sets = 0
        self.last_update = "Loading..."
        self.dashboard_state = None
        self.pool_grid.reset()

        self._replace_pools_with_message(
            "Fetching tournament data from start.gg...",
            "Please wait while we load match information.",
            message_id="loading-message",
        )

    def _get_pools_container(self) -> Horizontal:
        """Return the pools container widget."""
        container = self.query_one("#main-container", ScrollableContainer)
        return container.query_one("#pools-container", Horizontal)

    def _apply_snapshot(self, snapshot: DisplaySnapshot) -> None:
        """Apply a prepared display snapshot to the app state."""
        self.event_name = snapshot.event_name
        self.title = snapshot.title
        self.matches = snapshot.matches
        self.total_sets = snapshot.total_sets
        self.ready_sets = snapshot.ready_sets
        self.in_progress_sets = snapshot.in_progress_sets
        self.last_update = snapshot.last_update

    def _replace_pools_with_message(
        self,
        title: str,
        body: str,
        *,
        message_id: str,
    ) -> None:
        """Swap the pool grid for a single message panel."""
        try:
            pools_container = self._get_pools_container()
            with self.batch_update():
                pools_container.remove_children()
                pools_container.mount(
                    Vertical(
                        Static(title, classes="pool-title"),
                        Static(body, id=message_id),
                        classes="pool-section",
                    )
                )
        except Exception as e:
            log(f"⚠️ Could not replace pools content: {e}")

    def load_mock_data(self) -> None:
        """Load mock data to test the UI"""
        from ..models.mock_data import MOCK_TOURNAMENT_DATA

        log("🧪 Loading mock data for testing...")
        data = MOCK_TOURNAMENT_DATA
        snapshot = replace(build_display_snapshot(data), last_update="Mock Data")
        self._apply_snapshot(snapshot)
        self.update_table()
        log("✅ Mock data loaded successfully")

    @work(exclusive=True)
    async def fetch_tournament_data(self) -> None:
        """Fetch tournament data from API (async worker)"""
        log("🔄 fetch_tournament_data() STARTED")
        try:
            if self.dashboard_source is not None:
                dashboard = await self.dashboard_source.fetch_dashboard_state(
                    previous_state=self.dashboard_state,
                )
                self.dashboard_state = dashboard
                if dashboard.main is None:
                    raise Exception("Dashboard state did not include main tournament data")
                snapshot = build_display_snapshot(dashboard.main)
                snapshot = replace(snapshot, last_update=dashboard.last_update)
                self._apply_snapshot(snapshot)
                self.update_table()
                return

            log("🔄 About to call api.fetch_sets()...")
            data = await self.api.fetch_sets()
            log(
                "🔄 api.fetch_sets() returned: "
                f"{type(data)} with keys: "
                f"{list(data.keys()) if isinstance(data, dict) else 'not a dict'}"
            )
            snapshot = build_display_snapshot(data)
            self._apply_snapshot(snapshot)
            log(f"🔄 Event name set to: {self.event_name}")
            log(f"🔄 Tournament title set to: {self.title}")
            log(f"🔄 Created {len(self.matches)} match objects")

            log(
                f"🔄 Stats: total={self.total_sets}, ready={self.ready_sets}, in_progress={self.in_progress_sets}"
            )

            # Update table directly since we're in the main thread
            log("🔄 About to call update_table()...")
            self.update_table()
            log(
                f"✅ Data updated: {self.total_sets} total, {self.ready_sets} ready, {self.in_progress_sets} in progress"
            )

        except Exception as e:
            log(f"❌ Exception in fetch_tournament_data: {type(e).__name__}: {e}")
            import traceback

            log(f"❌ Full traceback: {traceback.format_exc()}")
            # Keep existing data, just update timestamp to show we tried
            self.last_update = build_error_timestamp()
            # Don't clear the display or change data - keep showing last successful state

    @work(exclusive=True, group="alerts")
    async def fetch_alerts(self) -> None:
        """Fetch late arrival / DQ alerts from jsonbin."""
        if not self.alert_source:
            return
        try:
            new_alerts = await self.alert_source.fetch_alerts()
            changed = (
                new_alerts.late_arrivals != self.alerts.late_arrivals
                or new_alerts.dqs != self.alerts.dqs
            )
            self.alerts = new_alerts
            if changed:
                log(
                    f"🔔 Alerts updated: {len(self.alerts.late_arrivals)} late, "
                    f"{len(self.alerts.dqs)} DQs"
                )
                self.update_table()
        except Exception as e:
            log(f"❌ Alert fetch error: {type(e).__name__}: {e}")

    def rebuild_table(
        self,
        plan,
    ) -> None:
        """Schedule a full pool layout rebuild."""
        self.refresh_controller.begin_ui_mutation()
        self.run_worker(
            self._rebuild_table_async(plan),
            group="ui",
            exclusive=True,
            exit_on_error=False,
        )

    async def _rebuild_table_async(
        self,
        plan,
    ) -> None:
        """Rebuild the pool layout after awaiting DOM removal/mount operations."""
        try:
            pools_container = self._get_pools_container()
            await self.pool_grid.rebuild(
                pools_container,
                plan,
                self.alerts,
                match_column_key=self.MATCH_COLUMN_KEY,
                status_column_key=self.STATUS_COLUMN_KEY,
                duration_column_key=self.DURATION_COLUMN_KEY,
                log_fn=log,
            )
            child_count = len(pools_container.children)
            log(
                f"✅ Rebuild complete: {child_count} DOM children, pools: {plan.sorted_pools}"
            )
            if child_count == 0:
                log("❌ Rebuild produced empty DOM!")
        except Exception as e:
            log(f"❌ Error during rebuild_table: {e}")
            self.pool_grid.reset()
            try:
                pools_container = self._get_pools_container()
                await self.pool_grid.replace_with_message(
                    pools_container,
                    title="Error updating display",
                    body=f"Rebuild failed: {str(e)[:50]}...",
                    message_id="error-message",
                )
            except Exception as fallback_error:
                log(f"❌ Fallback error display also failed: {fallback_error}")
        finally:
            self.refresh_controller.finish_ui_mutation(flush_update=self.update_table)

    def rebuild_dashboard(self) -> None:
        if self.dashboard_state is None:
            return
        self.refresh_controller.begin_ui_mutation()
        self.run_worker(
            self._rebuild_dashboard_async(self.dashboard_state),
            group="ui",
            exclusive=True,
            exit_on_error=False,
        )

    async def _rebuild_dashboard_async(self, dashboard: DashboardState) -> None:
        try:
            pools_container = self._get_pools_container()
            await self.dashboard_grid.rebuild(pools_container, dashboard, self.alerts)
        except Exception as e:
            log(f"❌ Error during rebuild_dashboard: {e}")
            self.pool_grid.reset()
        finally:
            self.refresh_controller.finish_ui_mutation(flush_update=self.update_table)

    def update_table(self) -> None:
        """Update the matches display with vertical pool columns"""
        log(f"🔄 update_table() called with {len(self.matches)} matches")

        if self.refresh_controller.ui_busy:
            self.refresh_controller.mark_ui_update_pending("update_table", log_fn=log)
            return

        pools_container = self._get_pools_container()

        if (
            self.dashboard_state is not None
            and self.dashboard_state.resolved_view != ViewMode.MAIN
        ):
            self.rebuild_dashboard()
            return

        if not self.matches:
            log("⚠️  No matches to display")
            self.pool_grid.reset()
            if not pools_container.query("#no-matches"):
                self._replace_pools_with_message(
                    "No matches found",
                    "No active matches at this time.",
                    message_id="no-matches",
                )
            return

        container_width = pools_container.size.width or self.size.width or 80
        plan = self.pool_grid.plan(
            self.matches,
            container_width=container_width,
            dom_has_pool=lambda pool_name: bool(
                pools_container.query(f"#{self.pool_grid.pool_id(pool_name)}")
            ),
        )

        log(f"🔄 Found {len(plan.pools)} pools: {list(plan.pools.keys())}")

        if not plan.dom_in_sync and set(plan.pools.keys()) == self.pool_grid.current_pool_names:
            log("🔧 DOM out of sync with pool names, forcing rebuild")

        log(
            f"🔄 Organizing {len(plan.sorted_pools)} pools into {plan.num_columns} columns"
        )

        if plan.rebuild_needed:
            if plan.layout_changed and self.pool_grid.current_layout_signature is not None:
                log("🔧 Layout width changed, forcing rebuild")
            log("🔄 Pool structure changed, rebuilding columns")
            self.rebuild_table(plan)
            return

        log("🔄 Pool structure unchanged, updating existing tables")

        # Update existing pool tables in-place (no DOM teardown)
        updated_in_place = False
        self.refresh_controller.begin_ui_mutation()
        try:
            self.pool_grid.sync_existing(
                pools_container,
                plan,
                self.alerts,
                match_column_key=self.MATCH_COLUMN_KEY,
                status_column_key=self.STATUS_COLUMN_KEY,
                duration_column_key=self.DURATION_COLUMN_KEY,
                log_fn=log,
            )
            updated_in_place = True
        except Exception as e:
            log(
                f"⚠️ Could not update pool layout in place: {e} — queuing rebuild"
            )
            self.pool_grid.reset()
            self.refresh_controller.mark_ui_update_pending("pool update failed", log_fn=log)
        finally:
            self.refresh_controller.finish_ui_mutation(flush_update=self.update_table)

        if updated_in_place:
            log("✅ Table updated successfully with separate pool sections")

    def update_display(self) -> None:
        """Update time-dependent displays (called every second)"""
        if not self.matches or self.refresh_controller.ui_busy:
            return

        if (
            self.dashboard_state is not None
            and self.dashboard_state.resolved_view != ViewMode.MAIN
        ):
            return

        # Update duration timers every second by updating just the duration column
        try:
            pools_container = self._get_pools_container()

            # Periodic health check: verify DOM has content
            now_sec = int(time.time())
            if now_sec % 30 == 0:
                child_count = len(pools_container.children)
                log(
                    f"📊 Health: {len(self.matches)} matches, "
                    f"{len(self.pool_grid.current_pool_names)} tracked pools, "
                    f"{child_count} DOM children"
                )
                if child_count == 0 and self.matches:
                    log("🔧 Health check: DOM empty but matches exist, forcing rebuild")
                    self.pool_grid.reset()
                    self.update_table()
                    return

            self.pool_grid.update_durations(
                pools_container,
                self.matches,
                duration_column_key=self.DURATION_COLUMN_KEY,
            )

        except Exception as e:
            log(f"⚠️ Could not update display: {e}")
            self.pool_grid.reset()

    def action_refresh(self) -> None:
        """Manually refresh data while preserving the current layout when possible."""
        log("🔄 Manual refresh triggered")
        self.refresh_controller.refresh_now(fetch_tournament_data=self.fetch_tournament_data)

    def on_unmount(self) -> None:
        """Clean up when app is unmounted"""
        self._cleanup_terminal()

    def _cleanup_terminal(self) -> None:
        """Ensure terminal state is properly restored"""
        try:
            # Force disable mouse tracking and restore cursor
            import sys

            sys.stdout.write(
                "\033[?1000l\033[?1003l\033[?1015l\033[?1006l\033[?25h\033[?1004l"
            )
            sys.stdout.flush()
        except Exception:
            pass

    async def action_quit(self):
        """Quit the application"""
        self._cleanup_terminal()
        self.exit()
