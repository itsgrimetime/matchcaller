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


EVENT_ID_BY_SLUG_QUERY = """
query getEventId($slug: String) {
    event(slug: $slug) {
        id
        name
    }
}
"""
