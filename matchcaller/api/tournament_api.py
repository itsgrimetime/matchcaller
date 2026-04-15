"""Tournament API client for start.gg GraphQL API."""

import asyncio
import json
import re
import time

from ..models.match import TournamentState
from ..models.mock_data import MOCK_TOURNAMENT_DATA
from ..models.startgg_api import StartGGAPIResponse, StartGGEventSetsResponse, StartGGSet
from .parsers import (
    extract_event_id,
    parse_event_sets_response,
    parse_tournament_events_payload,
    validate_startgg_response,
)
from .event_sets import fetch_event_sets_payload
from .queries import (
    EVENT_ID_BY_SLUG_QUERY,
    TOURNAMENT_EVENTS_QUERY,
    TOURNAMENT_SEARCH_QUERY,
)
from .transport import AiohttpTransport, HTTPTransport
from ..utils.logging import log


_ABBEY_NAME_RE = re.compile(r"^Melee @ Abbey Tavern #\d+$", re.IGNORECASE)
_ABBEY_SLUG_RE = re.compile(r"^(?:tournament/)?(melee-abbey-tavern-\d+)$", re.IGNORECASE)


def _parse_abbey_search_candidate(
    node: dict,
    now: int,
) -> tuple[tuple[int, int], str, str] | None:
    """Parse and rank a tournament search result if it is an Abbey weekly."""
    name = str(node.get("name") or "")
    slug = str(node.get("slug") or "")
    slug_match = _ABBEY_SLUG_RE.match(slug)
    if not _ABBEY_NAME_RE.match(name) and slug_match is None:
        return None

    start_at = node.get("startAt")
    if not isinstance(start_at, int):
        return None

    tournament_slug = slug_match.group(1) if slug_match else slug.removeprefix("tournament/")
    # Prefer the closest date; if two are equally close, prefer the future event.
    rank = (abs(start_at - now), 0 if start_at >= now else 1)
    return rank, tournament_slug, name or tournament_slug


