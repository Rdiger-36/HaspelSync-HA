from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, CONF_BASE_URL, CONF_PRINTERS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data.setdefault(DOMAIN, {})

    hass.data[DOMAIN][entry.entry_id] = {
        CONF_BASE_URL: entry.data[CONF_BASE_URL],
        CONF_PRINTERS: entry.data[CONF_PRINTERS],
    }

    await hass.config_entries.async_forward_entry_setups(entry, ["switch"])
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Apply options changes by merging them into entry.data and reloading."""
    if entry.options:
        hass.config_entries.async_update_entry(entry, data={**entry.data, **entry.options}, options={})
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    unloaded = await hass.config_entries.async_forward_entry_unload(entry, "switch")
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
