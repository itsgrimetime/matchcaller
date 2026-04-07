"""JsonBin.io API client for fetching late arrivals and DQ data."""

from ..utils.logging import log
from .transport import AiohttpTransport, HTTPTransport


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

    def __init__(
        self,
        bin_id: str,
        api_key: str | None = None,
        *,
        transport: HTTPTransport | None = None,
    ):
        self.bin_id = bin_id
        self.api_key = api_key
        self.base_url = f"https://api.jsonbin.io/v3/b/{bin_id}/latest"
        self.transport = transport or AiohttpTransport()

    async def fetch_alerts(self) -> AlertData:
        headers: dict[str, str] = {}
        if self.api_key:
            headers["X-Master-Key"] = self.api_key
        else:
            headers["X-Access-Key"] = "$2a$10$placeholder"  # public read

        try:
            log(f"🔔 Fetching alerts from jsonbin: {self.bin_id}")
            response = await self.transport.get_json(
                self.base_url,
                headers=headers,
                timeout_seconds=10,
            )
            if response.status != 200:
                error_text = response.text or str(response.json_data)
                log(f"❌ JsonBin HTTP {response.status}: {error_text}")
                return AlertData({})

            if not isinstance(response.json_data, dict):
                log("❌ JsonBin returned a non-JSON response")
                return AlertData({})

            record = response.json_data.get("record", {})
            log(
                f"✅ Alerts fetched: {len(record.get('lateArrivals', []))} late, "
                f"{len(record.get('dqs', []))} DQs"
            )
            return AlertData(record)

        except Exception as e:
            log(f"❌ JsonBin fetch error: {type(e).__name__}: {e}")
            return AlertData({})
