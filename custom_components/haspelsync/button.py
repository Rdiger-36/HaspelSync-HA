from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError

from .api import BackendUnreachable, async_post_action
from .const import DOMAIN, DATA_COORDINATORS
from .entity import AmsEntity


async def async_setup_entry(hass, entry, async_add_entities):
    """Sets up the clear and reconnect buttons of every configured printer."""
    coordinators = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATORS]

    entities = []
    for coordinator in coordinators.values():
        entities.append(AmsClearPrintResultButton(coordinator))
        entities.append(AmsReconnectButton(coordinator))
    async_add_entities(entities)


class AmsActionButton(AmsEntity, ButtonEntity):
    """A button that sends one backend action and reads the printer back.

    Unlike the switch, a button raises what went wrong: a switch that did not
    move shows it on its own, a button press that did nothing would otherwise
    look exactly like one that worked.
    """

    def _path(self) -> str:
        """The action endpoint this button posts to."""
        raise NotImplementedError

    async def async_press(self):
        coordinator = self.coordinator

        try:
            status, body = await async_post_action(coordinator.session, coordinator.base_url, coordinator.api_key, self._path())
        except BackendUnreachable as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="backend_unreachable",
                translation_placeholders={"error": str(err)},
            ) from err
        finally:
            # Also after a failure: a refused key reaches the reauth flow through
            # the refresh, and a refused action still leaves a state worth reading.
            await coordinator.async_request_refresh()

        if status != 200 or body.get("ok") is False:
            message = body.get("error") or body.get("message") or f"HTTP {status}"
            # The backend's own reason stays in English: it is the sentence the
            # backend writes, and only the frame around it is translated.
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="action_refused",
                translation_placeholders={"message": message},
            )


class AmsClearPrintResultButton(AmsActionButton):
    """Clears a finished print from the backend now instead of after its countdown.

    The job name, the layers and the consumption figures go back to an idle
    printer. The backend refuses it with a message while a print is active,
    which is raised to whoever pressed.
    """

    _attr_translation_key = "clear_print_result"
    _attr_icon = "mdi:broom"

    def __init__(self, coordinator):
        super().__init__(coordinator, "clear_print_result")

    def _path(self) -> str:
        return f"/api/print/{self.coordinator.printer_id}/clear"


class AmsReconnectButton(AmsActionButton):
    """Rebuilds the MQTT connections of the backend without restarting it.

    The backend offers this for all of its printers at once, so every printer
    device carries the same button and each one reconnects them all. It keeps
    the consumption tracking of a running print, which a restart would lose.
    """

    _attr_translation_key = "reconnect"
    _attr_icon = "mdi:lan-connect"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator):
        super().__init__(coordinator, "reconnect")

    def _path(self) -> str:
        return "/api/printers/reconnect"
