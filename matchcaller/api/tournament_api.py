"""Tournament API client for start.gg GraphQL API."""

import asyncio
import json
import time
from typing import Dict, Optional

import aiohttp

from ..utils.logging import log


MOCK_TOURNAMENT_DATA = {
    "event_name": "Singles Tournament",
    "tournament_name": "Summer Showdown 2025",
    "sets": [
        {
            "id": 1,
            "displayName": "Winners Bracket - Round 1",
            "player1": {"tag": "Alice"},
            "player2": {"tag": "Bob"},
            "state": 2,  # Ready to be called
            "updatedAt": int(time.time()) - 300,  # 5 minutes ago
        },
        {
            "id": 2,
            "displayName": "Winners Bracket - Quarterfinals",
            "player1": {"tag": "Charlie"},
            "player2": {"tag": "Dave"},
            "state": 6,  # In progress
            "updatedAt": int(time.time()) - 120,  # 2 minutes ago
        },
        {
            "id": 3,
            "displayName": "Losers Bracket - Round 2",
            "player1": {"tag": "Eve"},
            "player2": {"tag": "Frank"},
            "state": 1,  # Not started
            "updatedAt": int(time.time()) - 60,
        },
        {
            "id": 4,
            "displayName": "Grand Finals",
            "player1": {"tag": "Winner A"},
            "player2": {"tag": "Winner B"},
            "state": 1,  # Not started
            "updatedAt": int(time.time()) - 30,
        },
    ],
}


