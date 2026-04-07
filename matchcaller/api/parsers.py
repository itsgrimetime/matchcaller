"""Pure parsers for start.gg transport responses."""

import time
from typing import Any

from ..models.match import MatchData, PlayerData, TournamentState
from ..models.mock_data import MOCK_TOURNAMENT_DATA
from ..models.startgg_api import (
    StartGGAPIResponse,
    StartGGEventSetsResponse,
    StartGGPhaseGroup,
    StartGGSet,
)


def validate_startgg_response(raw_data: dict[str, Any]) -> StartGGAPIResponse:
    """Validate raw GraphQL JSON against the Pydantic response models."""
    return StartGGAPIResponse(**raw_data)


def parse_event_sets_response(
    api_response: StartGGAPIResponse,
    *,
    fallback_to_mock: bool = False,
) -> TournamentState:
    """Parse the start.gg event-sets response into application state."""
    try:
        response = _require_event_sets_response(api_response)
        event = response.event
        if event is None:
            raise Exception("No event data in response")

        event_name = event.name
        tournament_name = event.tournament.name if event.tournament else "Unknown Tournament"
        sets_data = event.sets.nodes if event.sets else []

        parsed_sets = [
            parsed_set
            for set_data in sets_data
            if (parsed_set := _parse_set(set_data)) is not None
        ]

        return TournamentState(
            event_name=event_name,
            tournament_name=tournament_name,
            sets=parsed_sets,
        )
    except Exception:
        if fallback_to_mock:
            return MOCK_TOURNAMENT_DATA
        raise


def extract_event_id(api_response: StartGGAPIResponse) -> str | None:
    """Extract an event ID from a validated start.gg response."""
    if api_response.errors:
        return None
    if not api_response.data or not hasattr(api_response.data, "event"):
        return None
    event = api_response.data.event
    if not event or not event.id:
        return None
    return str(event.id)


def parse_tournament_events_payload(raw_data: dict[str, Any]) -> list[dict[str, str]]:
    """Parse the tournament-events payload into simple event summaries."""
    if raw_data.get("errors"):
        return []

    tournament = (raw_data.get("data") or {}).get("tournament")
    if not tournament:
        return []

    return [
        {
            "id": str(event["id"]),
            "name": event.get("name", ""),
            "slug": event.get("slug", ""),
        }
        for event in (tournament.get("events") or [])
    ]


def _require_event_sets_response(
    api_response: StartGGAPIResponse,
) -> StartGGEventSetsResponse:
    """Require an event-sets response payload and raise on invalid structure."""
    if api_response.errors:
        raise Exception(f"GraphQL errors: {api_response.errors}")
    if not api_response.data:
        raise Exception("No data field in API response")
    if not isinstance(api_response.data, StartGGEventSetsResponse):
        raise Exception("Expected StartGGEventSetsResponse")
    if not api_response.data.event:
        raise Exception("No event data in response")
    return api_response.data


def _parse_set(set_data: StartGGSet) -> MatchData | None:
    """Parse a single start.gg set into app match data."""
    player1 = _extract_player(set_data, 0)
    player2 = _extract_player(set_data, 1)

    if player1.tag == "TBD" and player2.tag == "TBD":
        return None

    bracket_name, pool_name = _build_names(set_data)
    timestamp = set_data.updatedAt or int(time.time())

    return MatchData(
        id=set_data.id,
        display_name=bracket_name,
        displayName=bracket_name,
        poolName=pool_name,
        phase_group=pool_name,
        phase_name=pool_name,
        player1=player1,
        player2=player2,
        state=set_data.state,
        created_at=None,
        started_at=set_data.startedAt,
        completed_at=None,
        updated_at=timestamp,
        updatedAt=timestamp,
        startedAt=set_data.startedAt,
        entrant1_source=None,
        entrant2_source=None,
        station=set_data.station.number if set_data.station else None,
        stream=set_data.stream.streamName if set_data.stream else None,
        simulation_context=None,
    )


def _extract_player(set_data: StartGGSet, slot_index: int) -> PlayerData:
    """Extract participant and Discord-link data from a set slot."""
    if len(set_data.slots) <= slot_index:
        return PlayerData(tag="TBD")

    slot = set_data.slots[slot_index]
    if not slot.entrant or not slot.entrant.participants:
        return PlayerData(tag="TBD")

    participant = slot.entrant.participants[0]
    discord_id: str | None = None
    discord_username: str | None = None
    if participant.user and participant.user.authorizations:
        authorization = participant.user.authorizations[0]
        discord_id = authorization.externalId
        discord_username = authorization.externalUsername

    return PlayerData(
        tag=participant.gamerTag,
        id=None,
        discord_id=discord_id,
        discord_username=discord_username,
    )


def _build_names(set_data: StartGGSet) -> tuple[str, str]:
    """Build the bracket and pool display names for a set."""
    bracket_name = "Unknown Bracket"
    pool_name = "Unknown Pool"

    if set_data.phaseGroup:
        bracket_name, pool_name = _names_from_phase_group(set_data.phaseGroup)

    if set_data.fullRoundText:
        bracket_name += f" - {set_data.fullRoundText}"
    elif set_data.identifier:
        bracket_name += f" - {set_data.identifier}"
    elif set_data.round:
        bracket_name += f" - Round {set_data.round}"

    return bracket_name, pool_name


def _names_from_phase_group(phase_group: StartGGPhaseGroup) -> tuple[str, str]:
    """Build bracket and pool names from phase-group metadata."""
    phase_name = phase_group.phase.name if phase_group.phase and phase_group.phase.name else ""
    bracket_name = phase_name or "Unknown Bracket"
    pool_name = "Unknown Pool"

    if phase_group.displayIdentifier:
        identifier = _format_pool_identifier(phase_group.displayIdentifier)
        pool_name = f"{phase_name} - {identifier}" if phase_name else identifier
    elif phase_name:
        pool_name = phase_name

    return bracket_name, pool_name


def _format_pool_identifier(raw_identifier: str) -> str:
    """Format pool/group identifiers consistently for display."""
    if raw_identifier.isdigit():
        return f"Pool {raw_identifier}"
    if raw_identifier.isalpha() and len(raw_identifier) == 1:
        return f"Pool {raw_identifier.upper()}"
    return raw_identifier
