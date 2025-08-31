"""Main tournament display TUI application."""

import time
from datetime import datetime
from typing import Optional, cast

try:
    from textual import work
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal, ScrollableContainer, Vertical
    from textual.reactive import reactive
    from textual.widgets import DataTable, Footer, Header, Static
    from textual.coordinate import Coordinate
except ImportError:
    raise ImportError(
        "Missing required dependencies. Please install with: pip install textual aiohttp"
    )

from ..api import TournamentAPI
from ..models import MatchRow, MatchState
from ..models.match import TournamentData
from ..utils.logging import log, set_console_logging


class TournamentDisplay(App):
    """Main tournament display application"""

    CSS = """
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

    BINDINGS = [
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
        api_token: Optional[str] = None,
        event_id: Optional[str] = None,
        event_slug: Optional[str] = None,
    ):
        super().__init__()
        self.api: TournamentAPI = TournamentAPI(api_token, event_id, event_slug)
        self.matches: list[MatchRow] = []
        # Set initial title - will be updated when tournament data is loaded
        self.title = "Loading Tournament..."
        log(
            f"🎯 TournamentDisplay initialized with token: {'***' + api_token[-4:] if api_token else 'None'}, event: {event_id}, slug: {event_slug}"
        )

    def compose(self) -> ComposeResult:
        """Create the UI layout"""
        yield Header()
        yield ScrollableContainer(Horizontal(id="pools-container"), id="main-container")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the app"""
        # Disable console logging when TUI starts
        set_console_logging(False)
        
        log("🏁 on_mount() called")

        # Show loading state
        log("📡 Showing loading state...")
        self.show_loading_state()

        # Start periodic updates
        self.set_interval(1.0, self.update_display)  # Update every second
        self.set_interval(
            30.0, self.fetch_tournament_data
        )  # Fetch fresh data every 30 seconds

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
        self.in_progress_sets = sum(1 for m in self.matches if m.state == MatchState.IN_PROGRESS)
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
                f"🔄 api.fetch_sets() returned: {type(data)} with keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}"
            )

            self.event_name = cast(str, data["event_name"])
            tournament_name = data.get("tournament_name", "Unknown Tournament")
            self.title = (
                f"{tournament_name} - {self.event_name}"  # Update the header title
            )
            log(f"🔄 Event name set to: {self.event_name}")
            log(f"🔄 Tournament title set to: {self.title}")

            self.matches = [MatchRow(set_data) for set_data in data["sets"]]  # type: ignore
            log(f"🔄 Created {len(self.matches)} match objects")

            self.total_sets = len(self.matches)
            self.ready_sets = sum(
                1 for m in self.matches if m.state == MatchState.READY and not m.started_at
            )
            self.in_progress_sets = sum(
                1
                for m in self.matches
                if (m.state == MatchState.IN_PROGRESS or (m.state == MatchState.READY and m.started_at))
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

    def update_table(self) -> None:
        """Update the matches display with vertical pool columns"""
        log(f"🔄 update_table() called with {len(self.matches)} matches")

        container = self.query_one("#main-container", ScrollableContainer)
        pools_container = container.query_one("#pools-container", Horizontal)

        if not self.matches:
            log("⚠️  No matches to display")
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

        # Group matches by pool
        from collections import defaultdict

        pools = defaultdict(list)
        for match in self.matches:
            pools[match.pool].append(match)

        log(f"🔄 Found {len(pools)} pools: {list(pools.keys())}")

        # Check if we need to rebuild the entire structure
        existing_pools = {
            section.id for section in pools_container.query(".pool-section")
        }
        new_pools = {f"pool-{(pool or 'unknown').lower().replace(' ', '-')}" for pool in pools.keys()}

        # Always rebuild if there's a loading message present
        has_loading_message = bool(pools_container.query("#loading-message"))

        rebuild_needed = existing_pools != new_pools or has_loading_message

        if rebuild_needed:
            log("🔄 Pool structure changed, rebuilding columns")
            pools_container.remove_children()
        else:
            log("🔄 Pool structure unchanged, updating existing tables")

        # Sort pools by name for consistent ordering
        sorted_pools = sorted(key for key in pools.keys() if key is not None)

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
            # Create column containers
            columns = []
            for i in range(num_columns):
                column = Vertical(classes="pool-column", id=f"column-{i}")
                columns.append(column)
                pools_container.mount(column)

            # Distribute pools across columns
            for i, pool_name in enumerate(sorted_pools):
                column_index = i % num_columns
                column = columns[column_index]
                pool_matches = pools[pool_name]
                pool_id = f"pool-{(pool_name or 'unknown').lower().replace(' ', '-')}"

                # Sort matches within each pool: In Progress first, then Ready, then Waiting
                sorted_matches = sorted(
                    pool_matches,
                    key=lambda m: (
                        # Check if state 2 match has actually started
                        (
                            0
                            if (m.state == MatchState.READY and m.started_at)
                            else 1 if m.state == MatchState.READY else 2 if m.state == MatchState.IN_PROGRESS else 3
                        ),  # Priority order
                        -(m.updated_at or 0),  # Most recent first within each priority
                    ),
                )

                # Create a new DataTable for this pool
                pool_table: DataTable = DataTable(classes="pool-table")
                pool_table.add_column("Match", width=28)
                pool_table.add_column("Status", width=10)
                pool_table.add_column("Duration", width=10)
                pool_table.cursor_type = "row"

                # Add matches to the pool table
                for match in sorted_matches:
                    row_data = [
                        match.match_name,
                        f"{match.status_icon} {match.status_text}",
                        match.time_since_ready,
                    ]
                    pool_table.add_row(*row_data, key=str(match.id))

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
        else:
            # Update existing pool tables
            for pool_name in sorted_pools:
                pool_matches = pools[pool_name]
                pool_id = f"pool-{(pool_name or 'unknown').lower().replace(' ', '-')}"

                # Sort matches within each pool
                sorted_matches = sorted(
                    pool_matches,
                    key=lambda m: (
                        (
                            0
                            if (m.state == MatchState.READY and m.started_at)
                            else 1 if m.state == MatchState.READY else 2 if m.state == MatchState.IN_PROGRESS else 3
                        ),
                        -(m.updated_at or 0),
                    ),
                )

                try:
                    pool_section = cast(Vertical, pools_container.query_one(f"#{pool_id}"))
                    pool_table = pool_section.query_one(DataTable)
                    pool_table.clear()

                    # Add updated matches
                    for match in sorted_matches:
                        row_data = [
                            match.match_name,
                            f"{match.status_icon} {match.status_text}",
                            match.time_since_ready,
                        ]
                        pool_table.add_row(*row_data, key=str(match.id))

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

            pools = defaultdict(list)
            for match in self.matches:
                pools[match.pool].append(match)

            for pool_name in sorted(key for key in pools.keys() if key is not None):
                pool_matches = pools[pool_name]
                pool_id = f"pool-{(pool_name or 'unknown').lower().replace(' ', '-')}"

                # Sort matches same as update_table
                sorted_matches = sorted(
                    pool_matches,
                    key=lambda m: (
                        (
                            0
                            if (m.state == MatchState.READY and m.started_at)
                            else 1 if m.state == MatchState.READY else 2 if m.state == MatchState.IN_PROGRESS else 3
                        ),
                        -(m.updated_at or 0),
                    ),
                )

                try:
                    pool_section = container.query_one(f"#{pool_id}")
                    pool_table = pool_section.query_one(DataTable)

                    # Update just the duration column (column 3) for each match
                    for i, match in enumerate(sorted_matches):
                        pool_table.update_cell_at(Coordinate(i, 3), match.time_since_ready)

                except Exception as e:
                    # If individual updates fail, fall back to full refresh every 10 seconds
                    if int(time.time()) % 10 == 0:
                        self.update_table()
                        break

        except Exception as e:
            # Only print this error occasionally to avoid spam
            if int(time.time()) % 30 == 0:
                log(f"⚠️  Could not update display: {e}")

    def action_refresh(self) -> None:
        """Manually refresh data"""
        log("🔄 Manual refresh triggered")
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
