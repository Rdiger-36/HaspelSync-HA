from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, PERCENTAGE, UnitOfMass, UnitOfTemperature, UnitOfTime
from homeassistant.util import dt as dt_util

from .const import DOMAIN, DATA_COORDINATORS
from .coordinator import AmsPrinterCoordinator
from .entity import AmsEntity, AmsSlotEntity, AmsUnitEntity, async_track_members


@dataclass(frozen=True, kw_only=True)
class AmsPrinterSensorDescription(SensorEntityDescription):
    """A printer sensor and the way it reads its value out of the coordinator."""

    value: Callable[[AmsPrinterCoordinator], Any]
    attributes: Callable[[AmsPrinterCoordinator], dict] | None = None


def _progress(coordinator: AmsPrinterCoordinator):
    """The print progress in percent, or None while no layer count is known.

    Layers are what the backend reports, so they are what the progress is built
    from. It stays None rather than 0 for a printer that is idle, because a
    finished print and a print that has not started would otherwise look the
    same on a graph.
    """
    job = coordinator.print_job
    total = job.get("totalLayers")
    layer = job.get("layerNum")
    if not total or layer is None:
        return None
    return min(round(layer / total * 100, 1), 100)


def _timestamp(value):
    """Parses a backend timestamp, which is ISO 8601 in UTC or absent."""
    if not value:
        return None
    parsed = dt_util.parse_datetime(value)
    return dt_util.as_utc(parsed) if parsed else None


