import aiohttp
import voluptuous as vol

from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_BASE_URL,
    CONF_PRINTERS,
)


class AmsManagerOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Bambu AMS Monitoring.

    `self.config_entry` is provided by the base class. Assigning it here is
    deprecated since Home Assistant 2024.11 and removed in 2025.12.
    """

    def __init__(self):
        self._printers_raw = []

    async def async_step_init(self, user_input=None):
        return await self.async_step_edit_printers()

    async def async_step_edit_printers(self, user_input=None):
        errors = {}

        base_url = self.config_entry.data.get(CONF_BASE_URL)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{base_url}/api/printers") as resp:
                    if resp.status != 200:
                        raise Exception("Backend error")
                    self._printers_raw = await resp.json()
        except Exception:
            errors["base"] = "cannot_connect"
            self._printers_raw = []

        printer_map = {
            p["id"]: f"{p['name']} ({p['id']})"
            for p in self._printers_raw
        }

        currently_selected = [
            p["id"] for p in self.config_entry.data.get(CONF_PRINTERS, [])
        ]

        # A printer that is configured here but currently missing from the
        # backend answer stays selectable, so a backend that is unreachable at
        # this moment cannot silently drop it from the entry.
        for p in self.config_entry.data.get(CONF_PRINTERS, []):
            printer_map.setdefault(p["id"], f"{p['name']} ({p['id']})")

        if user_input is None:
            return self.async_show_form(
                step_id="edit_printers",
                data_schema=vol.Schema({
                    vol.Required(CONF_PRINTERS, default=currently_selected): cv.multi_select(printer_map)
                }),
                errors=errors,
            )

        selected_ids = user_input[CONF_PRINTERS]

        name_lookup = {p["id"]: p["name"] for p in self._printers_raw}
        for p in self.config_entry.data.get(CONF_PRINTERS, []):
            name_lookup.setdefault(p["id"], p["name"])

        # Preserve names for IDs that are still known; fall back to ID as name
        printers_final = [
            {"id": pid, "name": name_lookup.get(pid, pid)}
            for pid in selected_ids
        ]

        # Options flow must write back into entry.data via a reload listener
        # We store the updated printer list in options; __init__.py reloads the entry.
        return self.async_create_entry(
            title="",
            data={
                CONF_BASE_URL: base_url,
                CONF_PRINTERS: printers_final,
            },
        )
