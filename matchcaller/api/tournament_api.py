"""Tournament API client for start.gg GraphQL API."""

import asyncio
import json
import time

import aiohttp

from ..models.match import MatchData, PlayerData, TournamentState
from ..models.mock_data import MOCK_TOURNAMENT_DATA
from ..models.startgg_api import (
    StartGGAPIResponse,
    StartGGEventBySlugResponse,
    StartGGEventSetsResponse,
)
from ..utils.logging import log


class TournamentAPI:
    """Handle API calls to start.gg"""

    def __init__(
        self,
        api_token: str | None = None,
        event_id: str | None = None,
        event_slug: str | None = None,
    ):
        self.api_token: str | None = api_token
        self.event_id: str | None = event_id
        self.event_slug: str | None = event_slug  # New: accept event slug
        self.base_url: str = "https://api.start.gg/gql/alpha"

    async def fetch_sets(self) -> TournamentState:
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

                    raw_data = await response.json()
                    log(f"🔍 Raw API response keys: {list(raw_data.keys())}")

                    # Parse and validate the response with Pydantic
                    try:
                        api_response = StartGGAPIResponse(**raw_data)
                    except Exception as e:
                        log(f"❌ Pydantic validation error: {e}")
                        log(
                            f"📋 Raw response: {json.dumps(raw_data, indent=2)[:500]}..."
                        )
                        raise Exception(f"API response validation failed: {e}")

                    if api_response.errors:
                        log("❌ GraphQL Errors: {api_response.errors}")
                        for error in api_response.errors:
                            log(f"   - {error.message}")
                        raise Exception(f"GraphQL errors: {api_response.errors}")

                    if not api_response.data:
                        log("❌ No data in response")
                        raise Exception("No data field in API response")

                    # Type narrowing for the response data
                    if not isinstance(api_response.data, StartGGEventSetsResponse):
                        log("❌ Unexpected response type")
                        raise Exception("Expected StartGGEventSetsResponse")

                    if not api_response.data.event:
                        log("❌ No event found for ID {self.event_id}")
                        raise Exception(f"Event not found for ID: {self.event_id}")

                    event = api_response.data.event
                    log("✅ Successfully fetched and validated data!")
                    log(f"📊 Event: {event.name}")

                    sets_count = 0
                    if event.sets:
                        sets_count = len(event.sets.nodes)
                    log(f"📊 Found {sets_count} sets")

                    # Log some sample sets to see what states they have
                    if sets_count > 0 and event.sets:
                        for i, set_data in enumerate(
                            event.sets.nodes[:5]
                        ):  # First 5 sets
                            player1 = "TBD"
                            player2 = "TBD"

                            if len(set_data.slots) >= 2:
                                # Player 1
                                if (
                                    set_data.slots[0].entrant
                                    and set_data.slots[0].entrant.participants
                                    and len(set_data.slots[0].entrant.participants) > 0
                                ):
                                    player1 = (
                                        set_data.slots[0]
                                        .entrant.participants[0]
                                        .gamerTag
                                    )

                                # Player 2
                                if (
                                    set_data.slots[1].entrant
                                    and set_data.slots[1].entrant.participants
                                    and len(set_data.slots[1].entrant.participants) > 0
                                ):
                                    player2 = (
                                        set_data.slots[1]
                                        .entrant.participants[0]
                                        .gamerTag
                                    )

                            log(
                                f"📋 Sample set {i+1}: {player1} vs {player2} - State: "
                                f"{set_data.state} - Round: {set_data.fullRoundText or 'N/A'}"
                            )

                    return self.parse_api_response(api_response)

        except Exception as e:
            log(f"❌ API Error: {type(e).__name__}: {e}")
            log("🔄 Falling back to mock data...")
            # Return mock data on error so the display still works
            return MOCK_TOURNAMENT_DATA

    def parse_api_response(self, api_response: StartGGAPIResponse) -> TournamentState:
        """Parse the start.gg API response into our format"""
        try:
            # Validate we have the expected response structure
            if not api_response.data or not isinstance(
                api_response.data, StartGGEventSetsResponse
            ):
                raise Exception("Invalid API response structure")

            if not api_response.data.event:
                raise Exception("No event data in response")

            event = api_response.data.event
            event_name = event.name
            tournament_name = "Unknown Tournament"
            if event.tournament:
                tournament_name = event.tournament.name

            sets_data = []
            if event.sets:
                sets_data = event.sets.nodes

            parsed_sets: list[MatchData] = []
            total_sets = len(sets_data)
            skipped_tbd_count = 0
            log(f"🔍 Processing {total_sets} sets from API")

            for set_data in sets_data:
                # Extract player names from slots
                player1_name = "TBD"
                player2_name = "TBD"

                if len(set_data.slots) >= 2:
                    # Player 1
                    slot1 = set_data.slots[0]
                    if (
                        slot1.entrant
                        and slot1.entrant.participants
                        and len(slot1.entrant.participants) > 0
                    ):
                        player1_name = slot1.entrant.participants[0].gamerTag

                    # Player 2
                    slot2 = set_data.slots[1]
                    if (
                        slot2.entrant
                        and slot2.entrant.participants
                        and len(slot2.entrant.participants) > 0
                    ):
                        player2_name = slot2.entrant.participants[0].gamerTag

                # Create bracket name from phase and round info
                bracket_name = "Unknown Bracket"
                pool_name = "Unknown Pool"

                if set_data.phaseGroup:
                    phase_group = set_data.phaseGroup

                    # Get pool/group identifier and format it nicely
                    if phase_group.displayIdentifier:
                        raw_identifier = phase_group.displayIdentifier
                        # Format pool names nicely
                        if raw_identifier.isdigit():
                            pool_name = f"Pool {raw_identifier}"
                        elif raw_identifier.isalpha() and len(raw_identifier) == 1:
                            pool_name = f"Pool {raw_identifier.upper()}"
                        else:
                            pool_name = raw_identifier

                    # Get phase name for bracket
                    if phase_group.phase and phase_group.phase.name:
                        phase_name = phase_group.phase.name
                        bracket_name = phase_name

                # Add round information to bracket name
                if set_data.fullRoundText:
                    bracket_name += f" - {set_data.fullRoundText}"
                elif set_data.identifier:
                    bracket_name += f" - {set_data.identifier}"
                elif set_data.round:
                    bracket_name += f" - Round {set_data.round}"

                # Skip matches where both players are TBD (not yet determined)
                if player1_name == "TBD" or player2_name == "TBD":
                    skipped_tbd_count += 1
                    log(f"⏭️  Skipping TBD match: {player1_name} vs {player2_name}")
                    continue

                parsed_set: MatchData = MatchData(
                    id=set_data.id,
                    display_name=bracket_name,
                    displayName=bracket_name,
                    poolName=pool_name,
                    phase_group=pool_name,
                    phase_name=pool_name,
                    player1=PlayerData(tag=player1_name, id=None),
                    player2=PlayerData(tag=player2_name, id=None),
                    state=set_data.state,
                    created_at=None,
                    started_at=set_data.startedAt,
                    completed_at=None,
                    updated_at=set_data.updatedAt or int(time.time()),
                    updatedAt=set_data.updatedAt or int(time.time()),
                    startedAt=set_data.startedAt,
                    entrant1_source=None,
                    entrant2_source=None,
                    station=(
                        str(set_data.station.number) if set_data.station else None
                    ),
                    stream=(set_data.stream.streamName if set_data.stream else None),
                    _simulation_context=None,
                )
                parsed_sets.append(parsed_set)
                log(
                    f"📋 Parsed set: {player1_name} vs {player2_name} ({bracket_name}) - State: {set_data.state}"
                )

            result: TournamentState = TournamentState(
                event_name=event_name,
                tournament_name=tournament_name,
                sets=parsed_sets,
            )
            log(f"✅ Successfully parsed {len(parsed_sets)} sets")
            log(
                f"📊 Total sets from API: {total_sets}, Skipped TBD vs TBD: "
                f"{skipped_tbd_count}, Included: {len(parsed_sets)}"
            )
            return result

        except Exception as e:
            log(f"❌ Error parsing API response: {e}")
            return MOCK_TOURNAMENT_DATA

    async def get_event_id_from_slug(self, event_slug: str) -> str | None:
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

                    raw_data = await response.json()
                    log(f"🔍 Event ID response: {raw_data}")

                    # Parse and validate the response with Pydantic
                    try:
                        api_response = StartGGAPIResponse(**raw_data)
                    except Exception as e:
                        log(f"❌ Pydantic validation error for event ID: {e}")
                        return None

                    if api_response.errors:
                        log(
                            f"❌ GraphQL Errors getting event ID: {api_response.errors}"
                        )
                        return None

                    if not api_response.data or not isinstance(
                        api_response.data, StartGGEventBySlugResponse
                    ):
                        log("❌ Invalid response structure for event lookup")
                        return None

                    if not api_response.data.event:
                        log(f"❌ No event found for slug: {event_slug}")
                        log(
                            "💡 Slug format should be: tournament/tournament-name/event/event-name"
                        )
                        log("💡 Example: tournament/evo-2023/event/street-fighter-6")
                        log("💡 Or try finding the correct slug from the start.gg URL")
                        return None

                    event = api_response.data.event
                    event_id = str(event.id) if event.id else None
                    event_name = event.name

                    if not event_id:
                        log("❌ Event found but no ID available")
                        return None

                    log(f"✅ Found event: {event_name} (ID: {event_id})")
                    return event_id

        except Exception as e:
            log(f"❌ Error getting event ID: {type(e).__name__}: {e}")
            return None
