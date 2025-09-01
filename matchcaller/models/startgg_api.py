"""Pydantic models for start.gg API responses."""

from typing import List, Optional, Union

from pydantic import Field

from ..models.match import DictCompatibleBaseModel


class StartGGParticipant(DictCompatibleBaseModel):
    """A participant in a tournament (player)"""
    
    gamerTag: str


class StartGGEntrant(DictCompatibleBaseModel):
    """An entrant in a set (can have multiple participants for teams)"""
    
    participants: List[StartGGParticipant]


class StartGGSlot(DictCompatibleBaseModel):
    """A slot in a set (position for an entrant)"""
    
    entrant: Optional[StartGGEntrant] = None


class StartGGPhase(DictCompatibleBaseModel):
    """A phase in a tournament (e.g., pools, top 8)"""
    
    name: str


class StartGGPhaseGroup(DictCompatibleBaseModel):
    """A phase group (e.g., Pool A, Pool B)"""
    
    displayIdentifier: Optional[str] = None
    phase: Optional[StartGGPhase] = None


class StartGGStation(DictCompatibleBaseModel):
    """A tournament station"""
    
    number: int


class StartGGStream(DictCompatibleBaseModel):
    """A tournament stream"""
    
    streamName: str


class StartGGSet(DictCompatibleBaseModel):
    """A set/match in a tournament"""
    
    id: int
    fullRoundText: Optional[str] = None
    identifier: Optional[str] = None
    state: int
    updatedAt: Optional[int] = None
    startedAt: Optional[int] = None
    round: Optional[int] = None
    slots: List[StartGGSlot]
    phaseGroup: Optional[StartGGPhaseGroup] = None
    station: Optional[StartGGStation] = None
    stream: Optional[StartGGStream] = None


class StartGGSetsContainer(DictCompatibleBaseModel):
    """Container for sets with pagination info"""
    
    nodes: List[StartGGSet]


class StartGGTournament(DictCompatibleBaseModel):
    """A tournament"""
    
    name: str


class StartGGEvent(DictCompatibleBaseModel):
    """An event within a tournament"""
    
    id: Optional[int] = None
    name: str
    tournament: Optional[StartGGTournament] = None
    sets: Optional[StartGGSetsContainer] = None


class StartGGEventBySlugResponse(DictCompatibleBaseModel):
    """Response for event by slug query"""
    
    event: Optional[StartGGEvent] = None


class StartGGEventSetsResponse(DictCompatibleBaseModel):
    """Response for event sets query"""
    
    event: Optional[StartGGEvent] = None


class StartGGError(DictCompatibleBaseModel):
    """GraphQL error from start.gg API"""
    
    message: str
    locations: Optional[List[dict]] = None
    path: Optional[List[str]] = None


class StartGGAPIResponse(DictCompatibleBaseModel):
    """Complete start.gg API response"""
    
    data: Optional[Union[StartGGEventSetsResponse, StartGGEventBySlugResponse]] = None
    errors: Optional[List[StartGGError]] = None