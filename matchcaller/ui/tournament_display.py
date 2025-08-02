"""Main tournament display TUI application."""

import time
from datetime import datetime
from typing import List, Optional

try:
    from textual import work
    from textual.app import App, ComposeResult
    from textual.containers import Container
    from textual.reactive import reactive
    from textual.widgets import DataTable, Footer, Header, Label
except ImportError:
    raise ImportError(
        "Missing required dependencies. Please install with: pip install textual aiohttp"
    )

from ..api import TournamentAPI
from ..models import MatchRow
from ..utils.logging import log


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

    DataTable {
        height: 1fr;
        margin: 1;
        border: solid $primary;
        min-height: 10;
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
        self.api = TournamentAPI(api_token, event_id, event_slug)
        self.matches: List[MatchRow] = []
        self.refresh_timer = None
        log(
            f"🎯 TournamentDisplay initialized with token: {'***' + api_token[-4:] if api_token else 'None'}, event: {event_id}, slug: {event_slug}"
        )

    def compose(self) -> ComposeResult:
        """Create the UI layout"""
        yield Header()
        yield DataTable(id="matches-table")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the app"""
        log("🏁 on_mount() called")
        # Set up the data table
        table = self.query_one("#matches-table", DataTable)
        table.add_columns("Match", "Bracket", "Status", "Duration")
        table.cursor_type = "row"

        # Test with mock data first to verify the UI works
        log("🧪 Testing with mock data first...")
        self.load_mock_data()

        # Start periodic updates
        self.set_interval(1.0, self.update_display)  # Update every second
        self.set_interval(
            30.0, self.fetch_tournament_data
        )  # Fetch fresh data every 30 seconds

        log("🚀 Starting initial data fetch...")
        # Initial fetch - run immediately after a delay
        self.set_timer(3.0, self.fetch_tournament_data)  # Wait 3 seconds then fetch
        log("🚀 Initial fetch scheduled")

    def load_mock_data(self) -> None:
        """Load mock data to test the UI"""
        from ..api.tournament_api import MOCK_TOURNAMENT_DATA

        log("🧪 Loading mock data for testing...")
        data = MOCK_TOURNAMENT_DATA
        self.event_name = data["event_name"]
        self.matches = [MatchRow(set_data) for set_data in data["sets"]]
        self.total_sets = len(self.matches)
        self.ready_sets = sum(1 for m in self.matches if m.state == 2)
        self.in_progress_sets = sum(1 for m in self.matches if m.state == 6)
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

            self.event_name = data["event_name"]
            log(f"🔄 Event name set to: {self.event_name}")

            self.matches = [MatchRow(set_data) for set_data in data["sets"]]
            log(f"🔄 Created {len(self.matches)} match objects")

            self.total_sets = len(self.matches)
            self.ready_sets = sum(
                1 for m in self.matches if m.state == 2 and not m.started_at
            )
            self.in_progress_sets = sum(
                1
                for m in self.matches
                if (m.state == 6 or (m.state == 2 and m.started_at))
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
        """Update the matches table"""
        log(f"🔄 update_table() called with {len(self.matches)} matches")
        table = self.query_one("#matches-table", DataTable)
        table.clear()

        if not self.matches:
            log("⚠️  No matches to display")
            return

        # Sort matches: In Progress first, then Ready, then Waiting
        sorted_matches = sorted(
            self.matches,
            key=lambda m: (
                # Check if state 2 match has actually started
                (
                    0
                    if (m.state == 2 and m.started_at)
                    else 1 if m.state == 2 else 2 if m.state == 6 else 3
                ),  # Priority order
                -m.updated_at,  # Most recent first within each priority
            ),
        )

        log(f"🔄 Adding {len(sorted_matches)} rows to table")
        for i, match in enumerate(sorted_matches):
            # Highlight ready matches
            style = "bold red" if match.state == 2 else None

            row_data = [
                match.match_name,
                match.bracket,
                f"{match.status_icon} {match.status_text}",
                match.time_since_ready,
            ]
            log(f"🔄 Adding row {i}: {row_data}")

            table.add_row(*row_data, key=str(match.id))

        log("✅ Table updated successfully")

    def update_display(self) -> None:
        """Update time-dependent displays (called every second)"""
        # Update time calculations in the table (for ready matches)
        if not self.matches:
            return

        table = self.query_one("#matches-table", DataTable)
        try:
            # Sort matches same as update_table to get correct row indices
            sorted_matches = sorted(
                self.matches,
                key=lambda m: (
                    0 if m.state == 2 else 1 if m.state == 6 else 2,
                    -m.updated_at,
                ),
            )

            for i, match in enumerate(sorted_matches):
                if match.state in [1, 2, 6] or (
                    match.state == 2 and match.started_at
                ):  # Waiting, Ready, In Progress, or Started matches - update time
                    try:
                        table.update_cell_at((i, 3), match.time_since_ready)
                    except:
                        pass  # Handle any table update errors gracefully
        except Exception as e:
            # Only print this error occasionally to avoid spam
            if int(time.time()) % 30 == 0:  # Every 30 seconds
                log(f"⚠️  Could not update table times: {e}")

    def action_refresh(self) -> None:
        """Manually refresh data"""
        log("🔄 Manual refresh triggered")
        self.fetch_tournament_data()
        self.notify("Refreshing tournament data...")

    def action_quit(self) -> None:
        """Quit the application"""
        if self.refresh_timer:
            self.refresh_timer.cancel()
        self.exit()
