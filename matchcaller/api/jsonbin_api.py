"""JsonBin.io API client for fetching late arrivals and DQ data."""

import aiohttp

from ..utils.logging import log


class AlertData:
    """Parsed alert data from jsonbin.

    The Discord bot sends Discord user IDs as keys, which are matched
    against the Discord accounts linked to start.gg profiles.
    """

    def __init__(self, data: dict):
        self.late_arrivals: set[str] = set()
        self.dqs: set[str] = set()
        self.last_updated: str = data.get("lastUpdated", "")

        # Values are Discord user IDs (strings)
        for discord_id in data.get("lateArrivals", []):
            self.late_arrivals.add(str(discord_id))
        for discord_id in data.get("dqs", []):
            self.dqs.add(str(discord_id))


class JsonBinAPI:
    """Fetch late arrival / DQ alerts from a jsonbin.io bin."""

    def __init__(self, bin_id: str, api_key: str | None = None):
        self.bin_id = bin_id
        self.api_key = api_key
        self.base_url = f"https://api.jsonbin.io/v3/b/{bin_id}/latest"

    async def fetch_alerts(self) -> AlertData:
        headers: dict[str, str] = {}
        if self.api_key:
            headers["X-Master-Key"] = self.api_key
        else:
            headers["X-Access-Key"] = "$2a$10$placeholder"  # public read

        try:
            async with aiohttp.ClientSession() as session:
                log(f"🔔 Fetching alerts from jsonbin: {self.bin_id}")
                async with session.get(
                    self.base_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        log(f"❌ JsonBin HTTP {response.status}: {error_text}")
                        return AlertData({})

                    data = await response.json()
                    record = data.get("record", {})
                    log(
                        f"✅ Alerts fetched: {len(record.get('lateArrivals', []))} late, "
                        f"{len(record.get('dqs', []))} DQs"
                    )
                    return AlertData(record)

        except Exception as e:
            log(f"❌ JsonBin fetch error: {type(e).__name__}: {e}")
            return AlertData({})
