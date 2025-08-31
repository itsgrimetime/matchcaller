"""Mock tournament data for testing and demo purposes."""

from typing import Final

from .match import TournamentState

# Fixed timestamp for consistent testing: Jan 1, 2022 00:00:00 UTC
MOCK_BASE_TIME: Final[int] = 1640995200

# Mock tournament data structure matching start.gg API response format
MOCK_TOURNAMENT_DATA: TournamentState = {
    "event_name": "Summer Showdown 2025",
    "tournament_name": "Summer Showdown Tournament Series",
    "sets": [
            {
                "id": 1,
                "display_name": "Winners Bracket - Round 1",
                "displayName": "Winners Bracket - Round 1",
                "poolName": "Pool A",
                "phase_group": "Winners Bracket",
                "phase_name": "Winners Bracket",
                "player1": {"tag": "Alice", "id": 1},
                "player2": {"tag": "Bob", "id": 2},
                "state": 2,  # Ready to be called
                "created_at": MOCK_BASE_TIME - 600,
                "started_at": None,
                "completed_at": None,
                "updated_at": MOCK_BASE_TIME - 300,  # 5 minutes ago
                "updatedAt": MOCK_BASE_TIME - 300,  # 5 minutes ago
                "startedAt": None,
                "entrant1_source": None,
                "entrant2_source": None,
                "_simulation_context": None,
            },
            {
                "id": 2,
                "display_name": "Winners Bracket - Quarterfinals",
                "displayName": "Winners Bracket - Quarterfinals",
                "poolName": "Pool A",
                "phase_group": "Winners Bracket",
                "phase_name": "Winners Bracket",
                "player1": {"tag": "Charlie", "id": 3},
                "player2": {"tag": "Dave", "id": 4},
                "state": 6,  # In progress
                "created_at": MOCK_BASE_TIME - 240,
                "started_at": MOCK_BASE_TIME - 120,
                "completed_at": None,
                "updated_at": MOCK_BASE_TIME - 120,  # 2 minutes ago
                "updatedAt": MOCK_BASE_TIME - 120,  # 2 minutes ago
                "startedAt": MOCK_BASE_TIME - 120,
                "entrant1_source": None,
                "entrant2_source": None,
                "_simulation_context": None,
            },
            {
                "id": 3,
                "display_name": "Losers Bracket - Round 2",
                "displayName": "Losers Bracket - Round 2",
                "poolName": "Pool B",
                "phase_group": "Losers Bracket",
                "phase_name": "Losers Bracket",
                "player1": {"tag": "Eve", "id": 5},
                "player2": {"tag": "Frank", "id": 6},
                "state": 1,  # Not started
                "created_at": MOCK_BASE_TIME - 180,
                "started_at": None,
                "completed_at": None,
                "updated_at": MOCK_BASE_TIME - 60,
                "updatedAt": MOCK_BASE_TIME - 60,
                "startedAt": None,
                "entrant1_source": None,
                "entrant2_source": None,
                "_simulation_context": None,
            },
            {
                "id": 4,
                "display_name": "Grand Finals",
                "displayName": "Grand Finals",
                "poolName": "Finals",
                "phase_group": "Finals",
                "phase_name": "Finals",
                "player1": {"tag": "Winner A", "id": 7},
                "player2": {"tag": "Winner B", "id": 8},
                "state": 1,  # Not started
                "created_at": MOCK_BASE_TIME - 90,
                "started_at": None,
                "completed_at": None,
                "updated_at": MOCK_BASE_TIME - 30,
                "updatedAt": MOCK_BASE_TIME - 30,
                "startedAt": None,
                "entrant1_source": None,
                "entrant2_source": None,
                "_simulation_context": None,
            },
        ],
}
