import voluptuous as vol

from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BackendUnauthorized, BackendUnreachable, async_fetch_printers
from .const import (
    DOMAIN,
    CONF_BASE_URL,
    CONF_PRINTERS,
    CONF_API_KEY,
    CONF_ERR_CANNOT_CONNECT,
    CONF_ERR_INVALID_AUTH,
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
        self._api_key = None
        self._printers_raw = None

    # -------------------------------------------------------------------------
    # STEP 1: ENTER BASE URL AND API KEY
    # -------------------------------------------------------------------------
    async def async_step_user(self, user_input=None):
        errors = {}
        base_url = ""
        api_key = ""

        if user_input is not None:
            base_url = user_input[CONF_BASE_URL].rstrip("/")
            api_key = user_input[CONF_API_KEY].strip()

            try:
                printers = await async_fetch_printers(
                    async_get_clientsession(self.hass), base_url, api_key
                )
            except BackendUnauthorized:
                errors["base"] = CONF_ERR_INVALID_AUTH
            except BackendUnreachable:
                errors["base"] = CONF_ERR_CANNOT_CONNECT
            else:
                self._base_url = base_url
                self._api_key = api_key
                self._printers_raw = printers
                return await self.async_step_select_printers()

        # Both fields come back filled with what was typed, so a rejected key
        # is corrected rather than retyped along with the URL. An empty default
        # would make the field look prefilled with nothing, so the first pass
        # through this form carries none.
        url_field = vol.Required(CONF_BASE_URL, default=base_url) if base_url else vol.Required(CONF_BASE_URL)
        key_field = vol.Required(CONF_API_KEY, default=api_key) if api_key else vol.Required(CONF_API_KEY)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                url_field: str,
                key_field: str,
            }),
            errors=errors,
        )

    # -------------------------------------------------------------------------
    # STEP 2: SELECT PRINTERS
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
                CONF_API_KEY: self._api_key,
                CONF_PRINTERS: [
                    {"id": pid, "name": printer_map[pid]}
                    for pid in selected
                ],
            },
        )

    # -------------------------------------------------------------------------
    # REAUTH: A KEY THAT STOPPED WORKING
    # -------------------------------------------------------------------------
    async def async_step_reauth(self, entry_data):
        """Entered when the backend answers 401 during normal operation.

        A key can be revoked in the Web UI, and an entry set up against a
        backend that did not ask for one yet holds no key at all. Both end up
        here, which asks for a key alone and leaves the printer selection and
        every entity of the entry untouched.
        """
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}

        # Read off the context rather than through _get_reauth_entry(), which
        # this integration's minimum Home Assistant version does not have.
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()

            try:
                await async_fetch_printers(
                    async_get_clientsession(self.hass),
                    entry.data[CONF_BASE_URL],
                    api_key,
                )
            except BackendUnauthorized:
                errors["base"] = CONF_ERR_INVALID_AUTH
            except BackendUnreachable:
                errors["base"] = CONF_ERR_CANNOT_CONNECT
            else:
                # Writes the key, reloads the entry and aborts in one step. The
                # entry may be in a failed setup here, where the update listener
                # that normally reloads it is not registered at all.
                return self.async_update_reload_and_abort(
                    entry, data={**entry.data, CONF_API_KEY: api_key}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({
                vol.Required(CONF_API_KEY): str,
            }),
            description_placeholders={"base_url": entry.data[CONF_BASE_URL]},
            errors=errors,
        )
