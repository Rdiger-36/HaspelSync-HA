from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, EXTERNAL_SLOT
from .coordinator import AmsPrinterCoordinator


def ams_unit_of(ams_id: str) -> str | None:
    """The AMS unit a slot label belongs to, or None for an external holder.

    A1 belongs to A. An AMS HT has a single slot and its label is the unit
    itself, HT-A. The external holders, External and External-2, belong to no
    unit and stay on the printer device.
    """
    if ams_id.startswith(EXTERNAL_SLOT):
        return None
    if ams_id.startswith("HT-"):
        return ams_id
    return ams_id.rstrip("0123456789") or None


def ams_device_info(coordinator: AmsPrinterCoordinator, unit: str) -> DeviceInfo:
    """The device of one AMS unit, attached below its printer.

    One device per unit, the way ha-bambulab shows them, so four slots and the
    readings of one AMS sit together instead of every slot of every unit on the
    printer. The identifier carries the printer ID, because the unit letter
    alone repeats on every printer, and it is the same in every integration
    instance holding the printer, which keeps one device for all of them.
    """
    return DeviceInfo(
        identifiers={(DOMAIN, f"{coordinator.printer_id}_ams_{unit}")},
        name=f"{coordinator.printer_name} AMS {unit}",
        manufacturer="Bambu Lab",
        # Read once when the entity is added. An AMS Lite reports no readings
        # and therefore no model, and the backend learns the model of the others
        # only after asking the printer, so it may still be missing here.
        model=(coordinator.ams_units.get(unit) or {}).get("model"),
        via_device=(DOMAIN, coordinator.printer_id),
    )


class AmsEntity(CoordinatorEntity):
    """Base for everything this integration reads out of one printer.

    Every entity of a printer attaches to the printer device, apart from those
    of an AMS unit and its slots, which attach to the device of that unit. The
    unique ID
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
            model="HaspelSync",
        )


class AmsSlotEntity(AmsEntity):
    """Base for an entity that describes a single AMS slot, for example A1."""

    def __init__(self, coordinator: AmsPrinterCoordinator, key: str, ams_id: str):
        super().__init__(coordinator, f"{key}_{ams_id}")
        self._ams_id = ams_id
        self._attr_translation_placeholders = {"slot": ams_id}
        unit = ams_unit_of(ams_id)
        if unit:
            self._attr_device_info = ams_device_info(coordinator, unit)

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
        self._attr_device_info = ams_device_info(coordinator, ams_id)

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
