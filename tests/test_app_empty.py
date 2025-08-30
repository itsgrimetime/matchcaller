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
        
    def load_mock_data(self):
        """Load empty tournament data"""
        self.event_name = "Empty Tournament"
        self.matches = []
        self.total_sets = 0
        self.ready_sets = 0
        self.in_progress_sets = 0
        self.last_update = "Empty Data"
        self.update_table()

if __name__ == "__main__":
    app = EmptyTournamentDisplay()
    app.run()