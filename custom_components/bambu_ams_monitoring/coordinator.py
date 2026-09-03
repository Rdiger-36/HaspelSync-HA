import inspect
import logging

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL, REQUEST_TIMEOUT, EXTERNAL_SLOT

_LOGGER = logging.getLogger(__name__)

# Passing the config entry became the documented way to build a coordinator only
# after the minimum version this integration supports, where the argument does
# not exist yet and would raise a TypeError. Checked once here rather than
# guarded per call.
_SUPPORTS_CONFIG_ENTRY = "config_entry" in inspect.signature(DataUpdateCoordinator.__init__).parameters


class AmsPrinterCoordinator(DataUpdateCoordinator):
    """Polls the backend for everything one printer exposes.

    One coordinator per printer rather than one per config entry: a backend that
    answers for one printer and 404s for another then leaves only that printer's
    entities unavailable. Three endpoints are read per cycle, but only
    /api/status decides whether the printer is reachable at all. The other two
    are allowed to fail on their own, because a spool list that cannot be read
    must not take the connection sensors down with it.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, session, base_url: str, printer_id: str, printer_name: str):
        self.session = session
        self.base_url = base_url.rstrip("/")
        self.printer_id = printer_id
        self.printer_name = printer_name
        self.entry_id = entry.entry_id

        kwargs = {
            "name": f"{DOMAIN} {printer_id}",
            "update_interval": UPDATE_INTERVAL,
        }
        if _SUPPORTS_CONFIG_ENTRY:
            kwargs["config_entry"] = entry

        super().__init__(hass, _LOGGER, **kwargs)

    async def _async_update_data(self):
        """Reads status, spools and print job of this printer."""
        status = await self._get(f"/api/status/{self.printer_id}", required=True)

        return {
            "status": status,
            "spools": await self._get(f"/api/spools/{self.printer_id}") or [],
            "print": await self._get(f"/api/print/{self.printer_id}"),
        }

    async def _get(self, path: str, required: bool = False):
        """Reads one backend endpoint.

        A required endpoint that cannot be read raises UpdateFailed, which marks
        every entity of this printer unavailable. An optional one answers None,
        so the entities that do not depend on it keep their state.
        """
        url = f"{self.base_url}{path}"
        try:
            timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            async with self.session.get(url, timeout=timeout) as resp:
                if resp.status != 200:
                    if required:
                        raise UpdateFailed(f"{path} answered HTTP {resp.status}")
                    _LOGGER.debug("%s answered HTTP %s", path, resp.status)
                    return None
                return await resp.json()
        except UpdateFailed:
            raise
        except (aiohttp.ClientError, ValueError, TimeoutError) as err:
            if required:
                raise UpdateFailed(f"{path} could not be read: {err}") from err
            _LOGGER.debug("%s could not be read: %s", path, err)
            return None

    @property
    def status(self) -> dict:
        """The last /api/status answer, empty before the first successful poll."""
        return (self.data or {}).get("status") or {}

    @property
    def print_job(self) -> dict:
        """The last /api/print answer, empty when that endpoint could not be read."""
        return (self.data or {}).get("print") or {}

    @property
    def slots(self) -> dict:
        """Every AMS slot of this printer, keyed by its label, for example A1."""
        return {
            spool["amsId"]: spool
            for spool in (self.data or {}).get("spools") or []
            if spool.get("amsId")
        }

    @property
    def ams_units(self) -> dict:
        """Every AMS unit that reports environment readings, keyed by its letter.

        The external spool holder is filtered out although it can appear as a
        slot: it is not a unit and has neither humidity nor a dryer. An AMS Lite
        reports no readings at all and is therefore absent here as well, while
        its slots are present in `slots`.
        """
        return {
            unit["amsId"]: unit
            for unit in self.status.get("amsEnv") or []
            if unit.get("amsId") and unit["amsId"] != EXTERNAL_SLOT
        }
