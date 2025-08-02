"""
Tournament Display TUI - A terminal-based tournament viewer
Designed for Raspberry Pi Zero 2W - no X11/browser required!
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

import aiohttp

# Set up file logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("/tmp/tournament_debug.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def log(message):
    """Log to both file and console"""
    logger.info(message)
    # Also write directly to file to be extra sure
    with open("/tmp/tournament_debug.log", "a") as f:
        f.write(f"{datetime.now()} - {message}\n")
        f.flush()


try:
    from textual import work
    from textual.app import App, ComposeResult
    from textual.containers import Container
    from textual.reactive import reactive
    from textual.widgets import DataTable, Footer, Header, Label
except ImportError:
    log("Installing required dependencies...")
    import subprocess

    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "textual", "aiohttp"]
    )
    log("Dependencies installed! Please run the script again.")
    sys.exit(0)

# Mock data for testing (replace with real start.gg API calls)
MOCK_TOURNAMENT_DATA = {
    "event_name": "Summer Showdown 2025",
    "sets": [
        {
            "id": 1,
            "displayName": "Winners Bracket - Round 1",
            "player1": {"tag": "Alice"},
            "player2": {"tag": "Bob"},
            "state": 2,  # Ready to be called
            "updatedAt": int(time.time()) - 300,  # 5 minutes ago
        },
        {
            "id": 2,
            "displayName": "Winners Bracket - Quarterfinals",
            "player1": {"tag": "Charlie"},
            "player2": {"tag": "Dave"},
            "state": 6,  # In progress
            "updatedAt": int(time.time()) - 120,  # 2 minutes ago
        },
        {
            "id": 3,
            "displayName": "Losers Bracket - Round 2",
            "player1": {"tag": "Eve"},
            "player2": {"tag": "Frank"},
            "state": 1,  # Not started
            "updatedAt": int(time.time()) - 60,
        },
        {
            "id": 4,
            "displayName": "Grand Finals",
            "player1": {"tag": "Winner A"},
            "player2": {"tag": "Winner B"},
            "state": 1,  # Not started
            "updatedAt": int(time.time()) - 30,
        },
    ],
}


class TournamentAPI:
    """Handle API calls to start.gg"""

    def __init__(
        self,
        api_token: Optional[str] = None,
        event_id: Optional[str] = None,
        event_slug: Optional[str] = None,
    ):
        self.api_token = api_token
        self.event_id = event_id
        self.event_slug = event_slug  # New: accept event slug
        self.base_url = "https://api.start.gg/gql/alpha"

    async def fetch_sets(self) -> dict:
        """Fetch tournament sets from start.gg API"""
        log(
            f"🔍 API Token: {'***' + self.api_token[-4:] if self.api_token else 'None'}"
        )
        log(f"🔍 Event ID: {self.event_id}")
        log(f"🔍 Event Slug: {self.event_slug}")

        if not self.api_token:
            log("⚠️  Missing API token - using mock data")
            await asyncio.sleep(0.1)  # Simulate network delay
            return MOCK_TOURNAMENT_DATA

        # If we have a slug, get the event ID first
        if self.event_slug and not self.event_id:
            log("🔍 Getting event ID from slug...")
            self.event_id = await self.get_event_id_from_slug(self.event_slug)
            if not self.event_id:
                log("❌ Could not get event ID from slug")
                return MOCK_TOURNAMENT_DATA
            log(f"✅ Got event ID: {self.event_id}")

        if not self.event_id:
            log("⚠️  Missing event ID - using mock data")
            return MOCK_TOURNAMENT_DATA

        # Fixed start.gg GraphQL query - filter for active matches only
        query = """
        query EventSets($eventId: ID!, $page: Int!, $perPage: Int!) {
            event(id: $eventId) {
                name
                sets(
                    page: $page
                    perPage: $perPage
                    sortType: CALL_ORDER
                    filters: {
                        state: [1, 2, 6]
                    }
                ) {
                    nodes {
                        id
                        fullRoundText
                        identifier
                        state
                        updatedAt
                        startedAt
                        completedAt
                        round
                        slots {
                            id
                            entrant {
                                id
                                name
                                participants {
                                    id
                                    gamerTag
                                }
                            }
                            seed {
                                seedNum
                            }
                        }
                        phaseGroup {
                            id
                            displayIdentifier
                            phase {
                                id
                                name
                            }
                        }
                        stream {
                            streamName
                        }
                        station {
                            id
                            number
                        }
                    }
                }
            }
        }
        """

        variables = {
            "eventId": self.event_id,
            "page": 1,
            "perPage": 100,  # Get more sets at once
        }

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                log(f"🔍 Fetching data for event ID: {self.event_id}")
                async with session.post(
                    self.base_url,
                    json={"query": query, "variables": variables},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    log(f"📡 API Response Status: {response.status}")

                    if response.status != 200:
                        error_text = await response.text()
                        log(f"❌ HTTP Error: {error_text}")
                        raise aiohttp.ClientError(
                            f"HTTP {response.status}: {error_text}"
                        )

                    data = await response.json()
                    log(f"🔍 Raw API response keys: {list(data.keys())}")

                    if "errors" in data:
                        log(f"❌ GraphQL Errors: {data['errors']}")
                        for error in data["errors"]:
                            log(f"   - {error.get('message', 'Unknown error')}")
                        raise Exception(f"GraphQL errors: {data['errors']}")

                    if not data.get("data"):
                        log(f"❌ No data in response: {data}")
                        raise Exception("No data field in API response")

                    if not data["data"].get("event"):
                        log(f"❌ No event found for ID {self.event_id}")
                        raise Exception(f"Event not found for ID: {self.event_id}")

                    log(f"✅ Successfully fetched data!")
                    event_name = data["data"]["event"]["name"]
                    sets_count = len(data["data"]["event"]["sets"]["nodes"])
                    log(f"📊 Event: {event_name}")
                    log(f"📊 Found {sets_count} sets")

                    # Log some sample sets to see what states they have
                    if sets_count > 0:
                        for i, set_data in enumerate(
                            data["data"]["event"]["sets"]["nodes"][:5]
                        ):  # First 5 sets
                            player1 = "TBD"
                            player2 = "TBD"
                            if set_data["slots"] and len(set_data["slots"]) >= 2:
                                if (
                                    set_data["slots"][0]
                                    and set_data["slots"][0].get("entrant")
                                    and set_data["slots"][0]["entrant"].get(
                                        "participants"
                                    )
                                ):
                                    player1 = set_data["slots"][0]["entrant"][
                                        "participants"
                                    ][0]["gamerTag"]
                                if (
                                    set_data["slots"][1]
                                    and set_data["slots"][1].get("entrant")
                                    and set_data["slots"][1]["entrant"].get(
                                        "participants"
                                    )
                                ):
                                    player2 = set_data["slots"][1]["entrant"][
                                        "participants"
                                    ][0]["gamerTag"]

                            log(
                                f"📋 Sample set {i+1}: {player1} vs {player2} - State: {set_data['state']} - Round: {set_data.get('fullRoundText', 'N/A')}"
                            )

                    return self.parse_api_response(data)

        except Exception as e:
            log(f"❌ API Error: {type(e).__name__}: {e}")
            log("🔄 Falling back to mock data...")
            # Return mock data on error so the display still works
            return MOCK_TOURNAMENT_DATA

    def parse_api_response(self, data: Dict) -> Dict:
        """Parse the start.gg API response into our format"""
        try:
            event_data = data["data"]["event"]
            event_name = event_data["name"]
            sets_data = event_data["sets"]["nodes"]

            parsed_sets = []
            for set_data in sets_data:
                # Extract player names from slots
                player1_name = "TBD"
                player2_name = "TBD"

                if set_data["slots"] and len(set_data["slots"]) >= 2:
                    # Player 1
                    slot1 = set_data["slots"][0]
                    if (
                        slot1
                        and slot1.get("entrant")
                        and slot1["entrant"].get("participants")
                        and len(slot1["entrant"]["participants"]) > 0
                    ):
                        player1_name = slot1["entrant"]["participants"][0]["gamerTag"]

                    # Player 2
                    slot2 = set_data["slots"][1]
                    if (
                        slot2
                        and slot2.get("entrant")
                        and slot2["entrant"].get("participants")
                        and len(slot2["entrant"]["participants"]) > 0
                    ):
                        player2_name = slot2["entrant"]["participants"][0]["gamerTag"]

                # Create bracket name from phase and round info
                bracket_name = "Unknown Bracket"
                if set_data.get("phaseGroup") and set_data["phaseGroup"].get("phase"):
                    phase_name = set_data["phaseGroup"]["phase"]["name"]
                    bracket_name = phase_name

                # Add round information
                if set_data.get("fullRoundText"):
                    bracket_name += f" - {set_data['fullRoundText']}"
                elif set_data.get("identifier"):
                    bracket_name += f" - {set_data['identifier']}"
                elif set_data.get("round"):
                    bracket_name += f" - Round {set_data['round']}"

                parsed_set = {
                    "id": set_data["id"],
                    "displayName": bracket_name,
                    "player1": {"tag": player1_name},
                    "player2": {"tag": player2_name},
                    "state": set_data["state"],
                    "updatedAt": set_data["updatedAt"] or int(time.time()),
                    "startedAt": set_data.get("startedAt"),
                    "station": (
                        set_data.get("station", {}).get("number")
                        if set_data.get("station")
                        else None
                    ),
                    "stream": (
                        set_data.get("stream", {}).get("streamName")
                        if set_data.get("stream")
                        else None
                    ),
                }
                parsed_sets.append(parsed_set)
                log(
                    f"📋 Parsed set: {player1_name} vs {player2_name} ({bracket_name}) - State: {set_data['state']}"
                )

            result = {"event_name": event_name, "sets": parsed_sets}
            log(f"✅ Successfully parsed {len(parsed_sets)} sets")
            return result

        except Exception as e:
            log(f"❌ Error parsing API response: {e}")
            log(f"📋 Response structure: {json.dumps(data, indent=2)[:500]}...")
            return MOCK_TOURNAMENT_DATA

    async def get_event_id_from_slug(self, event_slug: str) -> Optional[str]:
        """Get event ID from event slug (e.g., 'tournament/the-c-stick-55/event/melee-singles')"""
        query = """
        query GetEvent($slug: String!) {
            event(slug: $slug) {
                id
                name
            }
        }
        """

        variables = {"slug": event_slug}
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                log(f"🔍 Fetching event ID for slug: {event_slug}")
                async with session.post(
                    self.base_url,
                    json={"query": query, "variables": variables},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    log(f"📡 Event ID API Response Status: {response.status}")

                    if response.status != 200:
                        error_text = await response.text()
                        log(f"❌ HTTP Error getting event ID: {error_text}")
                        return None

                    data = await response.json()
                    log(f"🔍 Event ID response: {data}")

                    if "errors" in data:
                        log(f"❌ GraphQL Errors getting event ID: {data['errors']}")
                        return None

                    if not data.get("data") or not data["data"].get("event"):
                        log(f"❌ No event found for slug: {event_slug}")
                        return None

                    event_id = data["data"]["event"]["id"]
                    event_name = data["data"]["event"]["name"]
                    log(f"✅ Found event: {event_name} (ID: {event_id})")
                    return event_id

        except Exception as e:
            log(f"❌ Error getting event ID: {type(e).__name__}: {e}")
            return None


class MatchRow:
    """Represents a single match/set"""

    STATE_COLORS = {
        1: "[dim]⚪[/dim]",  # Not started/Waiting - white
        2: "[red]🔴[/red]",  # Ready to be called - red
        3: "[green]✅[/green]",  # Completed - green
        6: "[yellow]🟡[/yellow]",  # In progress - yellow
        7: "[green]✅[/green]",  # Completed (alternative) - green
    }

    STATE_NAMES = {
        1: "Waiting",
        2: "Ready",
        3: "Completed",
        6: "In Progress",
        7: "Completed",
    }

    def __init__(self, set_data: Dict):
        self.id = set_data["id"]
        self.bracket = set_data["displayName"]
        self.player1 = set_data["player1"]["tag"] if set_data["player1"] else "TBD"
        self.player2 = set_data["player2"]["tag"] if set_data["player2"] else "TBD"
        self.state = set_data["state"]
        self.updated_at = set_data["updatedAt"]
        self.started_at = set_data.get("startedAt")
        self.station = set_data.get("station")
        self.stream = set_data.get("stream")

    @property
    def status_icon(self) -> str:
        # Check if match has actually started based on startedAt timestamp
        if self.state == 2 and self.started_at:
            # State 2 but has startedAt - it's actually in progress
            return "[yellow]🟡[/yellow]"
        else:
            return self.STATE_COLORS.get(self.state, "⚪")

    @property
    def status_text(self) -> str:
        # Check if match has actually started based on startedAt timestamp
        if self.state == 2 and self.started_at:
            # State 2 but has startedAt - it's actually in progress
            status = "In Progress"
        else:
            status = self.STATE_NAMES.get(self.state, "Unknown")

        # Add station info if available
        if self.station:
            status += f" (Station {self.station})"
        elif self.stream:
            status += f" (Stream: {self.stream})"

        return status

    @property
    def match_name(self) -> str:
        return f"{self.player1} vs {self.player2}"

    @property
    def time_since_ready(self) -> str:
        """Calculate time since match became ready or started"""
        if self.state == 2:  # Ready to be called
            now = int(time.time())
            diff = now - self.updated_at

            if diff < 60:
                return f"{diff}s ago"
            elif diff < 3600:
                minutes = diff // 60
                return f"{minutes}m {diff % 60}s ago"
            else:
                hours = diff // 3600
                minutes = (diff % 3600) // 60
                return f"{hours}h {minutes}m ago"

        elif self.state == 6 and self.started_at:  # In progress
            now = int(time.time())
            diff = now - self.started_at

            if diff < 60:
                return f"Started {diff}s ago"
            elif diff < 3600:
                minutes = diff // 60
                return f"Started {minutes}m ago"
            else:
                hours = diff // 3600
                minutes = (diff % 3600) // 60
                return f"Started {hours}h {minutes}m ago"

        return "-"


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

    .info-bar {
        height: 1;
        background: $surface;
        border: solid $primary;
        margin: 0 1;
        padding: 0 1;
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

        # Compact info bar with all stats in one line
        with Container(classes="info-bar"):
            yield Label(
                f"🏆 {self.event_name} | Total: {self.total_sets} | Ready: {self.ready_sets} | In Progress: {self.in_progress_sets} | Updated: {self.last_update}",
                id="info-line",
            )

        yield DataTable(id="matches-table")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the app"""
        log("🏁 on_mount() called")
        # Set up the data table
        table = self.query_one("#matches-table", DataTable)
        table.add_columns("Match", "Bracket", "Status", "Time Ready")
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
        # Update the compact info line
        info_text = f"🏆 {self.event_name} | Total: {self.total_sets} | Ready: [red]{self.ready_sets}[/red] | In Progress: [yellow]{self.in_progress_sets}[/yellow] | Updated: {self.last_update}"
        try:
            self.query_one("#info-line", Label).update(info_text)
        except Exception as e:
            # Only print this error occasionally to avoid spam
            if int(time.time()) % 10 == 0:  # Every 10 seconds
                print(f"⚠️  Could not update info line: {e}")

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
                if match.state in [2, 6] or (
                    match.state == 2 and match.started_at
                ):  # Ready, In Progress, or Started matches - update time
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


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Tournament Display TUI")
    parser.add_argument("--token", help="start.gg API token")
    parser.add_argument("--event", help="start.gg event ID")
    parser.add_argument(
        "--slug",
        help="start.gg event slug (e.g., tournament/the-c-stick-55/event/melee-singles)",
    )
    parser.add_argument("--demo", action="store_true", help="Run with demo data")

    args = parser.parse_args()

    log(f"🔍 Command line args:")
    log(f"   Token: {'***' + args.token[-4:] if args.token else 'None'}")
    log(f"   Event: {args.event}")
    log(f"   Slug: {args.slug}")
    log(f"   Demo: {args.demo}")

    # Debug the actual values being passed
    log(f"🔍 Raw args.token: {repr(args.token)}")
    log(f"🔍 Raw args.event: {repr(args.event)}")
    log(f"🔍 Raw args.slug: {repr(args.slug)}")

    if args.demo or (not args.token or (not args.event and not args.slug)):
        log("🏆 Running in DEMO mode with mock data")
        log("   Use --token and (--event or --slug) for real data")
        log("   Press Ctrl+C to exit\n")
        time.sleep(2)
        # Force None values in demo mode
        token_to_use = None
        event_to_use = None
        slug_to_use = None
    else:
        log("🌐 Running with REAL start.gg data")
        log("   Press Ctrl+C to exit\n")
        time.sleep(1)
        token_to_use = args.token
        event_to_use = args.event
        slug_to_use = args.slug

    log(
        f"🔍 Creating app with token: {repr(token_to_use)}, event: {repr(event_to_use)}, slug: {repr(slug_to_use)}"
    )

    app = TournamentDisplay(
        api_token=token_to_use, event_id=event_to_use, event_slug=slug_to_use
    )

    try:
        log("🏁 Starting Textual app...")
        app.run()
        log("🏁 Textual app finished")
    except KeyboardInterrupt:
        log("\n👋 Tournament display stopped")
    except Exception as e:
        log(f"❌ App crashed: {type(e).__name__}: {e}")
        import traceback

        log(f"❌ Full traceback: {traceback.format_exc()}")


if __name__ == "__main__":
    main()
