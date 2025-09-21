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
    def __init__(self, session: aiohttp.ClientSession):
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

    async def _fetch_html(self, source: str) -> str:
            try:
                async with self._session.get(source) as resp:
                    resp.raise_for_status()
                    # let aiohttp handle encoding detection
                    return await resp.text()
            finally:
                await self._session.close()

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
