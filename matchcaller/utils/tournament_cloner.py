"""Tournament cloner for capturing historical match data from start.gg tournaments."""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import aiohttp

from .logging import log


class TournamentCloner:
    """Clone completed tournaments for simulation and testing"""
    
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.data_dir = Path("simulator_data")
        self.data_dir.mkdir(exist_ok=True)
    
    async def clone_tournament(self, event_slug: str) -> Optional[str]:
        """
        Clone a tournament by fetching all historical data.
        Returns the filename of the saved data.
        """
        log(f"🔄 Cloning tournament: {event_slug}")
        
        # Get event ID from slug
        event_id = await self._get_event_id_from_slug(event_slug)
        if not event_id:
            log("❌ Could not resolve event ID from slug")
            return None
        
        log(f"✅ Event ID: {event_id}")
        
        # Fetch all tournament data (including completed matches)
        tournament_data = await self._fetch_complete_tournament_data(event_id)
        if not tournament_data:
            log("❌ Failed to fetch tournament data")
            return None
        
        # Process and structure the data for simulation
        simulation_data = self._process_for_simulation(tournament_data, event_slug)
        
        # Save to file
        filename = self._generate_filename(event_slug)
        filepath = self.data_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(simulation_data, f, indent=2)
        
        log(f"✅ Tournament cloned successfully!")
        log(f"📁 Saved to: {filepath}")
        log(f"📊 Total matches: {len(simulation_data['matches'])}")
        log(f"⏱️  Duration: {simulation_data['duration_minutes']} minutes")
        
        return str(filepath)
    
    async def _get_event_id_from_slug(self, event_slug: str) -> Optional[int]:
        """Get event ID from slug"""
        query = """
        query EventBySlug($slug: String!) {
            event(slug: $slug) {
                id
                name
            }
        }
        """
        
        variables = {"slug": event_slug}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.start.gg/gql/alpha",
                    json={"query": query, "variables": variables},
                    headers={
                        "Authorization": f"Bearer {self.api_token}",
                        "Content-Type": "application/json",
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status != 200:
                        return None
                    
                    data = await response.json()
                    
                    if "errors" in data or not data.get("data", {}).get("event"):
                        return None
                    
                    return data["data"]["event"]["id"]
        except Exception as e:
            log(f"❌ Error resolving slug: {e}")
            return None
    
    async def _fetch_complete_tournament_data(self, event_id: int) -> Optional[Dict]:
        """Fetch all match data including completed matches"""
        query = """
        query CompleteEventData($eventId: ID!, $page: Int!, $perPage: Int!) {
            event(id: $eventId) {
                id
                name
                startAt
                tournament {
                    name
                    slug
                }
                sets(
                    page: $page
                    perPage: $perPage
                    sortType: CALL_ORDER
                    filters: {
                        state: [1, 2, 3, 6, 7]
                    }
                ) {
                    pageInfo {
                        total
                        totalPages
                    }
                    nodes {
                        id
                        fullRoundText
                        identifier
                        state
                        createdAt
                        updatedAt
                        startedAt
                        completedAt
                        round
                        winnerId
                        slots {
                            entrant {
                                id
                                participants {
                                    gamerTag
                                }
                            }
                        }
                        phaseGroup {
                            id
                            displayIdentifier
                            phase {
                                name
                            }
                        }
                        games {
                            winnerId
                            selections {
                                entrant {
                                    id
                                }
                                character {
                                    name
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        
        all_sets = []
        page = 1
        per_page = 50
        
        try:
            async with aiohttp.ClientSession() as session:
                while True:
                    variables = {
                        "eventId": event_id,
                        "page": page,
                        "perPage": per_page
                    }
                    
                    log(f"📥 Fetching page {page}...")
                    
                    async with session.post(
                        "https://api.start.gg/gql/alpha",
                        json={"query": query, "variables": variables},
                        headers={
                            "Authorization": f"Bearer {self.api_token}",
                            "Content-Type": "application/json",
                        },
                        timeout=aiohttp.ClientTimeout(total=15),
                    ) as response:
                        if response.status != 200:
                            log(f"❌ HTTP error: {response.status}")
                            return None
                        
                        data = await response.json()
                        
                        if "errors" in data:
                            log(f"❌ GraphQL errors: {data['errors']}")
                            return None
                        
                        event_data = data["data"]["event"]
                        sets_data = event_data["sets"]["nodes"]
                        page_info = event_data["sets"]["pageInfo"]
                        
                        all_sets.extend(sets_data)
                        
                        log(f"📊 Page {page}: {len(sets_data)} sets (total so far: {len(all_sets)})")
                        
                        if page >= page_info["totalPages"]:
                            break
                        
                        page += 1
                        
                        # Be nice to the API
                        await asyncio.sleep(0.2)
                
                # Add the sets back to the event data
                event_data["sets"]["nodes"] = all_sets
                
                return {"data": {"event": event_data}}
                
        except Exception as e:
            log(f"❌ Error fetching tournament data: {e}")
            return None
    
    def _process_for_simulation(self, tournament_data: Dict, event_slug: str) -> Dict:
        """Process raw tournament data into simulation format"""
        event_data = tournament_data["data"]["event"]
        
        # Extract basic info
        event_name = event_data["name"]
        tournament_name = event_data["tournament"]["name"]
        tournament_slug = event_data["tournament"]["slug"]
        
        # Process all matches
        matches = []
        timestamps = []
        
        for set_data in event_data["sets"]["nodes"]:
            # Extract player info
            player1 = "TBD"
            player2 = "TBD"
            
            if set_data["slots"] and len(set_data["slots"]) >= 2:
                slot1 = set_data["slots"][0]
                if (slot1 and slot1.get("entrant") and 
                    slot1["entrant"].get("participants") and 
                    len(slot1["entrant"]["participants"]) > 0):
                    player1 = slot1["entrant"]["participants"][0]["gamerTag"]
                
                slot2 = set_data["slots"][1]
                if (slot2 and slot2.get("entrant") and 
                    slot2["entrant"].get("participants") and 
                    len(slot2["entrant"]["participants"]) > 0):
                    player2 = slot2["entrant"]["participants"][0]["gamerTag"]
            
            # Create match entry
            match = {
                "id": set_data["id"],
                "display_name": set_data.get("fullRoundText", f"Round {set_data.get('round', '?')}"),
                "player1": {"tag": player1},
                "player2": {"tag": player2},
                "state": set_data["state"],
                "created_at": set_data.get("createdAt"),
                "updated_at": set_data.get("updatedAt"),
                "started_at": set_data.get("startedAt"),
                "completed_at": set_data.get("completedAt"),
                "winner_id": set_data.get("winnerId"),
                "phase_group": set_data.get("phaseGroup", {}).get("displayIdentifier", "Unknown"),
                "phase_name": set_data.get("phaseGroup", {}).get("phase", {}).get("name", "Unknown Phase"),
            }
            
            matches.append(match)
            
            # Collect timestamps for timeline
            for timestamp_field in ["created_at", "updated_at", "started_at", "completed_at"]:
                if match[timestamp_field]:
                    timestamps.append(match[timestamp_field])
        
        # Calculate tournament duration
        timestamps = [ts for ts in timestamps if ts]
        if timestamps:
            start_time = min(timestamps)
            end_time = max(timestamps)
            duration_minutes = (end_time - start_time) // 60
        else:
            duration_minutes = 0
        
        # Sort matches by created time (tournament progression)
        matches.sort(key=lambda m: m["created_at"] or 0)
        
        return {
            "metadata": {
                "event_slug": event_slug,
                "event_name": event_name,
                "tournament_name": tournament_name,
                "tournament_slug": tournament_slug,
                "cloned_at": int(time.time()),
                "total_matches": len(matches),
            },
            "duration_minutes": duration_minutes,
            "matches": matches,
        }
    
    def _generate_filename(self, event_slug: str) -> str:
        """Generate filename for cloned tournament data"""
        # Clean up slug for filename
        clean_slug = event_slug.replace("/", "_").replace("-", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"tournament_{clean_slug}_{timestamp}.json"
    
    def list_cloned_tournaments(self) -> List[Dict]:
        """List all cloned tournaments"""
        tournaments = []
        
        for filepath in self.data_dir.glob("tournament_*.json"):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                
                tournaments.append({
                    "filename": filepath.name,
                    "filepath": str(filepath),
                    "metadata": data["metadata"],
                    "duration_minutes": data["duration_minutes"],
                })
            except Exception as e:
                log(f"⚠️  Could not read {filepath}: {e}")
        
        # Sort by clone date (newest first)
        tournaments.sort(key=lambda t: t["metadata"].get("cloned_at", 0), reverse=True)
        
        return tournaments