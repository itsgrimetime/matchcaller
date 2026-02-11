"""Pydantic models for start.gg API responses."""

from ..models.match import DictCompatibleBaseModel


class StartGGAuthorization(DictCompatibleBaseModel):
    """A linked account authorization (Discord, Twitch, etc.)"""

    externalUsername: str | None = None
    externalId: str | None = None


class StartGGUser(DictCompatibleBaseModel):
    """A start.gg user account"""

    authorizations: list[StartGGAuthorization] | None = None


class StartGGParticipant(DictCompatibleBaseModel):
    """A participant in a tournament (player)"""

    gamerTag: str
    user: StartGGUser | None = None


class StartGGEntrant(DictCompatibleBaseModel):
    """An entrant in a set (can have multiple participants for teams)"""

    participants: list[StartGGParticipant]


class StartGGSlot(DictCompatibleBaseModel):
    """A slot in a set (position for an entrant)"""

    entrant: StartGGEntrant | None = None


class StartGGPhase(DictCompatibleBaseModel):
    """A phase in a tournament (e.g., pools, top 8)"""

    name: str


class StartGGPhaseGroup(DictCompatibleBaseModel):
    """A phase group (e.g., Pool A, Pool B)"""

    displayIdentifier: str | None = None
    phase: StartGGPhase | None = None


class StartGGStation(DictCompatibleBaseModel):
    """A tournament station"""

    number: int


class StartGGStream(DictCompatibleBaseModel):
    """A tournament stream"""

    streamName: str


class StartGGSet(DictCompatibleBaseModel):
    """A set/match in a tournament"""

    id: str | int
    fullRoundText: str | None = None
    identifier: str | None = None
    state: int
    updatedAt: int | None = None
    startedAt: int | None = None
    round: int | None = None
    slots: list[StartGGSlot]
    phaseGroup: StartGGPhaseGroup | None = None
    station: StartGGStation | None = None
    stream: StartGGStream | None = None


class StartGGSetsContainer(DictCompatibleBaseModel):
    """Container for sets with pagination info"""

    nodes: list[StartGGSet]


class StartGGTournament(DictCompatibleBaseModel):
    """A tournament"""

    name: str


class StartGGEvent(DictCompatibleBaseModel):
    """An event within a tournament"""

    id: int | None = None
    name: str
    tournament: StartGGTournament | None = None
    sets: StartGGSetsContainer | None = None


class StartGGEventBySlugResponse(DictCompatibleBaseModel):
    """Response for event by slug query"""

    event: StartGGEvent | None = None


class StartGGEventSetsResponse(DictCompatibleBaseModel):
    """Response for event sets query"""

    event: StartGGEvent | None = None


class StartGGError(DictCompatibleBaseModel):
    """GraphQL error from start.gg API"""

    message: str
    locations: list[DictCompatibleBaseModel] | None = None
    path: list[str] | None = None


class StartGGAPIResponse(DictCompatibleBaseModel):
    """Complete start.gg API response"""

    data: StartGGEventSetsResponse | StartGGEventBySlugResponse | None = None
    errors: list[StartGGError] | None = None
