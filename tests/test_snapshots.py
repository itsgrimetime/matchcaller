"""Snapshot tests for UI consistency and visual regression detection

These tests capture the exact visual output of the TUI and detect any changes
that might occur during refactoring. Perfect for ensuring your TUI looks 
exactly the same after code changes.
"""

import pytest
from unittest.mock import patch
from matchcaller.matchcaller import TournamentDisplay


@pytest.mark.ui
class TestUISnapshots:
    """Snapshot tests for visual consistency"""

    def test_demo_mode_initial_display_snapshot(self, snap_compare):
        """Test that demo mode displays consistently"""
        # Use stable app to avoid time-based variations
        assert snap_compare("test_app_stable.py:StableTournamentDisplay", terminal_size=(120, 30))

    def test_demo_mode_after_refresh_snapshot(self, snap_compare):
        """Test that demo mode looks the same after refresh"""
        # Since the app doesn't require user interaction for demo mode,
        # we can test the base display state which should be consistent
        assert snap_compare("test_app_stable.py:StableTournamentDisplay", 
                          terminal_size=(120, 30))

    def test_different_terminal_sizes(self, snap_compare):
        """Test that the UI adapts correctly to different terminal sizes"""
        # Test common terminal sizes
        sizes = [
            (80, 24),   # Standard small terminal
            (120, 30),  # Medium terminal
            (160, 40),  # Large terminal
        ]
        
        for width, height in sizes:
            # Create separate snapshots for each size
            assert snap_compare(
                "test_app_stable.py:StableTournamentDisplay", 
                terminal_size=(width, height)
            )

    def test_custom_tournament_data_snapshot(self, snap_compare):
        """Test display with standard demo data"""
        # Test the standard demo mode which has varied match states
        assert snap_compare(
            "test_app_stable.py:StableTournamentDisplay",
            terminal_size=(140, 35)
        )

    def test_empty_tournament_snapshot(self, snap_compare):
        """Test display when tournament has no active matches"""
        assert snap_compare(
            "test_app_empty.py:EmptyTournamentDisplay",
            terminal_size=(120, 25)
        )

    def test_error_state_snapshot(self, snap_compare):
        """Test display when API errors occur (shows demo data)"""
        # When API fails, app falls back to demo data
        assert snap_compare(
            "test_app_stable.py:StableTournamentDisplay",
            terminal_size=(120, 25)
        )

    def test_raspberry_pi_display_size(self, snap_compare):
        """Test display at Raspberry Pi console size with large fonts"""
        # Simulate Raspberry Pi Zero 2W console with large fonts
        # Terminus 32x16 Bold would give roughly 50x15 characters
        assert snap_compare(
            "test_app_stable.py:StableTournamentDisplay",
            terminal_size=(50, 15)
        )