class TournamentAPI:
    """Handle API calls to start.gg"""

    def __init__(
        self,
        api_token: Optional[str] = None,
        event_id: Optional[str] = None,
        event_slug: Optional[str] = None,
    ):
        self.api_token = api_token
        self.event_id = event_id
        self.event_slug = event_slug  # New: accept event slug
        self.base_url = "https://api.start.gg/gql/alpha"

    async def fetch_sets(self) -> Dict:
        """Fetch tournament sets from start.gg API"""
        log(
            f"🔍 API Token: {'***' + self.api_token[-4:] if self.api_token else 'None'}"
        )
        log(f"🔍 Event ID: {self.event_id}")
        log(f"🔍 Event Slug: {self.event_slug}")

        if not self.api_token:
            log("⚠️  Missing API token - using mock data")
            await asyncio.sleep(0.1)  # Simulate network delay
            return MOCK_TOURNAMENT_DATA

        # If we have a slug, get the event ID first
        if self.event_slug and not self.event_id:
            log("🔍 Getting event ID from slug...")
            self.event_id = await self.get_event_id_from_slug(self.event_slug)
            if not self.event_id:
                log("❌ Could not get event ID from slug")
                return MOCK_TOURNAMENT_DATA
            log(f"✅ Got event ID: {self.event_id}")

        if not self.event_id:
            log("⚠️  Missing event ID - using mock data")
            return MOCK_TOURNAMENT_DATA

        # Simplified start.gg GraphQL query - filter for active matches only
        query = """
        query EventSets($eventId: ID!, $page: Int!, $perPage: Int!) {
            event(id: $eventId) {
                name
                tournament {
                    name
                }
                sets(
                    page: $page
                    perPage: $perPage
                    sortType: CALL_ORDER
                    filters: {
                        state: [1, 2, 6]
                    }
                ) {
                    nodes {
                        id
                        fullRoundText
                        identifier
                        state
                        updatedAt
                        startedAt
                        round
                        slots {
                            entrant {
                                participants {
                                    gamerTag
                                }
                            }
                        }
                        phaseGroup {
                            displayIdentifier
                            bracketType
                            phase {
                                name
                            }
                        }
                        stream {
                            streamName
                        }
                        station {
                            number
                        }
                    }
                }
            }
        }
        """

        variables = {
            "eventId": self.event_id,
            "page": 1,
            "perPage": 50,  # Reduce to avoid complexity limits
        }

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                log(f"🔍 Fetching data for event ID: {self.event_id}")
                async with session.post(
                    self.base_url,
                    json={"query": query, "variables": variables},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    log(f"📡 API Response Status: {response.status}")

                    if response.status != 200:
                        error_text = await response.text()
                        log(f"❌ HTTP Error: {error_text}")
                        raise aiohttp.ClientError(
                            f"HTTP {response.status}: {error_text}"
                        )

                    data = await response.json()
                    log(f"🔍 Raw API response keys: {list(data.keys())}")

                    if "errors" in data:
                        log(f"❌ GraphQL Errors: {data['errors']}")
                        for error in data["errors"]:
                            log(f"   - {error.get('message', 'Unknown error')}")
                        raise Exception(f"GraphQL errors: {data['errors']}")

                    if not data.get("data"):
                        log(f"❌ No data in response: {data}")
                        raise Exception("No data field in API response")

                    if not data["data"].get("event"):
                        log(f"❌ No event found for ID {self.event_id}")
                        raise Exception(f"Event not found for ID: {self.event_id}")

                    log(f"✅ Successfully fetched data!")
                    event_name = data["data"]["event"]["name"]
                    sets_count = len(data["data"]["event"]["sets"]["nodes"])
                    log(f"📊 Event: {event_name}")
                    log(f"📊 Found {sets_count} sets")

                    # Log some sample sets to see what states they have
                    if sets_count > 0:
                        for i, set_data in enumerate(
                            data["data"]["event"]["sets"]["nodes"][:5]
                        ):  # First 5 sets
                            player1 = "TBD"
                            player2 = "TBD"
                            if set_data["slots"] and len(set_data["slots"]) >= 2:
                                if (
                                    set_data["slots"][0]
                                    and set_data["slots"][0].get("entrant")
                                    and set_data["slots"][0]["entrant"].get(
                                        "participants"
                                    )
                                ):
                                    player1 = set_data["slots"][0]["entrant"][
                                        "participants"
                                    ][0]["gamerTag"]
                                if (
                                    set_data["slots"][1]
                                    and set_data["slots"][1].get("entrant")
                                    and set_data["slots"][1]["entrant"].get(
                                        "participants"
                                    )
                                ):
                                    player2 = set_data["slots"][1]["entrant"][
                                        "participants"
                                    ][0]["gamerTag"]

                            log(
                                f"📋 Sample set {i+1}: {player1} vs {player2} - State: {set_data['state']} - Round: {set_data.get('fullRoundText', 'N/A')}"
                            )

                    return self.parse_api_response(data)

        except Exception as e:
            log(f"❌ API Error: {type(e).__name__}: {e}")
            log("🔄 Falling back to mock data...")
            # Return mock data on error so the display still works
            return MOCK_TOURNAMENT_DATA

    def parse_api_response(self, data: Dict) -> Dict:
        """Parse the start.gg API response into our format"""
        try:
            event_data = data["data"]["event"]
            event_name = event_data["name"]
            tournament_name = event_data.get("tournament", {}).get("name", "Unknown Tournament")
            sets_data = event_data["sets"]["nodes"]

            parsed_sets = []
            for set_data in sets_data:
                # Extract player names from slots
                player1_name = "TBD"
                player2_name = "TBD"

                if set_data["slots"] and len(set_data["slots"]) >= 2:
                    # Player 1
                    slot1 = set_data["slots"][0]
                    if (
                        slot1
                        and slot1.get("entrant")
                        and slot1["entrant"].get("participants")
                        and len(slot1["entrant"]["participants"]) > 0
                    ):
                        player1_name = slot1["entrant"]["participants"][0]["gamerTag"]

                    # Player 2
                    slot2 = set_data["slots"][1]
                    if (
                        slot2
                        and slot2.get("entrant")
                        and slot2["entrant"].get("participants")
                        and len(slot2["entrant"]["participants"]) > 0
                    ):
                        player2_name = slot2["entrant"]["participants"][0]["gamerTag"]

                # Create bracket name from phase and round info
                bracket_name = "Unknown Bracket"
                pool_name = "Unknown Pool"
                
                if set_data.get("phaseGroup"):
                    phase_group = set_data["phaseGroup"]
                    
                    # Get pool/group identifier and format it nicely
                    if phase_group.get("displayIdentifier"):
                        raw_identifier = phase_group["displayIdentifier"]
                        # Format pool names nicely
                        if raw_identifier.isdigit():
                            pool_name = f"Pool {raw_identifier}"
                        elif raw_identifier.isalpha() and len(raw_identifier) == 1:
                            pool_name = f"Pool {raw_identifier.upper()}"
                        else:
                            pool_name = raw_identifier
                    
                    # Get phase name for bracket
                    if phase_group.get("phase") and phase_group["phase"].get("name"):
                        phase_name = phase_group["phase"]["name"]
                        bracket_name = phase_name

                # Add round information to bracket name
                if set_data.get("fullRoundText"):
                    bracket_name += f" - {set_data['fullRoundText']}"
                elif set_data.get("identifier"):
                    bracket_name += f" - {set_data['identifier']}"
                elif set_data.get("round"):
                    bracket_name += f" - Round {set_data['round']}"

                # Skip matches where both players are TBD (not yet determined)
                if player1_name == "TBD" and player2_name == "TBD":
                    log(f"⏭️  Skipping TBD vs TBD match: {bracket_name}")
                    continue

                parsed_set = {
                    "id": set_data["id"],
                    "displayName": bracket_name,
                    "poolName": pool_name,
                    "player1": {"tag": player1_name},
                    "player2": {"tag": player2_name},
                    "state": set_data["state"],
                    "updatedAt": set_data["updatedAt"] or int(time.time()),
                    "startedAt": set_data.get("startedAt"),
                    "station": (
                        set_data.get("station", {}).get("number")
                        if set_data.get("station")
                        else None
                    ),
                    "stream": (
                        set_data.get("stream", {}).get("streamName")
                        if set_data.get("stream")
                        else None
                    ),
                }
                parsed_sets.append(parsed_set)
                log(
                    f"📋 Parsed set: {player1_name} vs {player2_name} ({bracket_name}) - State: {set_data['state']}"
                )

            result = {
                "event_name": event_name, 
                "tournament_name": tournament_name,
                "sets": parsed_sets
            }
            log(f"✅ Successfully parsed {len(parsed_sets)} sets")
            return result

        except Exception as e:
            log(f"❌ Error parsing API response: {e}")
            log(f"📋 Response structure: {json.dumps(data, indent=2)[:500]}...")
            return MOCK_TOURNAMENT_DATA

    async def get_event_id_from_slug(self, event_slug: str) -> Optional[str]:
        """Get event ID from event slug (e.g., 'tournament/the-c-stick-55/event/melee-singles')"""
        
        # Auto-fix common slug format issues
        if not event_slug.startswith("tournament/"):
            log(f"🔧 Slug missing 'tournament/' prefix, fixing: {event_slug}")
            event_slug = f"tournament/{event_slug}"
            log(f"🔧 Fixed slug: {event_slug}")
        
        log(f"🔍 Using event slug: {event_slug}")
        query = """
        query GetEvent($slug: String!) {
            event(slug: $slug) {
                id
                name
            }
        }
        """

        variables = {"slug": event_slug}
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                log(f"🔍 Fetching event ID for slug: {event_slug}")
                async with session.post(
                    self.base_url,
                    json={"query": query, "variables": variables},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    log(f"📡 Event ID API Response Status: {response.status}")

                    if response.status != 200:
                        error_text = await response.text()
                        log(f"❌ HTTP Error getting event ID: {error_text}")
                        return None

                    data = await response.json()
                    log(f"🔍 Event ID response: {data}")

                    if "errors" in data:
                        log(f"❌ GraphQL Errors getting event ID: {data['errors']}")
                        return None

                    if not data.get("data") or not data["data"].get("event"):
                        log(f"❌ No event found for slug: {event_slug}")
                        log("💡 Slug format should be: tournament/tournament-name/event/event-name")
                        log("💡 Example: tournament/evo-2023/event/street-fighter-6")
                        log("💡 Or try finding the correct slug from the start.gg URL")
                        return None

                    event_id = data["data"]["event"]["id"]
                    event_name = data["data"]["event"]["name"]
                    log(f"✅ Found event: {event_name} (ID: {event_id})")
                    return event_id

        except Exception as e:
            log(f"❌ Error getting event ID: {type(e).__name__}: {e}")
            return None