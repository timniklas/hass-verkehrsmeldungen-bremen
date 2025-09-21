from dataclasses import dataclass
from datetime import timedelta
import logging

import re

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from aiohttp import ClientError
from xml.dom import minidom
from .api import TrafficAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class TrafficAPIData:
    """Class to hold api data."""

    items: [any]


class TrafficCoordinator(DataUpdateCoordinator):
    """My coordinator."""

    data: TrafficAPIData

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize coordinator."""

        # Initialise DataUpdateCoordinator
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({config_entry.unique_id})",
            # Method to call on every update interval.
            update_method=self.async_update_data,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=60),
        )
        self.connected: bool = False
        websession = async_get_clientsession(hass)
        self.api = TrafficAPI(websession)

    async def async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            data = await self.api.fetch()
            self.connected = True
            return TrafficAPIData(items=data)
        except ClientError as err:
            # This will show entities as unavailable by raising UpdateFailed exception
            raise UpdateFailed(f"Error communicating with API: {err}") from err
