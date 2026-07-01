"""Tournament API source that combines active sets from multiple events."""

from __future__ import annotations

from typing import Iterable

from ..models.match import MatchData, TournamentState
from ..utils.logging import log
from .tournament_api import TournamentAPI
from .transport import AiohttpTransport, HTTPTransport


DOUBLES_KEYWORDS = ("doubles", "teams", "2v2")
SINGLES_KEYWORDS = ("singles",)
IGNORED_EVENT_KEYWORDS = ("waitlist", "ladder", "redemption", "staging")


class MultiEventTournamentAPI:
    """Fetch active matches across the singles/doubles events in one tournament."""

    def __init__(
        self,
        api_token: str,
        tournament_slug: str,
        *,
        transport: HTTPTransport | None = None,
    ) -> None:
        self.api_token = api_token
        self.tournament_slug = tournament_slug
        self.base_url = "https://api.start.gg/gql/alpha"
        self.transport = transport or AiohttpTransport()
        self._event_api = TournamentAPI(
            api_token=api_token,
            transport=self.transport,
        )

    async def fetch_sets(self) -> TournamentState:
        """Fetch and combine active sets from relevant tournament events."""
        events = await self._event_api.get_events_for_tournament(self.tournament_slug)
        selected_events = select_main_events(events)
        if not selected_events:
            return TournamentState(
                event_name="No events found",
                tournament_name=self.tournament_slug,
                sets=[],
            )

        log(
            "🔍 Multi-event auto source selected events: "
            + ", ".join(event["name"] for event in selected_events)
        )

        active_states: list[tuple[dict[str, str], TournamentState]] = []
        last_tournament_name = self.tournament_slug
        for event in selected_events:
            try:
                event_api = TournamentAPI(
                    api_token=self.api_token,
                    event_id=event.get("id"),
                    event_slug=event.get("slug"),
                    transport=self.transport,
                )
                state = await event_api.fetch_sets()
            except Exception as exc:
                log(
                    f"⚠️  Could not fetch event {event.get('name', 'unknown')}: "
                    f"{type(exc).__name__}: {exc}"
                )
                continue

            last_tournament_name = state.tournament_name or last_tournament_name
            if state.sets:
                active_states.append((event, state))

        combined_sets: list[MatchData] = []
        active_event_names: list[str] = []
        for event, state in active_states:
            active_event_names.append(event["name"])
            combined_sets.extend(
                prefix_sets_for_event(state.sets, event_name=event["name"])
            )

        event_name = (
            " + ".join(active_event_names)
            if active_event_names
            else "No active singles/doubles matches"
        )
        return TournamentState(
            event_name=event_name,
            tournament_name=last_tournament_name,
            sets=combined_sets,
        )


def select_main_events(events: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    """Select doubles plus singles/main bracket events from tournament events."""
    all_events = list(events)
    viable_events = [
        event for event in all_events
        if not _has_any_keyword(event, IGNORED_EVENT_KEYWORDS)
    ]
    if not viable_events:
        viable_events = all_events

    doubles_events = [
        event for event in viable_events
        if _has_any_keyword(event, DOUBLES_KEYWORDS)
    ]
    singles_events = [
        event for event in viable_events
        if _has_any_keyword(event, SINGLES_KEYWORDS)
    ]

    selected: list[dict[str, str]] = []
    selected.extend(doubles_events[:1])
    if singles_events:
        selected.extend(singles_events[:1])
    else:
        selected_slugs = {
            selected_event.get("slug") for selected_event in selected
        }
        selected.extend(
            event
            for event in viable_events[:1]
            if event.get("slug") not in selected_slugs
        )

    return selected


def prefix_sets_for_event(
    sets: Iterable[MatchData],
    *,
    event_name: str,
) -> list[MatchData]:
    """Prefix pool names so singles and doubles pools do not collapse together."""
    return [
        set_data.model_copy(
            update={
                "poolName": _event_prefixed_label(event_name, set_data.poolName),
                "phase_group": _event_prefixed_label(
                    event_name,
                    set_data.phase_group,
                ),
                "phase_name": _event_prefixed_label(event_name, set_data.phase_name),
            }
        )
        for set_data in sets
    ]


def _event_prefixed_label(event_name: str, value: str | None) -> str:
    label = value or "Unknown Pool"
    if label.lower().startswith(event_name.lower()):
        return label
    return f"{event_name} - {label}"


def _has_any_keyword(event: dict[str, str], keywords: tuple[str, ...]) -> bool:
    haystack = f"{event.get('name', '')} {event.get('slug', '')}".lower()
    return any(keyword in haystack for keyword in keywords)
