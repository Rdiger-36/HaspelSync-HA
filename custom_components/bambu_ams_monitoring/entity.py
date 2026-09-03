from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AmsPrinterCoordinator


class AmsEntity(CoordinatorEntity):
    """Base for everything this integration reads out of one printer.

    Every entity of a printer attaches to the same device, so a slot sensor, an
    AMS humidity reading and the monitoring switch sit together. The unique ID
    keeps the shape the switch has always used, `{entry_id}_{key}_{printer_id}`,
    because the entry scope is what lets the same printer be configured in
    several integration instances.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: AmsPrinterCoordinator, key: str):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_{key}_{coordinator.printer_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.printer_id)},
            name=coordinator.printer_name,
            manufacturer="Rdiger-36",
            model="Bambu AMS Monitoring",
        )


class AmsSlotEntity(AmsEntity):
    """Base for an entity that describes a single AMS slot, for example A1."""

    def __init__(self, coordinator: AmsPrinterCoordinator, key: str, ams_id: str):
        super().__init__(coordinator, f"{key}_{ams_id}")
        self._ams_id = ams_id
        self._attr_translation_placeholders = {"slot": ams_id}

    @property
    def slot(self) -> dict:
        """The backend payload of this slot, empty while the slot is not reported."""
        return self.coordinator.slots.get(self._ams_id) or {}

    @property
    def available(self) -> bool:
        # A slot disappears when its AMS unit is unplugged. Reporting the last
        # known filament for a unit that is no longer there would be wrong, and
        # deleting the entity would lose its history, so it goes unavailable.
        return super().available and self._ams_id in self.coordinator.slots


class AmsUnitEntity(AmsEntity):
    """Base for an entity that describes one AMS unit, for example A."""

    def __init__(self, coordinator: AmsPrinterCoordinator, key: str, ams_id: str):
        super().__init__(coordinator, f"{key}_{ams_id}")
        self._ams_id = ams_id
        self._attr_translation_placeholders = {"ams": ams_id}

    @property
    def unit(self) -> dict:
        """The environment readings of this unit, empty while it is not reported."""
        return self.coordinator.ams_units.get(self._ams_id) or {}

    @property
    def available(self) -> bool:
        return super().available and self._ams_id in self.coordinator.ams_units


@callback
def async_track_members(entry, coordinator, async_add_entities, members, build):
    """Creates entities for AMS units or slots as the backend starts reporting them.

    Neither is known at setup: the backend answers with an empty spool list until
    its first AMS update, and a unit plugged in later appears only in a later
    poll. Discovering on every coordinator update means such a unit brings its
    entities with it instead of waiting for the next reload of the entry.

    @param members: returns the currently reported IDs, a dict or a set
    @param build: returns the entities for one newly seen ID
    """
    known = set()

    @callback
    def _discover():
        new = set(members()) - known
        if not new:
            return

        known.update(new)
        entities = []
        for member_id in sorted(new):
            entities.extend(build(member_id))
        async_add_entities(entities)

    _discover()
    entry.async_on_unload(coordinator.async_add_listener(_discover))
