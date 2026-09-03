import voluptuous as vol

from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BackendUnauthorized, BackendUnreachable, async_fetch_printers
from .const import (
    CONF_BASE_URL,
    CONF_PRINTERS,
    CONF_API_KEY,
    CONF_ERR_CANNOT_CONNECT,
    CONF_ERR_INVALID_AUTH,
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
        """Edits the printer selection and the API key of an entry.

        The key sits in the same step rather than in one of its own: it is read
        for the printer list this step shows, so a step asking for it separately
        would have to fetch that list twice.

        Its field starts empty and stays empty, so the stored key is never put
        back on screen. An empty field therefore cannot mean "no key", it means
        the key of the entry is kept, which is what somebody editing the printer
        selection alone is after.
        """
        errors = {}
        key_rejected = False

        base_url = self.config_entry.data.get(CONF_BASE_URL)
        stored_key = self.config_entry.data.get(CONF_API_KEY, "")
        api_key = (user_input or {}).get(CONF_API_KEY, "").strip() or stored_key

        try:
            self._printers_raw = await async_fetch_printers(
                async_get_clientsession(self.hass), base_url, api_key
            )
        except BackendUnauthorized:
            errors["base"] = CONF_ERR_INVALID_AUTH
            key_rejected = True
            self._printers_raw = []
        except BackendUnreachable:
            errors["base"] = CONF_ERR_CANNOT_CONNECT
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

        # A key the backend rejects is not saved: the form comes back with the
        # rejection rather than writing an entry that can only go into reauth. A
        # backend that is merely unreachable saves as it always did, otherwise
        # its downtime would keep the printer selection from being edited.
        if user_input is None or key_rejected:
            return self.async_show_form(
                step_id="edit_printers",
                data_schema=vol.Schema({
                    vol.Optional(CONF_API_KEY, default=""): str,
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
                CONF_API_KEY: api_key,
                CONF_PRINTERS: printers_final,
            },
        )
