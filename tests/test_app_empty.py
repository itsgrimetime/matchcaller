#!/usr/bin/env python3
"""Test app with empty tournament data for snapshot testing"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from matchcaller.matchcaller import TournamentDisplay

# Override the API to return empty data
class EmptyTournamentDisplay(TournamentDisplay):
    def __init__(self):
        super().__init__(api_token=None, event_id=None, event_slug=None)
        
    def on_mount(self) -> None:
        """Override to prevent time-based updates for stable snapshots"""
        # Load empty data immediately without setting up periodic updates
        self.show_loading_state()
        self.load_mock_data()
        
    def fetch_tournament_data(self):
        """Override to prevent time updates - just reload empty data (not async)"""
        self.load_mock_data()
        
    def update_display(self) -> None:
        """Override to prevent periodic time updates"""
        # Do nothing - keep display stable
        pass
        
    def load_mock_data(self):
        """Load empty tournament data"""
        self.event_name = "Empty Tournament"
        self.matches = []
        self.total_sets = 0
        self.ready_sets = 0
        self.in_progress_sets = 0
        self.last_update = "Empty Data"
        self.title = "Empty Tournament - No Matches"
        self.update_table()

if __name__ == "__main__":
    app = EmptyTournamentDisplay()
    app.run()