class TournamentAPI:
    """Handle API calls to start.gg"""

    def __init__(
        self,
        api_token: str | None = None,
        event_id: str | None = None,
        event_slug: str | None = None,
        *,
        transport: HTTPTransport | None = None,
    ):
        self.api_token: str | None = api_token
        self.event_id: str | None = event_id
        self.event_slug: str | None = event_slug  # New: accept event slug
        self.base_url: str = "https://api.start.gg/gql/alpha"
        self.transport = transport or AiohttpTransport()

    def _headers(self) -> dict[str, str]:
        """Build GraphQL request headers."""
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _log_sample_sets(sets: list[StartGGSet]) -> None:
        """Log a few sample sets for debugging tournament state mapping."""
        for index, set_data in enumerate(sets[:5]):
            player1 = "TBD"
            player2 = "TBD"

            if len(set_data.slots) >= 2:
                slot1 = set_data.slots[0]
                if slot1.entrant and slot1.entrant.participants:
                    player1 = slot1.entrant.participants[0].gamerTag

                slot2 = set_data.slots[1]
                if slot2.entrant and slot2.entrant.participants:
                    player2 = slot2.entrant.participants[0].gamerTag

            log(
                f"📋 Sample set {index + 1}: {player1} vs {player2} - State: "
                f"{set_data.state} - Round: {set_data.fullRoundText or 'N/A'}"
            )

    async def fetch_sets(self) -> TournamentState:
        """Fetch tournament sets from start.gg API"""
        log(f"🔍 API Token: {'present' if self.api_token else 'None'}")
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
                if not self.api_token:
                    return MOCK_TOURNAMENT_DATA
                else:
                    raise Exception(
                        "Could not resolve event ID from slug - check if slug is correct"
                    )
            log(f"✅ Got event ID: {self.event_id}")

        if not self.event_id:
            log("⚠️  Missing event ID - using mock data")
            if not self.api_token:
                return MOCK_TOURNAMENT_DATA
            else:
                raise Exception(
                    "Missing event ID - provide either event_id or event_slug parameter"
                )

        try:
            log(f"🔍 Fetching data for event ID: {self.event_id}")
            raw_data = await fetch_event_sets_payload(
                transport=self.transport,
                base_url=self.base_url,
                headers=self._headers(),
                event_id=self.event_id,
                timeout_seconds=10,
            )
            log(f"🔍 Raw API response keys: {list(raw_data.keys())}")

            # Parse and validate the response with Pydantic
            try:
                api_response = validate_startgg_response(raw_data)
            except Exception as e:
                log(f"❌ Pydantic validation error: {e}")
                log(f"📋 Raw response: {json.dumps(raw_data, indent=2)[:500]}...")
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
                self._log_sample_sets(event.sets.nodes)

            return parse_event_sets_response(api_response)

        except Exception as e:
            log(f"❌ API Error: {type(e).__name__}: {e}")
            # Only fall back to mock data if no API token was provided
            # If the user provided an API token, they want real data - don't show mock
            if not self.api_token:
                log("🔄 Falling back to mock data (no API token provided)...")
                return MOCK_TOURNAMENT_DATA
            else:
                log(
                    "🔄 No fallback to mock data - re-raising exception to preserve existing display"
                )
                raise e

    def parse_api_response(self, api_response: StartGGAPIResponse) -> TournamentState:
        """Parse the start.gg API response into our format"""
        try:
            return parse_event_sets_response(
                api_response,
                fallback_to_mock=not self.api_token,
            )
        except Exception as e:
            log(f"❌ Error parsing API response: {e}")
            raise

    async def get_events_for_tournament(self, tournament_slug: str) -> list[dict[str, str]]:
        """Get all events for a tournament slug (e.g., 'melee-abbey-tavern-122').

        Returns a list of dicts with 'id', 'name', and 'slug' keys.
        """
        variables = {"slug": tournament_slug}

        try:
            log(f"🔍 Fetching events for tournament: {tournament_slug}")
            response = await self.transport.post_json(
                self.base_url,
                payload={"query": TOURNAMENT_EVENTS_QUERY, "variables": variables},
                headers=self._headers(),
                timeout_seconds=10,
            )
            if response.status != 200:
                error_text = response.text or str(response.json_data)
                log(f"❌ HTTP Error fetching events: {error_text}")
                return []

            if not isinstance(response.json_data, dict):
                log("❌ Tournament events endpoint returned a non-JSON response")
                return []

            raw_data = response.json_data
            result = parse_tournament_events_payload(raw_data)
            if not result:
                if raw_data.get("errors"):
                    log(f"❌ GraphQL errors: {raw_data['errors']}")
                else:
                    log(f"❌ No tournament found for slug: {tournament_slug}")
                return []

            tournament = (raw_data.get("data") or {}).get("tournament") or {}
            log(
                f"✅ Found {len(result)} events for {tournament.get('name', tournament_slug)}"
            )
            for ev in result:
                log(f"   - {ev['name']} (slug: {ev['slug']})")
            return result

        except Exception as e:
            log(f"❌ Error fetching tournament events: {type(e).__name__}: {e}")
            return []

    async def find_nearest_abbey_tournament_slug(
        self,
        *,
        now: int | None = None,
        day_window: int = 30,
    ) -> str | None:
        """Find the Abbey weekly tournament slug nearest to now via GraphQL search."""
        if now is None:
            now = int(time.time())
        variables = {
            "name": "abbey",
            "after": now - day_window * 24 * 60 * 60,
            "before": now + day_window * 24 * 60 * 60,
        }

        try:
            log(
                "🔍 Searching start.gg API for nearest Melee @ Abbey Tavern "
                f"tournament within ±{day_window} days"
            )
            response = await self.transport.post_json(
                self.base_url,
                payload={"query": TOURNAMENT_SEARCH_QUERY, "variables": variables},
                headers=self._headers(),
                timeout_seconds=10,
            )
            if response.status != 200:
                error_text = response.text or str(response.json_data)
                log(f"❌ HTTP Error searching tournaments: {error_text}")
                return None

            if not isinstance(response.json_data, dict):
                log("❌ Tournament search endpoint returned a non-JSON response")
                return None

            raw_data = response.json_data
            if raw_data.get("errors"):
                log(f"❌ GraphQL errors searching tournaments: {raw_data['errors']}")
                return None

            nodes = (
                ((raw_data.get("data") or {}).get("tournaments") or {}).get("nodes")
                or []
            )
            candidates = [
                candidate
                for node in nodes
                if (candidate := _parse_abbey_search_candidate(node, now)) is not None
            ]
            if not candidates:
                log("❌ No Melee @ Abbey Tavern tournament candidates found")
                return None

            candidates.sort(key=lambda candidate: candidate[0])
            _, tournament_slug, tournament_name = candidates[0]
            log(f"✅ Found nearest Abbey tournament: {tournament_name} ({tournament_slug})")
            return tournament_slug

        except Exception as e:
            log(f"❌ Error searching Abbey tournaments: {type(e).__name__}: {e}")
            return None

    async def get_event_id_from_slug(self, event_slug: str) -> str | None:
        """Get event ID from event slug (e.g., 'tournament/the-c-stick-55/event/melee-singles')"""

        # Auto-fix common slug format issues
        if not event_slug.startswith("tournament/"):
            log(f"🔧 Slug missing 'tournament/' prefix, fixing: {event_slug}")
            event_slug = f"tournament/{event_slug}"
            log(f"🔧 Fixed slug: {event_slug}")

        log(f"🔍 Using event slug: {event_slug}")
        variables = {"slug": event_slug}

        try:
            log(f"🔍 Fetching event ID for slug: {event_slug}")
            response = await self.transport.post_json(
                self.base_url,
                payload={"query": EVENT_ID_BY_SLUG_QUERY, "variables": variables},
                headers=self._headers(),
                timeout_seconds=10,
            )
            log(f"📡 Event ID API Response Status: {response.status}")

            if response.status != 200:
                error_text = response.text or str(response.json_data)
                log(f"❌ HTTP Error getting event ID: {error_text}")
                return None

            if not isinstance(response.json_data, dict):
                log("❌ Event ID endpoint returned a non-JSON response")
                return None

            raw_data = response.json_data
            log(f"🔍 Event ID response: {raw_data}")

            # Parse and validate the response with Pydantic
            try:
                api_response = validate_startgg_response(raw_data)
            except Exception as e:
                log(f"❌ Pydantic validation error for event ID: {e}")
                return None

            log(f"🔍 API response: {api_response}")

            if api_response.errors:
                log(f"❌ GraphQL Errors getting event ID: {api_response.errors}")
                return None

            event_id = extract_event_id(api_response)
            if not event_id:
                log(f"❌ No event found for slug: {event_slug}")
                log(
                    "💡 Slug format should be: tournament/tournament-name/event/event-name"
                )
                log("💡 Example: tournament/evo-2023/event/street-fighter-6")
                log("💡 Or try finding the correct slug from the start.gg URL")
                return None

            event = api_response.data.event
            event_name = event.name

            log(f"✅ Found event: {event_name} (ID: {event_id})")
            return event_id

        except Exception as e:
            log(f"❌ Error getting event ID: {type(e).__name__}: {e}")
            return None
