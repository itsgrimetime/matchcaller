"""Tournament API client for start.gg GraphQL API."""

import asyncio
import json
import random
import time
from typing import Dict, Optional

import aiohttp

from ..models.mock_data import MOCK_TOURNAMENT_DATA
from ..utils.logging import log


async def find_active_tournament(api_token: str) -> Optional[str]:
    """Find a random active tournament with multiple pools using your manual search approach"""
    log("🔍 Searching for recent tournaments with active brackets...")

    # Calculate timestamps for recent tournaments (tournaments are typically 1-6 hours long)
    now = int(time.time())
    start_of_search = now - (12 * 3600)  # 12 hours ago (to catch ongoing tournaments)
    end_of_search = now + (6 * 3600)  # 6 hours from now

    # GraphQL query to find recent tournaments
    query = """
    query TournamentsToday($perPage: Int!, $afterDate: Timestamp!, $beforeDate: Timestamp!) {
        tournaments(query: {
            perPage: $perPage
            page: 1
            filter: {
                afterDate: $afterDate
                beforeDate: $beforeDate
                published: true
            }
        }) {
            nodes {
                id
                name
                slug
                startAt
                endAt
                state
                events {
                    id
                    name
                    slug
                    state
                    sets(page: 1, perPage: 5, filters: {state: [1, 2, 6]}) {
                        nodes {
                            id
                            state
                            phaseGroup {
                                displayIdentifier
                            }
                        }
                    }
                }
            }
        }
    }
    """

    variables = {
        "perPage": 75,  # Reasonable number for 18-hour window
        "afterDate": start_of_search,
        "beforeDate": end_of_search,
    }
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.start.gg/gql/alpha",
                json={"query": query, "variables": variables},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    log(f"❌ Error fetching tournaments: HTTP {response.status}")
                    return None

                data = await response.json()

                if "errors" in data:
                    log(f"❌ GraphQL errors: {data['errors']}")
                    return None

                tournaments = (
                    data.get("data", {}).get("tournaments", {}).get("nodes", [])
                )
                log(
                    f"🔍 Found {len(tournaments)} tournaments in 18-hour window (12h ago to 6h from now)"
                )

                # Filter for tournaments with active brackets
                suitable_tournaments = []
                # Accept tournaments that started up to 8 hours ago or start up to 4 hours from now
                past_cutoff = now - (8 * 3600)  # Started within last 8 hours
                future_cutoff = now + (4 * 3600)  # Or starting within next 4 hours

                log(f"🔍 Debug: Current time: {now}")
                log(
                    f"🔍 Debug: Filtering for tournaments between {past_cutoff} and {future_cutoff}"
                )
                log(
                    "🔍 Debug: This covers tournaments from 8 hours ago to 4 hours from now"
                )

                for i, tournament in enumerate(tournaments):
                    if i < 5:  # Debug first 5 tournaments
                        log(
                            f"🔍 Debug Tournament {i+1}: {tournament.get('name', 'Unknown')}"
                        )
                        log(f"   Slug: {tournament.get('slug')}")
                        log(
                            f"   URL: https://www.start.gg/{tournament.get('slug', '')}"
                        )
                        log(
                            f"   Start time: {tournament.get('startAt')} (vs cutoff: {past_cutoff})"
                        )
                        log(f"   State: {tournament.get('state')}")
                        log(f"   Events: {len(tournament.get('events', []))}")

                    start_time = tournament.get("startAt")
                    if not start_time:
                        if i < 5:
                            log("   ❌ Skipped: No start time")
                        continue
                    if start_time < past_cutoff or start_time > future_cutoff:
                        if i < 5:
                            if start_time < now:
                                hours_ago = (now - start_time) / 3600
                                log(
                                    f"   ❌ Skipped: Started {hours_ago:.1f} hours ago (too long)"
                                )
                            else:
                                hours_future = (start_time - now) / 3600
                                log(
                                    f"   ❌ Skipped: Starts {hours_future:.1f} hours from now (too far)"
                                )
                        continue

                    events = tournament.get("events", [])
                    if i < 5:
                        log(f"   ✅ Recent enough, checking {len(events)} events")

                    for j, event in enumerate(events):
                        sets = event.get("sets", {}).get("nodes", [])
                        if i < 5:
                            log(
                                f"     Event {j+1} '{event.get('name', 'Unknown')}': {len(sets)} sets, state: {event.get('state')}"
                            )
                            log(f"       Event slug: {event.get('slug')}")
                            log(
                                f"       Event URL: https://www.start.gg/{event.get('slug', '')}"
                            )

                        if not sets:
                            if i < 5:
                                log("       ❌ No active matches")
                            continue

                        # Check for multiple pools by counting unique pool identifiers
                        pools = set()
                        active_matches = 0
                        for match_set in sets:
                            if match_set.get("state") in [
                                1,
                                2,
                                6,
                            ]:  # Active match states
                                active_matches += 1
                                phase_group = match_set.get("phaseGroup", {})
                                if phase_group and phase_group.get("displayIdentifier"):
                                    pools.add(phase_group["displayIdentifier"])

                        if i < 5:
                            log(
                                f"       Active matches: {active_matches}, Pools: {list(pools)}"
                            )

                        # Check if the event/bracket has actually started
                        event_state = event.get("state")
                        if i < 5:
                            log(
                                f"       Event state: {event_state} (1=Created, 2=Active, 3=Completed)"
                            )

                        # Prioritize events that are ACTIVE (state 2) with active matches
                        # State 1 = Created (not started), State 2 = Active (started), State 3 = Completed
                        # Also accept events with many active matches even if not in "ACTIVE" state (some TOs don't update state)
                        is_suitable = (
                            (
                                event_state == 2 and active_matches > 0
                            )  # Properly started events
                            or (
                                active_matches >= 5
                            )  # Or events with many active matches regardless of state
                        ) and (len(pools) > 1 or active_matches >= 3)

                        if is_suitable:
                            hours_since = (now - start_time) / 3600
                            suitable_tournaments.append(
                                {
                                    "tournament": tournament,
                                    "event": event,
                                    "pool_count": len(pools),
                                    "active_matches": active_matches,
                                    "hours_since_start": hours_since,
                                    "event_state": event_state,
                                }
                            )
                            if i < 5:
                                if event_state == 2:
                                    log(
                                        f"       ✅ SUITABLE! Event ACTIVE (state {event_state}), {len(pools)} pools, {active_matches} matches"
                                    )
                                else:
                                    log(
                                        f"       ✅ SUITABLE! Many active matches ({active_matches}), {len(pools)} pools, state {event_state}"
                                    )
                        elif i < 5:
                            if active_matches == 0:
                                log("       ❌ No active matches found")
                            elif event_state != 2 and active_matches < 5:
                                log(
                                    f"       ❌ Event not active: state {event_state}, only {active_matches} matches (need 5+ or state 2)"
                                )
                            else:
                                log(
                                    f"       ❌ Not enough pools: {len(pools)} pools (need multiple pools or 3+ matches)"
                                )

                log(f"🎯 Found {len(suitable_tournaments)} suitable tournaments")

                if not suitable_tournaments:
                    log("❌ No suitable tournaments found")
                    log(
                        "💡 Looking for: tournaments with ACTIVE brackets (state 2) that have multiple pools and ongoing matches"
                    )
                    log(
                        "💡 Note: We skip tournaments with 'Created' brackets (state 1) that haven't started yet"
                    )
                    return None

                # Pick a random tournament, prefer ones with more pools/matches
                selected = random.choice(suitable_tournaments)
                tournament = selected["tournament"]
                event = selected["event"]

                log(f"✅ Selected: {tournament['name']} - {event['name']}")
                log(
                    f"📊 {selected['pool_count']} pools, {selected['active_matches']} active matches"
                )
                log(f"⏱️  Started {selected['hours_since_start']:.1f} hours ago")
                log(
                    f"🎯 Event state: {selected['event_state']} (Active bracket with ongoing matches)"
                )

                # Create the event slug (just use the event slug directly)
                event_slug = event["slug"]
                log(f"🔍 Debug: Tournament slug: {tournament['slug']}")
                log(f"🔍 Debug: Event slug: {event['slug']}")
                log(f"🔍 Debug: Final event slug: {event_slug}")
                return event_slug

    except Exception as e:
        log(f"❌ Error finding active tournaments: {e}")
        return None


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
                        }
                    }
                }
            }
        }
        """

        variables = {
            "eventId": self.event_id,
            "page": 1,
            "perPage": 100,  # Increased after simplifying query to reduce complexity
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
            tournament_name = event_data.get("tournament", {}).get(
                "name", "Unknown Tournament"
            )
            sets_data = event_data["sets"]["nodes"]

            parsed_sets = []
            total_sets = len(sets_data)
            skipped_tbd_count = 0
            log(f"🔍 Processing {total_sets} sets from API")

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
                if player1_name == "TBD" or player2_name == "TBD":
                    skipped_tbd_count += 1
                    log(f"⏭️  Skipping TBD match: {player1_name} vs {player2_name}")
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
                "sets": parsed_sets,
            }
            log(f"✅ Successfully parsed {len(parsed_sets)} sets")
            log(
                f"📊 Total sets from API: {total_sets}, Skipped TBD vs TBD: {skipped_tbd_count}, Included: {len(parsed_sets)}"
            )
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
                        log(
                            "💡 Slug format should be: tournament/tournament-name/event/event-name"
                        )
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
