"""Mock tournament data for testing and demo purposes."""

from typing import Any, Dict

# Fixed timestamp for consistent testing: Jan 1, 2022 00:00:00 UTC
MOCK_BASE_TIME = 1640995200

# Mock tournament data structure matching start.gg API response format
MOCK_TOURNAMENT_DATA: Dict[str, Any] = {
    "event_name": "Summer Showdown 2025",
    "sets": [
        {
            "id": 1,
            "displayName": "Winners Bracket - Round 1",
            "player1": {"tag": "Alice"},
            "player2": {"tag": "Bob"},
            "state": 2,  # Ready to be called
            "updatedAt": MOCK_BASE_TIME - 300,  # 5 minutes ago
        },
        {
            "id": 2,
            "displayName": "Winners Bracket - Quarterfinals",
            "player1": {"tag": "Charlie"},
            "player2": {"tag": "Dave"},
            "state": 6,  # In progress
            "updatedAt": MOCK_BASE_TIME - 120,  # 2 minutes ago
        },
        {
            "id": 3,
            "displayName": "Losers Bracket - Round 2",
            "player1": {"tag": "Eve"},
            "player2": {"tag": "Frank"},
            "state": 1,  # Not started
            "updatedAt": MOCK_BASE_TIME - 60,
        },
        {
            "id": 4,
            "displayName": "Grand Finals",
            "player1": {"tag": "Winner A"},
            "player2": {"tag": "Winner B"},
            "state": 1,  # Not started
            "updatedAt": MOCK_BASE_TIME - 30,
        },
    ],
}