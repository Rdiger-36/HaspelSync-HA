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
    """Handle options flow for Bambu AMS Monitoring."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        self.config_entry = config_entry
        self._printers_raw = None


    async def async_step_init(self, user_input=None):
        """Initial step: choose whether to change base URL or printers."""
        return await self.async_step_edit_printers()


    # -------------------------------------------------------------------------
    # PRINTER EDITING
    # -------------------------------------------------------------------------
    async def async_step_edit_printers(self, user_input=None):
        errors = {}

        base_url = self.config_entry.data.get(CONF_BASE_URL)

        # Fetch printers again from backend
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{base_url}/api/printers") as resp:
                    if resp.status != 200:
                        raise Exception("Backend error")
                    printers = await resp.json()
        except Exception:
            errors["base"] = "cannot_connect"
            printers = []

        # Build printer list
        printer_map = {
            p["id"]: f"{p['name']} ({p['id']})"
            for p in printers
        }

        # First run
        if user_input is None:
            return self.async_show_form(
                step_id="edit_printers",
                data_schema=vol.Schema({
                    vol.Required(
                        CONF_PRINTERS,
                        default=[p["id"] for p in self.config_entry.data.get(CONF_PRINTERS, [])]
                    ): cv.multi_select(printer_map)
                }),
                errors=errors,
            )

        # Save new configuration
        selected = user_input[CONF_PRINTERS]

        return self.async_create_entry(
            title="",
            data={
                CONF_PRINTERS: selected,
                CONF_BASE_URL: base_url,
            }
        )
