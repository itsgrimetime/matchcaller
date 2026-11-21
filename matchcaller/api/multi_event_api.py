"""Tournament API source that combines active sets from multiple events."""

from __future__ import annotations

from typing import Iterable

from ..models.match import MatchData, TournamentState
from ..utils.logging import log
from .tournament_api import TournamentAPI
from .transport import AiohttpTransport, HTTPTransport


DOUBLES_KEYWORDS = ("doubles", "teams", "2v2")
SINGLES_KEYWORDS = ("singles",)
AMATEUR_KEYWORDS = ("amateur", "ammy", "redemption")
IGNORED_EVENT_KEYWORDS = ("waitlist", "ladder", "staging")


class MultiEventTournamentAPI:
    """Fetch active singles, doubles, and amateur matches in one tournament."""

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
        finals_pending = False
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
            finals_pending = finals_pending or state.finals_pending
            if state.sets:
                active_states.append((event, state))

        combined_sets: list[MatchData] = []
        active_event_names: list[str] = []
        for event, state in active_states:
            active_event_names.append(event["name"])
            combined_sets.extend(
                prefix_sets_for_event(
                    state.sets,
                    event_name=event["name"],
                    qualify_pool_labels=len(selected_events) > 1,
                )
            )

        event_name = (
            " + ".join(active_event_names)
            if active_event_names
            else "No active singles/doubles/amateur matches"
        )
        return TournamentState(
            event_name=event_name,
            tournament_name=last_tournament_name,
            sets=combined_sets,
            finals_pending=finals_pending,
        )


def select_main_events(events: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    """Select the main singles/doubles events plus any amateur brackets."""
    viable_events = [
        event for event in events
        if not _has_any_keyword(event, IGNORED_EVENT_KEYWORDS)
    ]
    amateur_events = [
        event for event in viable_events
        if _has_any_keyword(event, AMATEUR_KEYWORDS)
    ]
    main_events = [event for event in viable_events if event not in amateur_events]

    doubles_events = [
        event for event in main_events
        if _has_any_keyword(event, DOUBLES_KEYWORDS)
    ]
    singles_events = [
        event for event in main_events
        if _has_any_keyword(event, SINGLES_KEYWORDS)
    ]

    # Doubles-only tournaments may have more than one bracket or time slot.
    selected = doubles_events[:1] if singles_events else doubles_events
    for event in (singles_events[:1] or main_events[:1]) + amateur_events:
        if event not in selected:
            selected.append(event)

    return selected


def prefix_sets_for_event(
    sets: Iterable[MatchData],
    *,
    event_name: str,
    qualify_pool_labels: bool = True,
) -> list[MatchData]:
    """Prefix pool names so different events' pools do not collapse together."""
    return [
        set_data.model_copy(
            update={
                "poolName": _event_prefixed_label(event_name, set_data.poolName),
                "pool_label": (
                    f"{set_data.pool_label} - {event_name}"
                    if set_data.pool_label and qualify_pool_labels
                    else set_data.pool_label
                ),
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
    event_slug = event.get("slug", "").split("/event/")[-1]
    haystack = f"{event.get('name', '')} {event_slug}".lower()
    return any(keyword in haystack for keyword in keywords)
