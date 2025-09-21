import sys
import json
import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup
import requests

DE_MONTHS = {
    "januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12
}

class TrafficAPI:
    def _parse_german_datetime(self, s: str) -> Optional[str]:
        """
        Parse strings like '21. September 2025, 15:35 Uhr' to ISO 8601.
        Returns ISO string in local time (no timezone info) or None if parsing fails.
        """
        s = s.strip()
        # 21. September 2025, 15:35 Uhr
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


    def _fetch_html(self, source: str) -> str:
        """Load HTML either from a local file path or from a URL."""
        if re.match(r"^https?://", source):
            if requests is None:
                raise RuntimeError("requests not installed; cannot fetch URL")
            resp = requests.get(source, timeout=20)
            resp.raise_for_status()
            return resp.text
        else:
            with open(source, "r", encoding="utf-8") as f:
                return f.read()


    def _parse_traffic(self, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        entries = []
        for li in soup.select("li.traffic-section-entry"):
            kind = li.select_one(".traffic-event-topline")
            title = li.select_one(".traffic-event-title")
            msg_block = li.select_one(".traffic-event-message")
            date = li.select_one(".traffic-event-date")

            kind_text = kind.get_text(strip=True) if kind else None
            title_text = title.get_text(" ", strip=True) if title else None

            # message element can contain multiple lines <br> or multiple text nodes
            message_text = None
            if msg_block:
                message_text = " ".join(msg_block.stripped_strings)

            date_text = date.get_text(strip=True) if date else None
            date_parsed = self._parse_german_datetime(date_text) if date_text else None

            entries.append({
                "type": kind_text,            # e.g., "Stau", "Blitzer"
                "title": title_text,          # full headline
                "message": message_text,      # extra details (may be None)
                "date": date_parsed,         # ISO 8601 minutes precision (best effort)
            })
        return entries

    def fetch(self) -> List[Dict[str, Any]]:
        html = self._fetch_html("https://www.bremenvier.de/verkehr/aktuelle-verkehrsmeldungen-aus-dem-land-bremen-und-der-region-100.html")
        return self._parse_traffic(html)
