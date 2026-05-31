import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_BASE_URL,
    CONF_PRINTERS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the AMS monitoring switches."""
    data = hass.data[DOMAIN][entry.entry_id]

    base_url = data[CONF_BASE_URL]
    printers = data[CONF_PRINTERS]   # [{id, name}, ...]
    session = async_get_clientsession(hass)

    entities = [
        AmsPrinterSwitch(session, base_url, printer["id"], printer["name"])
        for printer in printers
    ]

    async_add_entities(entities, update_before_add=True)


class AmsPrinterSwitch(SwitchEntity):
    """Switch to enable/disable AMS monitoring for a single Bambu printer."""

    def __init__(self, session, base_url, printer_id, printer_name):
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._printer_id = printer_id

        self._attr_unique_id = f"ams_monitoring_{printer_id}"
        self._attr_name = f"AMS Monitoring {printer_name}"
        self._attr_should_poll = True
        self._attr_is_on = False
        self._attr_available = False

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, printer_id)},
            name=printer_name,
            manufacturer="Rdiger-36",
            model="Bambu AMS Monitoring",
        )

    async def async_turn_on(self, **kwargs):
        url = f"{self._base_url}/api/printer/{self._printer_id}/monitoring/start"
        try:
            async with self._session.post(url) as resp:
                if resp.status == 200:
                    self._attr_is_on = True
                    self._attr_available = True
                else:
                    _LOGGER.warning("Failed to start monitoring for %s: HTTP %s", self._printer_id, resp.status)
        except Exception as err:
            _LOGGER.error("Error starting monitoring for %s: %s", self._printer_id, err)
            self._attr_available = False
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        url = f"{self._base_url}/api/printer/{self._printer_id}/monitoring/stop"
        try:
            async with self._session.post(url) as resp:
                if resp.status == 200:
                    self._attr_is_on = False
                    self._attr_available = True
                else:
                    _LOGGER.warning("Failed to stop monitoring for %s: HTTP %s", self._printer_id, resp.status)
        except Exception as err:
            _LOGGER.error("Error stopping monitoring for %s: %s", self._printer_id, err)
            self._attr_available = False
        self.async_write_ha_state()

    async def async_update(self):
        url = f"{self._base_url}/api/status/{self._printer_id}"
        try:
            async with self._session.get(url) as resp:
                if resp.status != 200:
                    _LOGGER.debug("Status check for %s returned HTTP %s", self._printer_id, resp.status)
                    self._attr_available = False
                    return
                data = await resp.json()
                self._attr_is_on = data.get("monitoringEnabled", False)
                self._attr_available = True
        except Exception as err:
            _LOGGER.warning("Cannot reach backend for %s: %s", self._printer_id, err)
            self._attr_available = False
