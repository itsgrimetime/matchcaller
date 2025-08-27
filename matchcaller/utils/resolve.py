import requests


def resolve_tournament_slug_from_unique_string(unique_string: str) -> str:
    response = requests.get(f"https://start.gg/{unique_string}")
    return response.url.split("/")[-2]
