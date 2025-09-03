"""Bracket simulator for replaying tournament state transitions."""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Callable

from typing_extensions import override

from ..api.tournament_api import TournamentAPI
from ..models.match import (
    MatchData,
    MatchState,
    SimulationProgress,
    TimelineEvent,
    TournamentData,
    TournamentState,
)
from ..models.startgg_api import StartGGAPIResponse
from ..utils.logging import log


class BracketSimulator:
    """Simulate tournament brackets by replaying historical state transitions"""

    tournament_file: Path
    speed_multiplier: float
    tournament_data: TournamentData | None
    current_time: int
    start_time: int
    is_running: bool
    timeline_events: list[TimelineEvent]

    def __init__(self, tournament_file: str, speed_multiplier: float = 60.0) -> None:
        """
        Initialize simulator

        Args:
            tournament_file: Path to cloned tournament JSON file
            speed_multiplier: How much faster than real-time (60.0 = 1 hour becomes 1 minute)
        """
        self.tournament_file = Path(tournament_file)
        self.speed_multiplier = speed_multiplier
        self.tournament_data = None
        self.current_time = 0
        self.start_time = 0
        self.is_running = False
        self.timeline_events = []

    def load_tournament_data_from_file(
        self, tournament_file: str | Path
    ) -> TournamentData:
        with open(tournament_file, "r") as f:
            raw_data = json.loads(f.read())
            tournament_data = TournamentData(**raw_data)
            return tournament_data

    def load_tournament(self) -> bool:
        """Load tournament data from file"""
        try:
            self.tournament_data = self.load_tournament_data_from_file(
                self.tournament_file
            )

            log(f"📁 Loaded tournament: {self.tournament_data.metadata.event_name}")
            log(f"📊 Total matches: {self.tournament_data.metadata.total_matches}")
            log(f"⏱️  Duration: {self.tournament_data.duration_minutes} minutes")

            # Build timeline of events
            self.build_timeline()

            return True

        except Exception as e:
            log(f"❌ Error loading tournament file: {e}")
            return False

    def build_timeline(self) -> None:
        """Build a timeline of all state transition events"""
        if not self.tournament_data:
            return

        # Simple timeline: just track completions and starts from the original data
        events: list[TimelineEvent] = []

        for match in self.tournament_data["matches"]:
            # Skip matches with missing players
            if match["player1"]["tag"] == "TBD" or match["player2"]["tag"] == "TBD":
                continue

            # Add completion events
            completed_at = match.get("completed_at")
            if completed_at is not None:
                events.append(
                    TimelineEvent(
                        timestamp=completed_at,
                        type="match_completed",
                        match_id=match["id"],
                        state=3,
                        match=match,
                    )
                )

            # Add start events
            started_at = match.get("started_at")
            if started_at is not None:
                events.append(
                    TimelineEvent(
                        timestamp=started_at,
                        type="match_started",
                        match_id=match["id"],
                        state=2,
                        match=match,
                    )
                )

        # Sort events by timestamp
        events.sort(key=lambda e: e.timestamp)
        self.timeline_events = events

        if events:
            self.start_time = (
                events[0].timestamp - 3600
            )  # Start 1 hour before first event
            log(f"📅 Timeline built: {len(events)} events")
            log(f"🏁 Tournament starts: {time.ctime(self.start_time)}")
        else:
            log("⚠️  No timeline events found - check tournament data")

    def get_current_state(self) -> TournamentState:
        """Get current tournament state based on simulation time - shows realistic bracket progression"""
        if not self.tournament_data:
            return TournamentState(
                event_name="No Tournament",
                tournament_name="No Tournament",
                sets=[],
            )

        # Get all available matches based on bracket dependencies and simulation time
        available_matches = self._get_available_matches()

        # Apply tournament organizer constraints (concurrent match limits)
        realistic_matches = self._apply_tournament_constraints(available_matches)

        # Add simulation context to each match for normalized time calculations
        for match in realistic_matches:
            match["_simulation_context"] = {
                "current_time": self.current_time,
                "start_time": self.start_time,
                "is_simulation": True,
            }

        return TournamentState(
            event_name=self.tournament_data.metadata.event_name,
            tournament_name=self.tournament_data.metadata.tournament_name,
            sets=realistic_matches,
        )

    async def start_simulation(
        self, callback: Callable[[TournamentState], Any] | None = None
    ) -> None:
        """Start the simulation with optional callback for state updates"""
        if not self.tournament_data:
            log("❌ No tournament data loaded")
            return

        if not self.timeline_events:
            log("❌ No timeline events found")
            return

        self.is_running = True
        self.current_time = self.start_time

        log(f"🎬 Starting simulation at {self.speed_multiplier}x speed")
        log("⏸️  Press Ctrl+C to stop")

        last_state = None

        try:
            while (
                self.is_running
                and self.current_time <= self.timeline_events[-1].timestamp
            ):
                current_state = self.get_current_state()

                # Only call callback if state changed
                if current_state != last_state:
                    log(f"⏱️  Simulation time: {time.ctime(self.current_time)}")
                    log(f"📊 Active matches: {len(current_state['sets'])}")

                    if callback:
                        await callback(current_state)

                    last_state = current_state

                # Advance simulation time
                real_seconds = 1.0
                sim_seconds = real_seconds * self.speed_multiplier
                self.current_time += int(sim_seconds)

                await asyncio.sleep(real_seconds)

            log("🏁 Simulation completed!")

        except KeyboardInterrupt:
            log("\n⏹️  Simulation stopped by user")

        self.is_running = False

    def stop_simulation(self) -> None:
        """Stop the running simulation"""
        self.is_running = False

    def get_simulation_progress(self) -> SimulationProgress:
        """Get current simulation progress"""
        if not self.timeline_events:
            return SimulationProgress(
                progress=0.0,
                current_time=0,
                start_time=0,
                end_time=0,
                current_time_str=time.ctime(0),
                active_matches=0,
            )

        end_time = self.timeline_events[-1].timestamp
        progress = (self.current_time - self.start_time) / (end_time - self.start_time)

        return SimulationProgress(
            progress=min(1.0, max(0.0, progress)),
            current_time=self.current_time,
            start_time=self.start_time,
            end_time=end_time,
            current_time_str=time.ctime(self.current_time),
            active_matches=len(self.get_current_state().sets),
        )

    def jump_to_time(self, timestamp: int) -> None:
        """Jump simulation to specific timestamp"""
        self.current_time = max(
            self.start_time, min(timestamp, self.timeline_events[-1].timestamp)
        )
        log(f"⏭️  Jumped to: {time.ctime(self.current_time)}")

    def jump_to_progress(self, progress: float) -> None:
        """Jump simulation to specific progress percentage (0.0 to 1.0)"""
        if not self.timeline_events:
            return

        progress = max(0.0, min(1.0, progress))
        end_time = self.timeline_events[-1].timestamp
        target_time = self.start_time + (end_time - self.start_time) * progress

        self.jump_to_time(int(target_time))

    def _apply_tournament_constraints(
        self, matches: list[MatchData]
    ) -> list[MatchData]:
        """Apply realistic tournament constraints to limit concurrent matches"""
        if not matches:
            return matches

        # Group matches by pool
        pools: dict[str, list[MatchData]] = {}
        for match in matches:
            pool_name = match.get("poolName") or "Unknown Pool"
            if pool_name not in pools:
                pools[pool_name] = []
            pools[pool_name].append(match)

        realistic_matches: list[MatchData] = []

        # Check if we're near tournament start - show all initial matches
        tournament_start_threshold = self.start_time + 7200  # First 2 hours
        is_tournament_start = self.current_time <= tournament_start_threshold

        for pool_name, pool_matches in pools.items():
            # Sort matches by priority: In Progress > Ready > Waiting > TBD
            # Within each state, prefer matches that started earlier
            def match_priority(match: MatchData) -> tuple[int, int]:
                state_priority: dict[int, int] = {
                    MatchState.IN_PROGRESS: 0,
                    MatchState.READY: 1,
                    MatchState.WAITING: 2,
                }  # In Progress, Ready, Waiting
                if not match.player1.tag or not match.player2.tag:
                    return (3, 0)
                return (
                    state_priority.get(match.state, 3),
                    match.updatedAt or 0,
                )

            pool_matches.sort(key=match_priority)

            # Always show in-progress matches
            in_progress = [
                m for m in pool_matches if m["state"] == MatchState.IN_PROGRESS
            ]
            ready_waiting = [
                m
                for m in pool_matches
                if m["state"] in [MatchState.WAITING, MatchState.READY]
            ]

            # Add in-progress matches
            realistic_matches.extend(in_progress)

            if is_tournament_start:
                # At tournament start, show ALL available matches (initial seeded matches)
                realistic_matches.extend(ready_waiting)
            else:
                # Later in tournament, apply concurrent match limits
                # Tournament organizers typically run 2-4 matches concurrently per pool
                max_concurrent = min(4, max(2, len(pool_matches) // 3))
                remaining_slots = max_concurrent - len(in_progress)
                realistic_matches.extend(ready_waiting[:remaining_slots])

        return realistic_matches

    def _get_available_matches(self) -> list[MatchData]:
        """Get matches that should be available at current simulation time based on bracket progression"""
        if not self.tournament_data:
            return []

        completed_matches: set[int] = set()
        available_matches: list[MatchData] = []

        # Find which matches have been completed by current simulation time
        for event in self.timeline_events:
            if (
                event["timestamp"] <= self.current_time
                and event["type"] == "match_completed"
            ):
                completed_matches.add(event["match_id"])

        # Check each match to see if it should be available
        for match in self.tournament_data["matches"]:
            match_id = match["id"]

            # Skip already completed matches
            if match_id in completed_matches:
                continue

            # Skip matches with missing players
            if match["player1"]["tag"] == "TBD" or match["player2"]["tag"] == "TBD":
                continue

            # Check if prerequisites are met using entrant source information AND phase progression
            entrant1_source = match.get("entrant1_source")
            entrant2_source = match.get("entrant2_source")
            phase_name = match.get("phase_name", "")

            # Match is available if:
            # 1. It's in Bracket phase round 1 (initial matches), OR
            # 2. All source matches have been completed AND phase prerequisites are met
            prerequisites_met = True

            # Special handling for phase progression
            if phase_name == "Top 8":
                # Top 8 matches only available after significant bracket progression
                # Check if enough Bracket matches are completed to justify Top 8
                bracket_completed = sum(
                    1
                    for mid in completed_matches
                    for m in self.tournament_data["matches"]
                    if m["id"] == mid and m.get("phase_name") == "Bracket"
                )
                # Only show Top 8 after at least 75% of bracket matches are done
                total_bracket = sum(
                    1
                    for m in self.tournament_data["matches"]
                    if m.get("phase_name") == "Bracket"
                )
                if bracket_completed < (total_bracket * 0.75):
                    prerequisites_met = False

            elif phase_name == "Top 24":
                # Top 24 matches available after some bracket progression
                bracket_completed = sum(
                    1
                    for mid in completed_matches
                    for m in self.tournament_data["matches"]
                    if m["id"] == mid and m.get("phase_name") == "Bracket"
                )
                total_bracket = sum(
                    1
                    for m in self.tournament_data["matches"]
                    if m.get("phase_name") == "Bracket"
                )
                if bracket_completed < (total_bracket * 0.5):
                    prerequisites_met = False

            # Check if entrant sources have completed prerequisites
            if (
                prerequisites_met
                and entrant1_source
                and entrant1_source.get("type") == "set"
            ):
                source_set_id = entrant1_source.get("typeId")
                if source_set_id and int(source_set_id) not in completed_matches:
                    prerequisites_met = False

            if (
                prerequisites_met
                and entrant2_source
                and entrant2_source.get("type") == "set"
            ):
                source_set_id = entrant2_source.get("typeId")
                if source_set_id and int(source_set_id) not in completed_matches:
                    prerequisites_met = False

            if prerequisites_met:
                # Create match data in API format
                match_copy = match.copy()

                # Transform field names
                if "display_name" in match_copy:
                    match_copy["displayName"] = match_copy["display_name"]
                match_copy["poolName"] = match_copy.get(
                    "phase_group", match_copy.get("phase_name", "Pool")
                )

                # Determine match state based on simulation time and events
                match_copy["state"] = self._determine_match_state(match_id)

                # Set updatedAt to when the match became available in simulation
                # This enables proper "time since ready" calculations
                current_state = match_copy["state"]

                # For initial matches at tournament start, set updatedAt to tournament start time
                # This shows "time since tournament began" for initial waiting matches
                if (
                    phase_name == "Bracket"
                    and match_copy.get("round", 1) == 1
                    and current_state == MatchState.WAITING
                ):
                    match_copy["updatedAt"] = self.start_time
                else:
                    # Find when this match changed to current state from timeline events
                    state_change_event = None
                    for event in reversed(self.timeline_events):  # Check latest first
                        if (
                            event["match_id"] == match_id
                            and event["timestamp"] <= self.current_time
                        ):
                            # Look for state change events
                            if (
                                (
                                    current_state == MatchState.READY
                                    and event["type"]
                                    in ["match_created", "match_ready"]
                                )
                                or (
                                    current_state == MatchState.IN_PROGRESS
                                    and event["type"] == "match_started"
                                )
                                or (
                                    current_state == MatchState.WAITING
                                    and event["type"] == "match_created"
                                )
                            ):
                                state_change_event = event
                                break

                    if state_change_event:
                        match_copy["updatedAt"] = state_change_event["timestamp"]
                    else:
                        # Fallback: use original timestamp or current time
                        original_updated = match_copy.get("updated_at", 0)
                        match_copy["updatedAt"] = original_updated or self.current_time

                # Set startedAt based on simulation events
                started_event = next(
                    (
                        e
                        for e in self.timeline_events
                        if e["match_id"] == match_id
                        and e["type"] == "match_started"
                        and e["timestamp"] <= self.current_time
                    ),
                    None,
                )
                if started_event:
                    # Use the event timestamp directly
                    match_copy["startedAt"] = started_event["timestamp"]
                else:
                    match_copy["startedAt"] = None

                available_matches.append(match_copy)

        return available_matches

    def _determine_match_state(self, match_id: int) -> int:
        """Determine the current state of a match based on simulation time"""
        # Check for events affecting this match up to current time
        relevant_events: list[TimelineEvent] = [
            e
            for e in self.timeline_events
            if e["match_id"] == match_id and e["timestamp"] <= self.current_time
        ]

        if not relevant_events:
            return MatchState.WAITING  # Waiting (just became available)

        # Get the latest event for this match
        latest_event = max(relevant_events, key=lambda e: e["timestamp"])

        if latest_event["type"] == "match_started":
            # Check if it's been long enough to be "In Progress" vs just "Ready"
            time_since_start = self.current_time - latest_event["timestamp"]
            if time_since_start < 600:  # Less than 10 minutes - likely in progress
                return MatchState.IN_PROGRESS  # In Progress
            else:
                return MatchState.READY  # Ready (called but taking a while to start)
        elif latest_event["type"] == "match_created":
            return MatchState.READY  # Ready to be called

        return MatchState.WAITING  # Default to waiting

    def _build_dependency_graph(self) -> dict[int, list[int]]:
        """Build a graph of match dependencies - which matches depend on which other matches"""
        dependencies: dict[int, list[int]] = {}

        if not self.tournament_data:
            return dependencies

        for match in self.tournament_data["matches"]:
            match_id = match["id"]
            dependencies[match_id] = []

            # Check if entrant 1 comes from a previous match
            entrant1_source = match.get("entrant1_source")
            if entrant1_source and entrant1_source.get("type") == "set":
                source_set_id = entrant1_source.get("typeId")
                if source_set_id:
                    dependencies[match_id].append(int(source_set_id))

            # Check if entrant 2 comes from a previous match
            entrant2_source = match.get("entrant2_source")
            if entrant2_source and entrant2_source.get("type") == "set":
                source_set_id = entrant2_source.get("typeId")
                if source_set_id:
                    dependencies[match_id].append(int(source_set_id))

        return dependencies

    def _has_no_dependencies(self, match: MatchData) -> bool:
        """Check if a match has no dependencies (seeded players only)"""
        entrant1_source = match.get("entrant1_source")
        entrant2_source = match.get("entrant2_source")

        # Match has no dependencies if neither player comes from a previous set
        # (i.e., both are seeded players or have no sources)
        has_entrant1_set_source = (
            entrant1_source and entrant1_source.get("type") == "set"
        )
        has_entrant2_set_source = (
            entrant2_source and entrant2_source.get("type") == "set"
        )

        return not has_entrant1_set_source and not has_entrant2_set_source

    def _find_newly_available_matches(
        self,
        completed_match_id: int,
        completed_matches: set[int],
        dependencies: dict[int, list[int]],
    ) -> list[MatchData]:
        """Find matches that become available after a match is completed"""
        newly_available: list[MatchData] = []

        if not self.tournament_data:
            return newly_available

        for match in self.tournament_data["matches"]:
            match_id = match["id"]

            # Skip if already completed or has missing players
            if (
                match_id in completed_matches
                or match["player1"]["tag"] == "TBD"
                or match["player2"]["tag"] == "TBD"
            ):
                continue

            # Check if this match depends on the completed match
            match_dependencies = dependencies.get(match_id, [])
            if completed_match_id in match_dependencies:
                # Check if ALL dependencies are now met
                all_deps_met = all(
                    dep_id in completed_matches for dep_id in match_dependencies
                )
                if all_deps_met:
                    newly_available.append(match)

        return newly_available


class SimulatedTournamentAPI(TournamentAPI):
    """Drop-in replacement for TournamentAPI that uses simulated data"""

    simulator: BracketSimulator
    event_name: str | None
    event_slug: str | None
    api_token: str | None
    event_id: str | None

    def __init__(self, simulator: BracketSimulator) -> None:
        super().__init__()
        self.simulator = simulator
        self.event_name = None
        self.event_slug = None
        self.api_token = None
        self.event_id = None

        # Initialize the simulation timeline
        if simulator.tournament_data:
            if not simulator.timeline_events:
                simulator.build_timeline()
            if simulator.timeline_events:
                simulator.current_time = simulator.start_time

    @override
    async def fetch_sets(self) -> TournamentState:
        """Return current simulated tournament state with gradual time progression"""
        if not self.simulator.tournament_data:
            log("❌ No tournament data in simulator")
            return TournamentState(
                event_name="Simulation Error",
                tournament_name="Error",
                sets=[],
            )

        # Advance simulation time more gradually for realistic progression
        if self.simulator.timeline_events:
            end_time = self.simulator.timeline_events[-1].timestamp

            # Use speed multiplier for time advancement
            # Default: advance by 30 seconds of real time, scaled by speed multiplier
            real_time_advance = 1  # 30 seconds of tournament time per API call
            advance_seconds = int(real_time_advance * self.simulator.speed_multiplier)
            self.simulator.current_time += advance_seconds

            # Don't go past the end
            if self.simulator.current_time > end_time:
                self.simulator.current_time = end_time

            # Log current simulation time for debugging
            from time import ctime

            log(f"🕐 Simulator at: {ctime(self.simulator.current_time)}")

        current_state = self.simulator.get_current_state()

        # Group matches by pools for better logging
        pools: dict[str, list[MatchData]] = {}
        for match in current_state["sets"]:
            pool_name = match.get("poolName") or "Unknown Pool"
            if pool_name not in pools:
                pools[pool_name] = []
            pools[pool_name].append(match)

        log(
            f"📊 Simulator returning {len(current_state['sets'])} matches across {len(pools)} pools"
        )
        for pool_name, matches in pools.items():
            states: dict[str, int] = {}
            for match in matches:
                state = match["state"]
                state_mapping: dict[int, str] = {
                    MatchState.WAITING: "Waiting",
                    MatchState.READY: "Ready",
                    MatchState.IN_PROGRESS: "In Progress",
                }
                state_name = state_mapping.get(state, f"State {state}")
                states[state_name] = states.get(state_name, 0) + 1
            log(f"   📋 {pool_name}: {dict(states)}")

        return current_state

    @override
    def parse_api_response(self, api_response: StartGGAPIResponse) -> TournamentState:
        """This method should not be called in simulation mode"""
        raise NotImplementedError(
            "SimulatedTournamentAPI does not parse API responses - it generates its own data"
        )

    async def get_event_id_from_slug(self, event_slug: str) -> str | None:
        """Simulate event ID resolution"""
        return "999999"  # Dummy event ID
