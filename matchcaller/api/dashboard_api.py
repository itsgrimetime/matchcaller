"""Dashboard-oriented start.gg API coordinator."""

from __future__ import annotations

from datetime import UTC, datetime
import re
import time
from typing import Any, Mapping

import aiohttp

from matchcaller.models.dashboard import (
    DashboardState,
    LadderDisplayStatus,
    LadderStanding,
    LadderState,
    Station,
    ViewMode,
    derive_ladder_display_status,
    derive_station_state,
    resolve_dashboard_view,
)
from matchcaller.models.match import MatchData, MatchRow, PlayerData, TournamentState
from matchcaller.utils.logging import log

from .parsers import parse_event_sets_response, validate_startgg_response
from .queries import (
    EVENT_ID_BY_SLUG_QUERY,
    EVENT_SETS_QUERY,
    LADDER_EVENT_DETAIL_QUERY,
    TOURNAMENT_DASHBOARD_EVENTS_QUERY,
    TOURNAMENT_STATIONS_QUERY,
)
from .transport import AiohttpTransport, HTTPTransport


STARTGG_GRAPHQL_URL = "https://api.start.gg/gql/alpha"


def derive_tournament_slug_from_event_slug(event_slug: str | None) -> str | None:
    """Extract the tournament slug from a start.gg event slug."""
    if not event_slug:
        return None
    match = re.match(r"^tournament/([^/]+)/event/.+$", event_slug)
    if not match:
        return None
    return match.group(1)


