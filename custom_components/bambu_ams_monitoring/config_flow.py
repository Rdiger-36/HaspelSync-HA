import aiohttp
import voluptuous as vol

from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_BASE_URL,
    CONF_PRINTERS,
    CONF_ERR_CANNOT_CONNECT,
)


class AmsManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for the Bambu AMS Monitoring integration.

    A printer may be configured in more than one integration instance, and the
    same backend may be added more than once. Printer IDs are therefore always
    used exactly as the backend reports them: they are the key the backend
    resolves in /api/status/<id>, so any rewriting here would produce entities
    that can never reach their printer.
    """

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        from .options_flow import AmsManagerOptionsFlowHandler
        return AmsManagerOptionsFlowHandler()

    def __init__(self):
        self._base_url = None
        self._printers_raw = None

    # -------------------------------------------------------------------------
    # STEP 1 – ENTER BASE URL
    # -------------------------------------------------------------------------
    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required(CONF_BASE_URL): str,
                }),
                errors=errors,
            )

        base_url = user_input[CONF_BASE_URL].rstrip("/")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{base_url}/api/printers") as resp:
                    if resp.status != 200:
                        raise Exception("Backend error")
                    printers = await resp.json()

        except Exception:
            errors["base"] = CONF_ERR_CANNOT_CONNECT

        else:
            self._base_url = base_url
            self._printers_raw = printers
            return await self.async_step_select_printers()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_BASE_URL, default=base_url): str
            }),
            errors=errors,
        )

    # -------------------------------------------------------------------------
    # STEP 2 – SELECT PRINTERS
    # -------------------------------------------------------------------------
    async def async_step_select_printers(self, user_input=None):
        assert self._printers_raw is not None
        assert self._base_url is not None

        printer_names = {
            p["id"]: f"{p['name']} ({p['id']})"
            for p in self._printers_raw
        }

        if user_input is None:
            return self.async_show_form(
                step_id="select_printers",
                data_schema=vol.Schema({
                    vol.Required(CONF_PRINTERS): cv.multi_select(printer_names)
                }),
                errors={},
            )

        selected = user_input[CONF_PRINTERS]
        printer_map = {p["id"]: p["name"] for p in self._printers_raw}

        return self.async_create_entry(
            title=f"Bambu AMS Monitoring ({self._base_url})",
            data={
                CONF_BASE_URL: self._base_url,
                CONF_PRINTERS: [
                    {"id": pid, "name": printer_map[pid]}
                    for pid in selected
                ],
            },
        )
