"""Bracket simulator for replaying tournament state transitions."""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

from .logging import log


class BracketSimulator:
    """Simulate tournament brackets by replaying historical state transitions"""
    
    def __init__(self, tournament_file: str, speed_multiplier: float = 60.0):
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
        
    def load_tournament(self) -> bool:
        """Load tournament data from file"""
        try:
            with open(self.tournament_file, 'r') as f:
                self.tournament_data = json.load(f)
            
            log(f"📁 Loaded tournament: {self.tournament_data['metadata']['event_name']}")
            log(f"📊 Total matches: {self.tournament_data['metadata']['total_matches']}")
            log(f"⏱️  Duration: {self.tournament_data['duration_minutes']} minutes")
            
            # Build timeline of events
            self._build_timeline()
            
            return True
            
        except Exception as e:
            log(f"❌ Error loading tournament file: {e}")
            return False
    
    def _build_timeline(self):
        """Build a timeline of all state transition events"""
        events = []
        
        for match in self.tournament_data["matches"]:
            # Skip matches with missing players
            if (match["player1"]["tag"] == "TBD" or 
                match["player2"]["tag"] == "TBD"):
                continue
            
            # Add events for each state transition
            if match["created_at"]:
                events.append({
                    "timestamp": match["created_at"],
                    "type": "match_created",
                    "match_id": match["id"],
                    "state": 1,
                    "match": match
                })
            
            if match["started_at"]:
                events.append({
                    "timestamp": match["started_at"],
                    "type": "match_started",
                    "match_id": match["id"],
                    "state": 2,  # or 6, we'll determine from context
                    "match": match
                })
            
            if match["completed_at"]:
                events.append({
                    "timestamp": match["completed_at"],
                    "type": "match_completed",
                    "match_id": match["id"],
                    "state": 3,
                    "match": match
                })
        
        # Sort events by timestamp
        events.sort(key=lambda e: e["timestamp"])
        
        self.timeline_events = events
        
        if events:
            self.start_time = events[0]["timestamp"]
            log(f"📅 Timeline built: {len(events)} events")
            log(f"🏁 First event: {time.ctime(self.start_time)}")
    
    def get_current_state(self) -> Dict[str, Any]:
        """Get current tournament state based on simulation time"""
        current_matches = []
        
        # Find all matches that should be visible at current time
        for event in self.timeline_events:
            if event["timestamp"] <= self.current_time:
                match = event["match"].copy()
                
                # Determine current state of this match
                if event["type"] == "match_created":
                    match["state"] = 1  # Waiting
                elif event["type"] == "match_started":
                    # Check if match is completed yet
                    completed = any(
                        e["match_id"] == match["id"] and 
                        e["type"] == "match_completed" and 
                        e["timestamp"] <= self.current_time
                        for e in self.timeline_events
                    )
                    if completed:
                        match["state"] = 3  # Completed - don't show
                        continue
                    else:
                        # Determine if Ready (2) or In Progress (6)
                        # If startedAt is recent, it's likely In Progress
                        time_since_start = self.current_time - event["timestamp"]
                        if time_since_start < 300:  # Less than 5 minutes
                            match["state"] = 6  # In Progress
                        else:
                            match["state"] = 2  # Ready
                elif event["type"] == "match_completed":
                    continue  # Don't show completed matches
                
                # Transform data to match API format expected by MatchRow
                # Convert display_name -> displayName
                if "display_name" in match:
                    match["displayName"] = match["display_name"]
                
                # Add missing fields with defaults
                if "poolName" not in match:
                    match["poolName"] = match.get("phase_name", "Unknown Pool")
                
                # Update timestamps to current simulation time
                match["updatedAt"] = min(event["timestamp"], self.current_time)
                if match.get("started_at") and match["started_at"] <= self.current_time:
                    match["startedAt"] = match["started_at"]
                
                # Check if this match is already in our current list
                existing_idx = None
                for i, existing_match in enumerate(current_matches):
                    if existing_match["id"] == match["id"]:
                        existing_idx = i
                        break
                
                if existing_idx is not None:
                    # Update existing match
                    current_matches[existing_idx] = match
                else:
                    # Add new match
                    current_matches.append(match)
        
        # Filter out completed matches and format for API response
        active_matches = [
            m for m in current_matches 
            if m["state"] in [1, 2, 6]  # Only show active matches
        ]
        
        return {
            "event_name": self.tournament_data["metadata"]["event_name"],
            "sets": active_matches,
        }
    
    async def start_simulation(self, callback=None):
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
            while self.is_running and self.current_time <= self.timeline_events[-1]["timestamp"]:
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
    
    def stop_simulation(self):
        """Stop the running simulation"""
        self.is_running = False
    
    def get_simulation_progress(self) -> Dict[str, Any]:
        """Get current simulation progress"""
        if not self.timeline_events:
            return {"progress": 0, "current_time": 0, "end_time": 0}
        
        end_time = self.timeline_events[-1]["timestamp"]
        progress = (self.current_time - self.start_time) / (end_time - self.start_time)
        
        return {
            "progress": min(1.0, max(0.0, progress)),
            "current_time": self.current_time,
            "start_time": self.start_time,
            "end_time": end_time,
            "current_time_str": time.ctime(self.current_time),
            "active_matches": len(self.get_current_state()["sets"])
        }
    
    def jump_to_time(self, timestamp: int):
        """Jump simulation to specific timestamp"""
        self.current_time = max(self.start_time, min(timestamp, self.timeline_events[-1]["timestamp"]))
        log(f"⏭️  Jumped to: {time.ctime(self.current_time)}")
    
    def jump_to_progress(self, progress: float):
        """Jump simulation to specific progress percentage (0.0 to 1.0)"""
        if not self.timeline_events:
            return
        
        progress = max(0.0, min(1.0, progress))
        end_time = self.timeline_events[-1]["timestamp"]
        target_time = self.start_time + (end_time - self.start_time) * progress
        
        self.jump_to_time(int(target_time))


class SimulatedTournamentAPI:
    """Drop-in replacement for TournamentAPI that uses simulated data"""
    
    def __init__(self, simulator: BracketSimulator):
        self.simulator = simulator
        self.event_name = None
        self.event_slug = None
        self.api_token = None
        self.event_id = None
        
        # Initialize the simulation timeline
        if simulator.tournament_data:
            if not simulator.timeline_events:
                simulator._build_timeline()
            if simulator.timeline_events:
                simulator.current_time = simulator.start_time
    
    async def fetch_sets(self) -> Dict[str, Any]:
        """Return current simulated tournament state"""
        if not self.simulator.tournament_data:
            log("❌ No tournament data in simulator")
            return {"event_name": "Simulation Error", "sets": []}
        
        # Advance simulation time more intelligently
        if self.simulator.timeline_events:
            end_time = self.simulator.timeline_events[-1]["timestamp"]
            
            # Advance by 5 minutes of simulated time each call
            advance_seconds = 300
            self.simulator.current_time += advance_seconds
            
            # Don't go past the end
            if self.simulator.current_time > end_time:
                self.simulator.current_time = end_time
                
            # Log current simulation time for debugging
            from time import ctime
            log(f"🕐 Simulator at: {ctime(self.simulator.current_time)}")
        
        current_state = self.simulator.get_current_state()
        log(f"📊 Simulator returning {len(current_state['sets'])} matches")
        return current_state
    
    def parse_api_response(self, data: Dict) -> Dict:
        """Pass through - simulator already returns in correct format"""
        return data
    
    async def get_event_id_from_slug(self, slug: str) -> Optional[int]:
        """Simulate event ID resolution"""
        return 999999  # Dummy event ID