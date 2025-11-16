import aiohttp
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN, CONF_BASE_URL, CONF_PRINTERS


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the AMS monitoring switches."""
    data = hass.data[DOMAIN][entry.entry_id]

    base_url = data[CONF_BASE_URL]
    printers = data[CONF_PRINTERS]   # [{id,name}, ...]

    entities = []
    existing_ids = set()

    for printer in printers:
        printer_id = printer["id"]
        printer_name = printer["name"]

        # Base unique ID pattern
        base_unique_id = f"ams_monitoring_{printer_id}"
        unique_id = base_unique_id
        counter = 2

        suffix_applied = False

        # Check for duplicates 
        while unique_id in existing_ids or any(
            ent for ent in entities if ent.unique_id == unique_id
        ):
            unique_id = f"{base_unique_id}_{counter}"
            counter += 1
            suffix_applied = True

        existing_ids.add(unique_id)

        # Send a persistent notification if a suffix was applied
        if suffix_applied:
            hass.components.persistent_notification.create(
                f"A duplicate printer ID was detected ('{printer_id}'). "
                f"The entity has been assigned the unique ID '{unique_id}'.",
                title="Bambu AMS Monitoring – Duplicate ID"
            )

        # Add entity
        entities.append(
            AmsPrinterSwitch(
                base_url,
                printer_id,
                printer_name,
                unique_id
            )
        )

    async_add_entities(entities, update_before_add=True)


class AmsPrinterSwitch(SwitchEntity):
    """Entity representing the monitoring on/off switch for a Bambu printer."""

    def __init__(self, base_url, printer_id, printer_name, unique_id):
        self._base_url = base_url.rstrip("/")
        self._printer_id = printer_id
        self._printer_name = printer_name

        # Unique ID (supports auto-suffixing)
        self._attr_unique_id = unique_id

        # Name following Option B: show printer name + unique_id
        self._attr_name = f"Bambu AMS Monitoring {printer_name} - {unique_id}"

        self._attr_should_poll = True
        self._attr_is_on = False

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},   # Make device unique as well
            name=f"{printer_name} ({unique_id})",
            manufacturer="Rdiger-36",
            model="Bambu AMS Monitoring",
        )

    async def async_turn_on(self, **kwargs):
        """Enable monitoring for this printer."""
        url = f"{self._base_url}/api/printer/{self._printer_id}/monitoring/start"

        async with aiohttp.ClientSession() as session:
            await session.post(url)

        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Disable monitoring for this printer."""
        url = f"{self._base_url}/api/printer/{self._printer_id}/monitoring/stop"

        async with aiohttp.ClientSession() as session:
            await session.post(url)

        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_update(self):
        """Pull the monitoring status from the backend."""
        url = f"{self._base_url}/api/status/{self._printer_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return

                data = await resp.json()
                self._attr_is_on = data.get("monitoringEnabled", False)