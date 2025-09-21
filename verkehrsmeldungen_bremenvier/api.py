import asyncio
import json
import re
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from bs4 import BeautifulSoup
import aiohttp
from aiohttp import ClientTimeout
import os
from .const import TRAFFIC_URL, DE_MONTHS

class TrafficAPI:
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self._session = session

    @staticmethod
    def _parse_german_datetime(s: str) -> Optional[str]:
        """
        Parse strings like '21. September 2025, 15:35 Uhr' to ISO 8601 (no tz).
        Returns ISO string in local time (no timezone info) or None if parsing fails.
        """
        if not s:
            return None
        s = s.strip()
        m = re.match(r"(\d{1,2})\.\s*([A-Za-zäöüÄÖÜ]+)\s+(\d{4}),\s*(\d{1,2}):(\d{2})", s)
        if not m:
            return None
        day = int(m.group(1))
        month_name = m.group(2).lower()
        month_name = month_name.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
        month = DE_MONTHS.get(month_name)
        if not month:
            return None
        year = int(m.group(3))
        hour = int(m.group(4))
        minute = int(m.group(5))
        try:
            dt = datetime(year, month, day, hour, minute)
            return dt.isoformat(timespec="minutes")
        except ValueError:
            return None

    async def _fetch_html(self, source: str, *, timeout_s: int = 20) -> str:
        """
        Load HTML either from a local file path or from a URL.
        - URLs: fetched via aiohttp (async)
        - Files: read in a thread pool to avoid blocking the loop
        """
        if re.match(r"^https?://", source):
            close_when_done = False
            session = self._session
            if session is None:
                session = aiohttp.ClientSession(timeout=ClientTimeout(total=timeout_s))
                close_when_done = True
            try:
                async with session.get(
                    source,
                    headers={"User-Agent": "traffic-scraper/1.0 (+https://example.local)"}
                ) as resp:
                    resp.raise_for_status()
                    # let aiohttp handle encoding detection
                    return await resp.text()
            finally:
                if close_when_done:
                    await session.close()
        else:
            loop = asyncio.get_running_loop()
            path = os.fspath(source)
            return await loop.run_in_executor(None, lambda: open(path, "r", encoding="utf-8").read())

    @staticmethod
    def _parse_traffic(html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        entries: List[Dict[str, Any]] = []

        for li in soup.select("li.traffic-section-entry"):
            kind = li.select_one(".traffic-event-topline")
            title = li.select_one(".traffic-event-title")
            msg_block = li.select_one(".traffic-event-message")
            date = li.select_one(".traffic-event-date")

            kind_text = kind.get_text(strip=True) if kind else None
            title_text = title.get_text(" ", strip=True) if title else None

            # message element can contain multiple lines <br> or multiple text nodes
            message_text: Optional[str] = None
            if msg_block:
                message_text = " ".join(msg_block.stripped_strings)

            date_text = date.get_text(strip=True) if date else None
            date_parsed = TrafficAPI._parse_german_datetime(date_text) if date_text else None

            entries.append({
                "type": kind_text,            # e.g., "Stau", "Blitzer"
                "title": title_text,          # full headline
                "message": message_text,      # extra details (may be None)
                "date": date_parsed,          # ISO 8601 minutes precision (best effort)
            })
        return entries

    async def fetch(self, source: Union[str, None] = None) -> List[Dict[str, Any]]:
        """
        Fetch and parse traffic data.
        If 'source' is None, the default TRAFFIC_URL is used.
        """
        src = source or TRAFFIC_URL
        html = await self._fetch_html(src)
        return self._parse_traffic(html)
