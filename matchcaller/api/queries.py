"""GraphQL queries used by the start.gg API client."""

EVENT_SETS_QUERY = """
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
                            user {
                                authorizations(types: [DISCORD]) {
                                    externalUsername
                                    externalId
                                }
                            }
                        }
                    }
                }
                phaseGroup {
                    displayIdentifier
                    phase {
                        name
                    }
                }
                station {
                    number
                }
                stream {
                    streamName
                }
            }
        }
    }
}
"""


TOURNAMENT_EVENTS_QUERY = """
query TournamentEvents($slug: String!) {
    tournament(slug: $slug) {
        name
        events {
            id
            name
            slug
        }
    }
}
"""


TOURNAMENT_SEARCH_QUERY = """
query SearchTournaments($name: String!, $after: Timestamp!, $before: Timestamp!) {
    tournaments(
        query: {
            page: 1
            perPage: 50
            sortBy: "startAt"
            filter: {
                name: $name
                afterDate: $after
                beforeDate: $before
            }
        }
    ) {
        nodes {
            id
            name
            slug
            startAt
        }
    }
}
"""


EVENT_ID_BY_SLUG_QUERY = """
query getEventId($slug: String) {
    event(slug: $slug) {
        id
        name
    }
}
"""


TOURNAMENT_DASHBOARD_EVENTS_QUERY = """
query TournamentDashboardEvents($slug: String!) {
    tournament(slug: $slug) {
        name
        events {
            id
            name
            slug
            state
            startAt
            numEntrants
            phases {
                id
                name
                bracketType
            }
            phaseGroups {
                id
                displayIdentifier
                bracketType
                phase {
                    id
                    name
                    bracketType
                }
            }
        }
    }
}
"""


LADDER_EVENT_DETAIL_QUERY = """
query LadderEventDetail($slug: String!, $page: Int!, $perPage: Int!) {
    event(slug: $slug) {
        id
        name
        slug
        state
        startAt
        updatedAt
        numEntrants
        sets(
            page: $page
            perPage: $perPage
            sortType: CALL_ORDER
            filters: {
                state: [1, 2, 6]
            }
        ) {
            pageInfo {
                total
                totalPages
            }
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
                            user {
                                authorizations(types: [DISCORD]) {
                                    externalUsername
                                    externalId
                                }
                            }
                        }
                    }
                }
                phaseGroup {
                    displayIdentifier
                    phase {
                        name
                    }
                }
                station {
                    number
                }
                stream {
                    streamName
                }
            }
        }
        standings(query: { page: 1, perPage: 20 }) {
            pageInfo {
                total
                totalPages
            }
            nodes {
                id
                placement
                entrant {
                    id
                    name
                    participants {
                        gamerTag
                    }
                }
                setRecordWithoutByes
            }
        }
    }
}
"""


TOURNAMENT_STATIONS_QUERY = """
query TournamentStations($slug: String!) {
    tournament(slug: $slug) {
        stations(page: 1, perPage: 100) {
            pageInfo {
                total
                totalPages
            }
            nodes {
                id
                number
                enabled
            }
        }
    }
}
"""
