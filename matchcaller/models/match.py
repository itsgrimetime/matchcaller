"""Match data model and related utilities."""

import time
from typing import Dict


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
        """Calculate time since match became ready, started, or was last updated"""
        now = int(time.time())

        if self.state == 2:  # Ready to be called
            diff = now - self.updated_at

            if diff < 60:
                return f"{diff}s"
            elif diff < 3600:
                minutes = diff // 60
                return f"{minutes}m {diff % 60}s"
            else:
                hours = diff // 3600
                minutes = (diff % 3600) // 60
                return f"{hours}h {minutes}m"

        elif self.state == 6 and self.started_at:  # In progress
            diff = now - self.started_at

            if diff < 60:
                return f"{diff}s"
            elif diff < 3600:
                minutes = diff // 60
                return f"{minutes}m"
            else:
                hours = diff // 3600
                minutes = (diff % 3600) // 60
                return f"{hours}h {minutes}m"

        elif self.state == 1:  # Waiting - show time since last updated
            diff = now - self.updated_at

            if diff < 60:
                return f"{diff}s"
            elif diff < 3600:
                minutes = diff // 60
                return f"{minutes}m"
            else:
                hours = diff // 3600
                minutes = (diff % 3600) // 60
                return f"{hours}h {minutes}m"

        return "-"
