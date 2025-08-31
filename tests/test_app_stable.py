#!/usr/bin/env python3
"""Test app with stable, non-time-dependent data for consistent snapshot testing"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from matchcaller.matchcaller import TournamentDisplay, MatchRow

class StableTournamentDisplay(TournamentDisplay):
    """Tournament display with stable mock data for consistent snapshots"""
    
    def __init__(self):
        super().__init__(api_token=None, event_id=None, event_slug=None)
        
    def on_mount(self) -> None:
        """Override to prevent time-based updates for stable snapshots"""
        # Load stable mock data immediately without setting up periodic updates
        self.show_loading_state()
        self.load_mock_data()
        
    def fetch_tournament_data(self):
        """Override to prevent time updates - just reload stable data (not async)"""
        self.load_mock_data()
        
    def update_display(self) -> None:
        """Override to prevent periodic time updates"""
        # Do nothing - keep display stable
        pass
        
    def load_mock_data(self):
        """Load stable mock data with fixed time displays"""
        self.event_name = "Summer Showdown 2025"
        
        # Create stable match data with fixed "time ready" displays
        stable_sets = [
            {
                "id": 1,
                "displayName": "Winners Bracket - Round 1",
                "player1": {"tag": "Alice"},
                "player2": {"tag": "Bob"},
                "state": 2,  # Ready
                "updatedAt": 1640995200,
                "startedAt": None
            },
            {
                "id": 2,
                "displayName": "Winners Bracket - Quarterfinals", 
                "player1": {"tag": "Charlie"},
                "player2": {"tag": "Dave"},
                "state": 6,  # In progress
                "updatedAt": 1640995200,
                "startedAt": 1640995200
            },
            {
                "id": 3,
                "displayName": "Losers Bracket - Round 2",
                "player1": {"tag": "Eve"},
                "player2": {"tag": "Frank"},
                "state": 1,  # Waiting
                "updatedAt": 1640995200
            },
            {
                "id": 4,
                "displayName": "Grand Finals",
                "player1": {"tag": "Winner A"},
                "player2": {"tag": "Winner B"},
                "state": 1,  # Waiting
                "updatedAt": 1640995200
            }
        ]
        
        # Create match objects with stable time displays
        self.matches = []
        for set_data in stable_sets:
            match = StableMatchRow(set_data)
            self.matches.append(match)
        
        self.total_sets = len(self.matches)
        self.ready_sets = sum(1 for m in self.matches if m.state == 2)
        self.in_progress_sets = sum(1 for m in self.matches if m.state == 6)
        self.last_update = "10:30:00"  # Fixed time
        # Set title after event name is set
        self.title = f"Mock Tournament - {self.event_name}"
        self.update_table()

class StableMatchRow(MatchRow):
    """MatchRow with stable time displays for snapshot consistency"""
    
    @property
    def time_since_ready(self) -> str:
        """Return fixed time display based on match state for consistency"""
        if self.state == 2:  # Ready
            return "5m 0s ago"
        elif self.state == 6:  # In progress
            return "Started 2m ago"
        else:
            return "-"

if __name__ == "__main__":
    app = StableTournamentDisplay()
    app.run()