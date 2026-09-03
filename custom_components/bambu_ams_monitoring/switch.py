import logging

import aiohttp

from homeassistant.components.switch import SwitchEntity

from .api import auth_headers
from .const import DOMAIN, DATA_COORDINATORS, REQUEST_TIMEOUT
from .entity import AmsEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the AMS monitoring switches."""
    coordinators = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATORS]

    async_add_entities(AmsPrinterSwitch(coordinator) for coordinator in coordinators.values())


class AmsPrinterSwitch(AmsEntity, SwitchEntity):
    """Switch to enable/disable AMS monitoring for a single Bambu printer.

    The state comes from the shared coordinator now, so the switch no longer
    polls /api/status on its own while the sensors read the same answer. Its
    name and unique ID stay exactly as they were: both are what an existing
    installation has in its entity registry.
    """

    _attr_has_entity_name = False

    def __init__(self, coordinator):
        super().__init__(coordinator, "ams_monitoring")
        self._attr_name = f"AMS Monitoring {coordinator.printer_name}"

    @property
    def is_on(self):
        return bool(self.coordinator.status.get("monitoringEnabled"))

    async def async_turn_on(self, **kwargs):
        await self._async_set_monitoring("start")

    async def async_turn_off(self, **kwargs):
        await self._async_set_monitoring("stop")

    async def _async_set_monitoring(self, action: str):
        """Starts or stops monitoring and reads the new state back.

        The two endpoints answer HTTP 200 with `ok: false` when the state was
        already what was asked for, so the body decides whether anything
        happened. Either way the coordinator refreshes, which is what puts the
        switch on the state the backend actually holds rather than on the one
        this call assumed.

        A 401 is left to that refresh as well: the coordinator turns it into the
        reauth flow, and raising it from a toggle would only tell the one person
        who happened to press the switch.
        """
        url = f"{self.coordinator.base_url}/api/printer/{self.coordinator.printer_id}/monitoring/{action}"

        try:
            timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            async with self.coordinator.session.post(url, headers=auth_headers(self.coordinator.api_key), timeout=timeout) as resp:
                if resp.status != 200:
                    _LOGGER.warning(
                        "Failed to %s monitoring for %s: HTTP %s",
                        action, self.coordinator.printer_id, resp.status,
                    )
                else:
                    body = await resp.json(content_type=None)
                    if isinstance(body, dict) and body.get("ok") is False:
                        _LOGGER.debug(
                            "Backend did not %s monitoring for %s: %s",
                            action, self.coordinator.printer_id, body.get("message"),
                        )
        except (aiohttp.ClientError, ValueError, TimeoutError) as err:
            _LOGGER.error("Error while sending %s for %s: %s", action, self.coordinator.printer_id, err)

        await self.coordinator.async_request_refresh()