PRINTER_SENSORS: tuple[AmsPrinterSensorDescription, ...] = (
    AmsPrinterSensorDescription(
        key="print_state",
        translation_key="print_state",
        icon="mdi:printer-3d",
        value=lambda c: c.status.get("gcodeState"),
        attributes=lambda c: {
            "job_name": c.print_job.get("jobName"),
            "layer": c.print_job.get("layerNum"),
            "total_layers": c.print_job.get("totalLayers"),
            "consumption_booked": c.print_job.get("consumptionBooked"),
        },
    ),
    AmsPrinterSensorDescription(
        key="print_progress",
        translation_key="print_progress",
        icon="mdi:progress-clock",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=_progress,
    ),
    AmsPrinterSensorDescription(
        key="last_ams_update",
        translation_key="last_ams_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda c: _timestamp(c.status.get("lastMqttAmsUpdate")),
    ),
    AmsPrinterSensorDescription(
        key="last_printer_message",
        translation_key="last_printer_message",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda c: _timestamp(c.status.get("lastMqttUpdate")),
    ),
    AmsPrinterSensorDescription(
        key="backend_version",
        translation_key="backend_version",
        icon="mdi:tag-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda c: c.status.get("VERSION"),
        attributes=lambda c: {
            "mode": c.status.get("MODE"),
            "legacy_mode": c.status.get("LEGACY_MODE"),
            "spoolman_url": c.status.get("SPOOLMAN_URL"),
        },
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Sets up the printer, AMS unit and slot sensors of this entry."""
    coordinators = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATORS]

    entities = [
        AmsPrinterSensor(coordinator, description)
        for coordinator in coordinators.values()
        for description in PRINTER_SENSORS
    ]
    async_add_entities(entities)

    for coordinator in coordinators.values():
        async_track_members(
            entry,
            coordinator,
            async_add_entities,
            lambda c=coordinator: c.ams_units,
            lambda ams_id, c=coordinator: [
                AmsHumiditySensor(c, ams_id),
                AmsHumidityLevelSensor(c, ams_id),
                AmsTemperatureSensor(c, ams_id),
                AmsDryingRemainingSensor(c, ams_id),
            ],
        )
        async_track_members(
            entry,
            coordinator,
            async_add_entities,
            lambda c=coordinator: c.slots,
            lambda ams_id, c=coordinator: [
                AmsSlotSensor(c, ams_id),
                AmsSlotWeightSensor(c, ams_id),
                AmsSlotPercentageSensor(c, ams_id),
            ],
        )


class AmsPrinterSensor(AmsEntity, SensorEntity):
    """One reading about the printer itself, its backend or its current print."""

    entity_description: AmsPrinterSensorDescription

    def __init__(self, coordinator: AmsPrinterCoordinator, description: AmsPrinterSensorDescription):
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self):
        return self.entity_description.value(self.coordinator)

    @property
    def extra_state_attributes(self):
        if not self.entity_description.attributes:
            return None
        return self.entity_description.attributes(self.coordinator)


class AmsHumiditySensor(AmsUnitEntity, SensorEntity):
    """The humidity inside one AMS unit in percent."""

    _attr_translation_key = "ams_humidity"
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, ams_id):
        super().__init__(coordinator, "ams_humidity", ams_id)

    @property
    def native_value(self):
        return self.unit.get("humidityPercent")


class AmsHumidityLevelSensor(AmsUnitEntity, SensorEntity):
    """The humidity level 1 to 5 an AMS shows as its drop icons.

    Kept beside the percentage because the two come from different fields and an
    AMS that reports only the level exists: the percentage is then empty and the
    level is the only reading there is.
    """

    _attr_translation_key = "ams_humidity_level"
    _attr_icon = "mdi:water-percent"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, ams_id):
        super().__init__(coordinator, "ams_humidity_level", ams_id)

    @property
    def native_value(self):
        return self.unit.get("humidity")


class AmsTemperatureSensor(AmsUnitEntity, SensorEntity):
    """The temperature inside one AMS unit."""

    _attr_translation_key = "ams_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, ams_id):
        super().__init__(coordinator, "ams_temperature", ams_id)

    @property
    def native_value(self):
        return self.unit.get("temperature")


class AmsDryingRemainingSensor(AmsUnitEntity, SensorEntity):
    """How many minutes of drying are left in one AMS unit.

    Only a unit with a dryer reports the drying block at all, so this stays
    unavailable on an AMS that cannot dry rather than claiming zero minutes.
    """

    _attr_translation_key = "ams_drying_remaining"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, coordinator, ams_id):
        super().__init__(coordinator, "ams_drying_remaining", ams_id)

    @property
    def available(self) -> bool:
        return super().available and self.unit.get("drying") is not None

    @property
    def native_value(self):
        return (self.unit.get("drying") or {}).get("remainingMinutes")

    @property
    def extra_state_attributes(self):
        drying = self.unit.get("drying") or {}
        return {
            "target_temperature": drying.get("targetTemp"),
            "duration_hours": drying.get("durationHours"),
            "filament": drying.get("filament"),
        }


def _remaining(slot: dict, legacy_mode: bool):
    """Resolves what is left on the spool in a slot.

    The same resolution the backend dashboard makes, so both show one figure:
    the AMS RFID remain percentage is the source only in legacy mode, because
    the G-code tracking does not keep it current. Wherever a Spoolman spool is
    linked, its weight wins, and the total is then the filament weight rather
    than the value the tag carries. The one deliberate difference is the missing
    reading below.

    @returns weight in grams, percentage and total weight, each possibly None
    """
    slot_data = slot.get("slot") or {}
    remain = slot_data.get("remain")
    tray_weight = slot_data.get("tray_weight")

    # The AMS reports -1 while it has no reading, for the first seconds after a
    # spool goes in and for every spool without an RFID tag. The dashboard prints
    # that number, a sensor may not: a negative percentage is not a measurement
    # and it would sit in the history forever.
    if remain is not None and remain < 0:
        remain = None

    weight = slot.get("correctedWeight")
    if weight is None and remain is not None and tray_weight:
        weight = round(tray_weight / 100 * remain)

    percentage = slot.get("correctedRemain")
    if percentage is None:
        percentage = remain

    total = tray_weight
    spool = slot.get("existingSpool") or {}
    linked = slot.get("connectedViaTag") or slot.get("connectedViaMapping")

    if not legacy_mode and linked and spool.get("remaining_weight") is not None:
        weight = round(spool["remaining_weight"])
        full = (spool.get("filament") or {}).get("weight")
        if spool.get("remaining_percentage") is not None:
            percentage = round(spool["remaining_percentage"])
        elif full:
            percentage = round(spool["remaining_weight"] / full * 100)
        if full:
            total = round(full)

    return weight, percentage, total


class AmsSlotSensor(AmsSlotEntity, SensorEntity):
    """What sits in one AMS slot.

    The state is the filament name, which is what a dashboard shows, and
    everything else about the slot rides along as an attribute. That keeps the
    slot readable as a single entity without an entity per field.
    """

    _attr_translation_key = "slot"
    _attr_icon = "mdi:printer-3d-nozzle"

    def __init__(self, coordinator, ams_id):
        super().__init__(coordinator, "slot", ams_id)

    @property
    def native_value(self):
        slot = self.slot
        # An empty slot has no filament name, and its slot state is the only
        # thing there is to show.
        return slot.get("filamentName") or slot.get("slotState")

    @property
    def extra_state_attributes(self):
        slot = self.slot
        slot_data = slot.get("slot") or {}
        weight, percentage, total = _remaining(slot, bool(self.coordinator.status.get("LEGACY_MODE")))

        return {
            "ams_slot": self._ams_id,
            "slot_state": slot.get("slotState"),
            "material": slot.get("material"),
            "vendor": slot.get("vendor"),
            "filament_name": slot.get("filamentName"),
            "color": slot_data.get("tray_color"),
            "colors": slot_data.get("cols"),
            "tray_type": slot_data.get("tray_type"),
            "tray_uuid": slot_data.get("tray_uuid"),
            "remaining_weight": weight,
            "remaining_percentage": percentage,
            "total_weight": total,
            "spool_id": slot.get("spoolmanId"),
            "connected_via_tag": slot.get("connectedViaTag"),
            "connected_via_mapping": slot.get("connectedViaMapping"),
            "archived": slot.get("archived"),
            "action": slot.get("option"),
            "error": slot.get("error"),
        }


class AmsSlotWeightSensor(AmsSlotEntity, SensorEntity):
    """The grams left on the spool in one slot."""

    _attr_translation_key = "slot_remaining_weight"
    _attr_device_class = SensorDeviceClass.WEIGHT
    _attr_native_unit_of_measurement = UnitOfMass.GRAMS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, ams_id):
        super().__init__(coordinator, "slot_remaining_weight", ams_id)

    @property
    def native_value(self):
        weight, _, _ = _remaining(self.slot, bool(self.coordinator.status.get("LEGACY_MODE")))
        return weight

    @property
    def extra_state_attributes(self):
        _, _, total = _remaining(self.slot, bool(self.coordinator.status.get("LEGACY_MODE")))
        return {"total_weight": total}


class AmsSlotPercentageSensor(AmsSlotEntity, SensorEntity):
    """How much of the spool in one slot is left, in percent."""

    _attr_translation_key = "slot_remaining_percentage"
    _attr_icon = "mdi:gauge"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, ams_id):
        super().__init__(coordinator, "slot_remaining_percentage", ams_id)

    @property
    def native_value(self):
        _, percentage, _ = _remaining(self.slot, bool(self.coordinator.status.get("LEGACY_MODE")))
        return percentage
