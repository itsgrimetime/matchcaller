"""Main tournament display TUI application."""

import time
from collections import defaultdict
from datetime import datetime
from typing import ClassVar, cast

from textual.binding import BindingType

try:
    from textual import work
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal, ScrollableContainer, Vertical
    from textual.coordinate import Coordinate
    from textual.reactive import reactive
    from textual.widgets import DataTable, Footer, Header, Static
except ImportError:
    raise ImportError(
        "Missing required dependencies. Please install with: pip install textual aiohttp"
    )

from ..api import TournamentAPI
from ..api.jsonbin_api import AlertData, JsonBinAPI
from ..models import MatchRow, MatchState
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

class TournamentDisplay(App[None]):
    """Main tournament display application"""

    # Add a flag to prevent concurrent rebuilds
    _rebuilding: bool = False
    _current_pool_names: set[str] = set()

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
        border: solid $primary;
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
    ):
        super().__init__()
        self.api: TournamentAPI = TournamentAPI(api_token, event_id, event_slug)
        self.matches: list[MatchRow] = []
        # Set initial title - will be updated when tournament data is loaded
        self.title = "Loading Tournament..."
        self.poll_interval: float = poll_interval

        # JsonBin alert integration
        self.jsonbin_api: JsonBinAPI | None = None
        if jsonbin_id:
            self.jsonbin_api = JsonBinAPI(jsonbin_id, jsonbin_key)
        self.alerts: AlertData = AlertData({})

        log(
            "🎯 TournamentDisplay initialized with token: "
            f"{'***' + api_token[-4:] if api_token else 'None'}, "
            f"event: {event_id}, slug: {event_slug}, poll_interval: {poll_interval}, "
            f"jsonbin: {jsonbin_id or 'None'}"
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

        # Start periodic updates
        self.set_interval(1.0, self.update_display)  # Update every second
        self.set_interval(
            self.poll_interval, self.fetch_tournament_data
        )  # Fetch fresh data every 30 seconds

        # Poll jsonbin for alerts if configured
        if self.jsonbin_api:
            self.set_interval(15.0, self.fetch_alerts)  # Check alerts every 15s
            self.fetch_alerts()

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

        # Add a loading message to the pools container
        try:
            container = self.query_one("#main-container", ScrollableContainer)
            pools_container = container.query_one("#pools-container", Horizontal)
            pools_container.remove_children()  # Clear any existing content
            pools_container.mount(
                Vertical(
                    Static(
                        "🔄 Fetching tournament data from start.gg...",
                        classes="pool-title",
                    ),
                    Static(
                        "Please wait while we load match information.",
                        id="loading-message",
                    ),
                    classes="pool-section",
                )
            )
        except Exception as e:
            log(f"⚠️  Could not show loading state: {e}")

    def load_mock_data(self) -> None:
        """Load mock data to test the UI"""
        from ..models.mock_data import MOCK_TOURNAMENT_DATA

        log("🧪 Loading mock data for testing...")
        data = MOCK_TOURNAMENT_DATA
        self.event_name = data["event_name"]
        tournament_name = data.get("tournament_name", "Mock Tournament")
        self.title = f"{tournament_name} - {self.event_name}"  # Update the header title
        self.matches = [MatchRow(set_data) for set_data in data["sets"]]
        self.total_sets = len(self.matches)
        self.ready_sets = sum(1 for m in self.matches if m.state == MatchState.READY)
        self.in_progress_sets = sum(
            1 for m in self.matches if m.state == MatchState.IN_PROGRESS
        )
        self.last_update = "Mock Data"
        self.update_table()
        log("✅ Mock data loaded successfully")

    @work(exclusive=True)
    async def fetch_tournament_data(self) -> None:
        """Fetch tournament data from API (async worker)"""
        log("🔄 fetch_tournament_data() STARTED")
        try:
            log("🔄 About to call api.fetch_sets()...")
            data = await self.api.fetch_sets()
            log(
                "🔄 api.fetch_sets() returned: "
                f"{type(data)} with keys: "
                f"{list(data.keys()) if isinstance(data, dict) else 'not a dict'}"
            )

            self.event_name = data.event_name
            tournament_name = data.tournament_name
            self.title = (
                f"{tournament_name} - {self.event_name}"  # Update the header title
            )
            log(f"🔄 Event name set to: {self.event_name}")
            log(f"🔄 Tournament title set to: {self.title}")

            self.matches = [MatchRow(set_data) for set_data in data.sets]
            log(f"🔄 Created {len(self.matches)} match objects")

            self.total_sets = len(self.matches)
            self.ready_sets = sum(
                1
                for m in self.matches
                if m.state == MatchState.READY and not m.started_at
            )
            self.in_progress_sets = sum(
                1
                for m in self.matches
                if (
                    m.state == MatchState.IN_PROGRESS
                    or (m.state == MatchState.READY and m.started_at)
                )
            )
            self.last_update = datetime.now().strftime("%H:%M:%S")

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
            self.last_update = f"Error at {datetime.now().strftime('%H:%M:%S')}"
            # Don't clear the display or change data - keep showing last successful state

    @work(exclusive=True, group="alerts")
    async def fetch_alerts(self) -> None:
        """Fetch late arrival / DQ alerts from jsonbin."""
        if not self.jsonbin_api:
            return
        try:
            new_alerts = await self.jsonbin_api.fetch_alerts()
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

    @staticmethod
    def _pool_id(pool_name: str) -> str:
        """Generate a stable DOM element ID for a pool name."""
        return f"pool-{(pool_name or 'unknown').lower().replace(' ', '-')}"

    @staticmethod
    def _sort_pool_matches(pool_matches: list[MatchRow]) -> list[MatchRow]:
        """Sort matches within a pool: known-player matches first, then TBD."""
        return sorted(
            pool_matches,
            key=lambda m: (
                m.has_tbd_player,
                (
                    0
                    if (m.state == MatchState.READY and m.started_at)
                    else (
                        1
                        if m.state == MatchState.READY
                        else 2 if m.state == MatchState.IN_PROGRESS else 3
                    )
                ),
                -(m.updated_at or 0),
            ),
        )

    def _match_row_data(self, match: MatchRow) -> list[str]:
        """Build the row data list for a match."""
        name = match.match_name
        # Annotate players with late arrival / DQ alerts (matched by Discord ID)
        discord_ids = {match.player1_discord_id, match.player2_discord_id} - {None}
        tags: list[str] = []
        if discord_ids & self.alerts.dqs:
            tags.append("[bold red]DQ[/bold red]")
        if discord_ids & self.alerts.late_arrivals:
            tags.append("[bold yellow]LATE[/bold yellow]")
        if tags:
            name = f"{name} {' '.join(tags)}"

        return [
            name,
            f"{match.status_icon} {match.status_text}",
            match.time_since_ready,
        ]

    def rebuild_table(
        self,
        pools: defaultdict[str, list[MatchRow]],
        sorted_pools: list[str],
        num_columns: int,
        pools_container: Horizontal,
    ) -> None:
        # Ensure container is clear before rebuilding
        try:
            pools_container.remove_children()
        except Exception as e:
            log(f"⚠️ Warning during remove_children: {e}")

        # Create column containers with stable IDs
        columns: list[Vertical] = []
        for i in range(num_columns):
            new_column: Vertical = Vertical(classes="pool-column", id=f"column-{i}")
            columns.append(new_column)
            pools_container.mount(new_column)

        # Distribute pools across columns
        for i, pool_name in enumerate(sorted_pools):
            column_index = i % num_columns
            column: Vertical = columns[column_index]
            pool_matches: list[MatchRow] = pools[pool_name]
            pool_id = self._pool_id(pool_name)

            sorted_matches = self._sort_pool_matches(pool_matches)

            # Create a new DataTable for this pool
            pool_table: DataTable[str] = DataTable(classes="pool-table")
            pool_table.add_column("Match", width=26)
            pool_table.add_column("Status", width=14)
            pool_table.add_column("Duration", width=10)
            pool_table.cursor_type = "row"

            # Add matches to the pool table
            for match in sorted_matches:
                pool_table.add_row(*self._match_row_data(match), key=str(match.id))

            # Create pool section with title and table
            pool_section = Vertical(
                Static(pool_name or "Unknown Pool", classes="pool-title"),
                pool_table,
                classes="pool-section",
                id=pool_id,
            )

            column.mount(pool_section)
            log(
                f"🔄 Added pool section: {pool_name} to column {column_index} with {len(sorted_matches)} matches"
            )

        # Store pool names so we can detect real changes on next refresh
        self._current_pool_names = set(sorted_pools)

    def update_table(self) -> None:
        """Update the matches display with vertical pool columns"""
        log(f"🔄 update_table() called with {len(self.matches)} matches")
        
        # Prevent concurrent rebuilds
        if self._rebuilding:
            log("⚠️ Rebuild already in progress, skipping this update")
            return

        container = self.query_one("#main-container", ScrollableContainer)
        pools_container = container.query_one("#pools-container", Horizontal)

        if not self.matches:
            log("⚠️  No matches to display")
            self._current_pool_names = set()  # Reset so next update triggers rebuild
            # Only clear if we need to show "no matches"
            if not pools_container.query("#no-matches"):
                pools_container.remove_children()
                pools_container.mount(
                    Vertical(
                        Static("No matches found", classes="pool-title"),
                        Static("No active matches at this time.", id="no-matches"),
                        classes="pool-section",
                    )
                )
            return

        pools: defaultdict[str, list[MatchRow]] = defaultdict(list)
        for match in self.matches:
            pools[match.pool].append(match)

        log(f"🔄 Found {len(pools)} pools: {list(pools.keys())}")

        # Check if we need to rebuild the entire structure
        new_pool_names = set(pools.keys())

        # Verify DOM actually has the expected pool sections
        dom_in_sync = all(
            bool(pools_container.query(f"#{self._pool_id(p)}"))
            for p in new_pool_names
        )

        rebuild_needed = (
            new_pool_names != self._current_pool_names
            or not dom_in_sync
        )
        if not dom_in_sync and new_pool_names == self._current_pool_names:
            log("🔧 DOM out of sync with pool names, forcing rebuild")

        # Sort pools by name for consistent ordering
        sorted_pools: list[str] = sorted(key for key in pools.keys())

        # Calculate number of columns based on number of pools
        num_pools = len(sorted_pools)
        if num_pools == 1:
            num_columns = 1
        elif num_pools <= 4:
            num_columns = 2
        elif num_pools <= 6:
            num_columns = 3
        else:
            num_columns = 4

        log(f"🔄 Organizing {num_pools} pools into {num_columns} columns")

        if rebuild_needed:
            log("🔄 Pool structure changed, rebuilding columns")
            self._rebuilding = True
            try:
                self.rebuild_table(pools, sorted_pools, num_columns, pools_container)
            except Exception as e:
                log(f"❌ Error during rebuild_table: {e}")
                # If rebuild fails, try to clear and show error message
                try:
                    pools_container.remove_children()
                    pools_container.mount(
                        Vertical(
                            Static("Error updating display", classes="pool-title"),
                            Static(f"Rebuild failed: {str(e)[:50]}...", id="error-message"),
                            classes="pool-section",
                        )
                    )
                except Exception as fallback_error:
                    log(f"❌ Fallback error display also failed: {fallback_error}")
            finally:
                self._rebuilding = False
                log("✅ Table updated successfully with separate pool sections")
            return
        else:
            log("🔄 Pool structure unchanged, updating existing tables")

        # Update existing pool tables in-place (no DOM teardown)
        for pool_name in sorted_pools:
            pool_matches: list[MatchRow] = pools[pool_name]
            pool_id = self._pool_id(pool_name)
            sorted_matches = self._sort_pool_matches(pool_matches)

            try:
                pool_section = cast(Vertical, pools_container.query_one(f"#{pool_id}"))
                pool_table = pool_section.query_one(DataTable)
                pool_table.clear()

                for match in sorted_matches:
                    pool_table.add_row(*self._match_row_data(match), key=str(match.id))

                log(
                    f"🔄 Updated existing pool: {pool_name} with {len(sorted_matches)} matches"
                )
            except Exception as e:
                log(f"⚠️  Could not update pool {pool_name}: {e}")

        log("✅ Table updated successfully with separate pool sections")

    def update_display(self) -> None:
        """Update time-dependent displays (called every second)"""
        if not self.matches:
            return

        # Update duration timers every second by updating just the duration column
        try:
            container = self.query_one("#main-container", ScrollableContainer)

            # Group matches by pool to match the UI structure
            from collections import defaultdict

            pools: defaultdict[str, list[MatchRow]] = defaultdict(list)
            for match in self.matches:
                pools[match.pool].append(match)

            for pool_name in sorted(key for key in pools.keys() if key is not None):
                pool_matches: list[MatchRow] = pools[pool_name]
                pool_id = self._pool_id(pool_name)
                sorted_matches = self._sort_pool_matches(pool_matches)

                try:
                    pool_section = container.query_one(f"#{pool_id}")
                    pools_table = pool_section.query_one(DataTable)

                    # Update just the duration column (column 2) for each match
                    for i, match in enumerate(sorted_matches):
                        try:
                            pools_table.update_cell_at(
                                Coordinate(i, 2), match.time_since_ready
                            )
                        except Exception:
                            pass

                except Exception as e:
                    log(f"⚠️ Failed to query pool: {e}")
                    if int(time.time()) % 10 == 0:
                        self.update_table()
                        break

        except Exception as e:
            # Only print this error occasionally to avoid spam
            if int(time.time()) % 30 == 0:
                log(f"⚠️  Could not update display: {e}")

    def action_refresh(self) -> None:
        """Manually refresh data (forces full rebuild)"""
        log("🔄 Manual refresh triggered - forcing full rebuild")
        self._current_pool_names = set()  # Force rebuild on next update
        self.fetch_tournament_data()
        self.notify("Refreshing tournament data...")

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