class TournamentDashboardAPI:
    """Coordinate the GraphQL calls needed for the dashboard state."""

    def __init__(
        self,
        api_token: str | None = None,
        event_id: str | None = None,
        event_slug: str | None = None,
        tournament_slug: str | None = None,
        requested_view: ViewMode = ViewMode.AUTO,
        *,
        transport: HTTPTransport | None = None,
    ) -> None:
        self.api_token = api_token
        self.event_id = event_id
        self.event_slug = event_slug
        self.tournament_slug = (
            tournament_slug or derive_tournament_slug_from_event_slug(event_slug)
        )
        self.requested_view = requested_view
        self.base_url = STARTGG_GRAPHQL_URL
        self.transport = transport or AiohttpTransport()

    def _headers(self) -> dict[str, str]:
        """Build GraphQL request headers."""
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    async def fetch_dashboard_state(
        self,
        previous_state: DashboardState | None = None,
    ) -> DashboardState:
        """Fetch the main bracket, ladder, stations, and resolved dashboard view."""
        main = await self._fetch_main_state()
        ladder: LadderState | None = None

        if self.tournament_slug:
            ladder_summary = await self._discover_ladder_summary()
            if ladder_summary is None:
                ladder = LadderState(display_status=LadderDisplayStatus.NOT_FOUND)
            else:
                ladder = await self._fetch_ladder_state(ladder_summary)

        stations = None
        if self.tournament_slug:
            active_sets = list(main.sets)
            if ladder:
                active_sets.extend(ladder.sets)
            try:
                stations = await self._fetch_station_state(active_sets)
            except Exception as exc:
                log(f"Station state fetch failed; continuing without stations: {exc}")

        ladder_was_visible = bool(
            previous_state
            and (
                previous_state.ladder_was_visible
                or previous_state.resolved_view in {ViewMode.SPLIT, ViewMode.LADDER}
            )
        )
        resolved_view = resolve_dashboard_view(
            self.requested_view,
            ladder,
            ladder_was_visible=ladder_was_visible,
        )

        return DashboardState(
            tournament_name=main.tournament_name,
            main=main,
            ladder=ladder,
            stations=stations,
            requested_view=self.requested_view,
            resolved_view=resolved_view,
            ladder_was_visible=ladder_was_visible
            or resolved_view in {ViewMode.SPLIT, ViewMode.LADDER},
            last_update=datetime.now(UTC).isoformat(),
        )

    async def _post_graphql(
        self,
        query: str,
        variables: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Post a GraphQL request and return a validated JSON object."""
        response = await self.transport.post_json(
            self.base_url,
            payload={"query": query, "variables": dict(variables)},
            headers=self._headers(),
            timeout_seconds=10,
        )
        if response.status != 200:
            error_text = response.text or str(response.json_data)
            raise aiohttp.ClientError(f"HTTP {response.status}: {error_text}")
        if not isinstance(response.json_data, dict):
            raise ValueError("Expected JSON object from start.gg API")
        if response.json_data.get("errors"):
            raise RuntimeError(f"GraphQL errors: {response.json_data['errors']}")
        return response.json_data

    async def _fetch_main_state(self) -> TournamentState:
        """Fetch the primary event state via the existing event-sets parser."""
        if self.event_slug and not self.event_id:
            self.event_id = await self._resolve_event_id_from_slug(self.event_slug)

        event_id = self.event_id
        if not event_id:
            raise ValueError("Missing event_id or unresolved event_slug for dashboard API")

        raw_data = await self._post_graphql(
            EVENT_SETS_QUERY,
            {"eventId": event_id, "page": 1, "perPage": 100},
        )
        return parse_event_sets_response(validate_startgg_response(raw_data))

    async def _resolve_event_id_from_slug(self, event_slug: str) -> str | None:
        """Resolve an event slug to its numeric start.gg event ID."""
        raw_data = await self._post_graphql(EVENT_ID_BY_SLUG_QUERY, {"slug": event_slug})
        event = (raw_data.get("data") or {}).get("event")
        if not isinstance(event, dict) or not event.get("id"):
            return None
        return str(event["id"])

    async def _discover_ladder_summary(self) -> dict[str, Any] | None:
        """Find the first tournament event that looks like a matchmaking ladder."""
        if not self.tournament_slug:
            return None

        raw_data = await self._post_graphql(
            TOURNAMENT_DASHBOARD_EVENTS_QUERY,
            {"slug": self.tournament_slug},
        )
        tournament = (raw_data.get("data") or {}).get("tournament") or {}
        events = tournament.get("events") or []
        return next(
            (
                event
                for event in events
                if isinstance(event, dict) and _is_ladder_event(event)
            ),
            None,
        )

    async def _fetch_ladder_state(self, event_summary: Mapping[str, Any]) -> LadderState:
        """Fetch and parse ladder sets and standings for one ladder event."""
        event_slug = event_summary.get("slug")
        if not event_slug:
            return LadderState(display_status=LadderDisplayStatus.NOT_FOUND)

        raw_data = await self._post_graphql(
            LADDER_EVENT_DETAIL_QUERY,
            {"slug": event_slug, "page": 1, "perPage": 100},
        )
        event = (raw_data.get("data") or {}).get("event")
        if not isinstance(event, dict):
            return LadderState(display_status=LadderDisplayStatus.NOT_FOUND)

        set_nodes = ((event.get("sets") or {}).get("nodes") or [])
        sets = [
            parsed_set
            for node in set_nodes
            if isinstance(node, dict)
            if (parsed_set := _parse_ladder_match(node)) is not None
        ]
        standings = [
            standing
            for node in ((event.get("standings") or {}).get("nodes") or [])
            if isinstance(node, dict)
            if (standing := _parse_ladder_standing(node)) is not None
        ]
        display_status = derive_ladder_display_status(event.get("state"), len(sets))

        return LadderState(
            display_status=display_status,
            event_id=event.get("id"),
            event_name=event.get("name"),
            event_slug=event.get("slug"),
            event_state=event.get("state"),
            start_at=event.get("startAt"),
            entrants_count=event.get("numEntrants") or 0,
            sets=sets,
            standings=standings,
            auto_should_show=display_status == LadderDisplayStatus.ACTIVE,
        )

    async def _fetch_station_state(self, active_sets: list[MatchData]):
        """Fetch tournament stations and derive occupied/available station numbers."""
        if not self.tournament_slug:
            return None

        raw_data = await self._post_graphql(
            TOURNAMENT_STATIONS_QUERY,
            {"slug": self.tournament_slug},
        )
        station_nodes = (
            ((raw_data.get("data") or {}).get("tournament") or {})
            .get("stations", {})
            .get("nodes", [])
        )
        stations = [
            Station(
                id=node["id"],
                number=node["number"],
                enabled=node.get("enabled"),
            )
            for node in station_nodes
            if isinstance(node, dict) and "id" in node and node.get("number") is not None
        ]
        return derive_station_state(stations, [MatchRow(match) for match in active_sets])


def _is_ladder_event(event: Mapping[str, Any]) -> bool:
    name = str(event.get("name") or "")
    if "ladder" not in name.lower():
        return False

    phases = event.get("phases") or []
    phase_groups = event.get("phaseGroups") or []
    if not phases and not phase_groups:
        return True

    return any(_has_matchmaking_type(item) for item in phases) or any(
        _has_matchmaking_type(item) or _has_matchmaking_type(item.get("phase") or {})
        for item in phase_groups
        if isinstance(item, dict)
    )


def _has_matchmaking_type(value: Any) -> bool:
    return (
        isinstance(value, Mapping)
        and str(value.get("bracketType") or "").upper() == "MATCHMAKING"
    )


def _parse_ladder_match(set_data: Mapping[str, Any]) -> MatchData | None:
    player1 = _extract_player(set_data, 0)
    player2 = _extract_player(set_data, 1)
    if player1.tag == "TBD" and player2.tag == "TBD":
        return None

    bracket_name, pool_name = _build_ladder_names(set_data)
    timestamp = set_data.get("updatedAt") or int(time.time())
    station = set_data.get("station") or {}
    stream = set_data.get("stream") or {}

    return MatchData(
        id=set_data["id"],
        display_name=bracket_name,
        displayName=bracket_name,
        poolName=pool_name,
        phase_group=pool_name,
        phase_name=pool_name,
        player1=player1,
        player2=player2,
        state=set_data.get("state") or 1,
        created_at=None,
        started_at=set_data.get("startedAt"),
        completed_at=None,
        updated_at=timestamp,
        updatedAt=timestamp,
        startedAt=set_data.get("startedAt"),
        entrant1_source=None,
        entrant2_source=None,
        station=station.get("number") if isinstance(station, dict) else None,
        stream=stream.get("streamName") if isinstance(stream, dict) else None,
        simulation_context=None,
    )


def _extract_player(set_data: Mapping[str, Any], slot_index: int) -> PlayerData:
    slots = set_data.get("slots") or []
    if len(slots) <= slot_index or not isinstance(slots[slot_index], dict):
        return PlayerData(tag="TBD")

    entrant = slots[slot_index].get("entrant")
    if not isinstance(entrant, dict):
        return PlayerData(tag="TBD")

    participants = entrant.get("participants") or []
    if not participants or not isinstance(participants[0], dict):
        return PlayerData(tag="TBD")

    participant = participants[0]
    discord_id = None
    discord_username = None
    user = participant.get("user")
    if isinstance(user, dict):
        authorizations = user.get("authorizations") or []
        if authorizations and isinstance(authorizations[0], dict):
            discord_id = authorizations[0].get("externalId")
            discord_username = authorizations[0].get("externalUsername")

    return PlayerData(
        tag=participant.get("gamerTag") or "TBD",
        discord_id=discord_id,
        discord_username=discord_username,
    )


def _build_ladder_names(set_data: Mapping[str, Any]) -> tuple[str, str]:
    phase_group = set_data.get("phaseGroup") or {}
    phase = phase_group.get("phase") or {}
    phase_name = phase.get("name") or "Ladder"
    bracket_name = phase_name

    display_identifier = phase_group.get("displayIdentifier")
    pool_name = (
        f"{phase_name} - Pool {display_identifier}"
        if display_identifier and str(display_identifier).isdigit()
        else f"{phase_name} - {display_identifier}" if display_identifier else phase_name
    )

    if set_data.get("fullRoundText"):
        bracket_name += f" - {set_data['fullRoundText']}"
    elif set_data.get("identifier"):
        bracket_name += f" - {set_data['identifier']}"
    elif set_data.get("round"):
        bracket_name += f" - Round {set_data['round']}"

    return bracket_name, pool_name


def _parse_ladder_standing(node: Mapping[str, Any]) -> LadderStanding | None:
    entrant = node.get("entrant") or {}
    if not isinstance(entrant, dict):
        return None

    entrant_name = entrant.get("name")
    participants = entrant.get("participants") or []
    if not entrant_name and participants and isinstance(participants[0], dict):
        entrant_name = participants[0].get("gamerTag")

    record = node.get("setRecordWithoutByes") or {}
    return LadderStanding(
        placement=node.get("placement") or 0,
        entrant_name=entrant_name or "Unknown",
        wins=record.get("wins") if isinstance(record, dict) else None,
        losses=record.get("losses") if isinstance(record, dict) else None,
        win_percentage=record.get("winPercentage") if isinstance(record, dict) else None,
    )
