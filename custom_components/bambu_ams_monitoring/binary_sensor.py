from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory

from .const import DOMAIN, DATA_COORDINATORS, SLOT_OPTIONS_WITHOUT_WORK
from .entity import AmsEntity, AmsSlotEntity, AmsUnitEntity, async_track_members


def _needs_work(slot: dict) -> bool:
    """Says whether the backend offers an action for this slot.

    The backend sends the button label rather than a key, so the three labels
    that mean there is nothing to do are what is compared against. A slot
    without a label at all has not been evaluated yet, which is not work either.
    """
    option = slot.get("option")
    return bool(option) and option not in SLOT_OPTIONS_WITHOUT_WORK


async def async_setup_entry(hass, entry, async_add_entities):
    """Sets up the connection, AMS unit and slot binary sensors of this entry."""
    coordinators = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATORS]

    entities = []
    for coordinator in coordinators.values():
        entities.append(AmsMqttConnectedSensor(coordinator))
        entities.append(AmsSpoolmanConnectedSensor(coordinator))
        entities.append(AmsAttentionSensor(coordinator))
    async_add_entities(entities)

    for coordinator in coordinators.values():
        async_track_members(
            entry,
            coordinator,
            async_add_entities,
            lambda c=coordinator: c.ams_units,
            lambda ams_id, c=coordinator: [AmsDryingSensor(c, ams_id)],
        )
        async_track_members(
            entry,
            coordinator,
            async_add_entities,
            lambda c=coordinator: c.slots,
            lambda ams_id, c=coordinator: [
                AmsSlotProblemSensor(c, ams_id),
                AmsSlotActionSensor(c, ams_id),
                AmsSlotLinkedSensor(c, ams_id),
            ],
        )


class AmsMqttConnectedSensor(AmsEntity, BinarySensorEntity):
    """Whether the backend currently holds the MQTT connection to this printer.

    Off covers every other state the backend reports, Disconnected, Error,
    Reconnecting and Disabled, which is the state a printer with monitoring
    turned off sits in. The exact word is kept as an attribute, because those
    four mean rather different things to whoever is looking.
    """

    _attr_translation_key = "mqtt_connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator):
        super().__init__(coordinator, "mqtt_connected")

    @property
    def is_on(self):
        return self.coordinator.status.get("mqttStatus") == "Connected"

    @property
    def extra_state_attributes(self):
        return {"status": self.coordinator.status.get("mqttStatus")}


class AmsSpoolmanConnectedSensor(AmsEntity, BinarySensorEntity):
    """Whether the backend can reach Spoolman.

    A property of the backend rather than of one printer, so every configured
    printer carries the same reading. It sits on the printer device anyway,
    because that is where someone looking at a slot that stopped updating will
    look for the reason.
    """

    _attr_translation_key = "spoolman_connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator):
        super().__init__(coordinator, "spoolman_connected")

    @property
    def is_on(self):
        return self.coordinator.status.get("spoolmanStatus") == "Connected"

    @property
    def extra_state_attributes(self):
        return {"status": self.coordinator.status.get("spoolmanStatus")}


class AmsAttentionSensor(AmsEntity, BinarySensorEntity):
    """Whether any slot of this printer needs someone to look at it.

    One entity that answers the question a dashboard actually asks, so an
    automation does not have to fan out over every slot entity. The slots behind
    it are listed as attributes, split by what is wrong with them.
    """

    _attr_translation_key = "attention"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator):
        super().__init__(coordinator, "attention")

    @property
    def is_on(self):
        return bool(self._problems() or self._actions())

    @property
    def extra_state_attributes(self):
        return {"problem_slots": self._problems(), "action_slots": self._actions()}

    def _problems(self):
        """The slots the backend reports an error or an archived spool for."""
        return sorted(
            ams_id
            for ams_id, slot in self.coordinator.slots.items()
            if slot.get("error") or slot.get("archived")
        )

    def _actions(self):
        """The slots that wait for a decision in the backend Web UI."""
        return sorted(
            ams_id
            for ams_id, slot in self.coordinator.slots.items()
            if _needs_work(slot)
        )


class AmsDryingSensor(AmsUnitEntity, BinarySensorEntity):
    """Whether one AMS unit is drying."""

    _attr_translation_key = "ams_drying"
    _attr_icon = "mdi:air-filter"

    def __init__(self, coordinator, ams_id):
        super().__init__(coordinator, "ams_drying", ams_id)

    @property
    def available(self) -> bool:
        # Only an AMS with a dryer reports the block at all. Without it there is
        # no answer to give, rather than a permanent off.
        return super().available and self.unit.get("drying") is not None

    @property
    def is_on(self):
        return bool((self.unit.get("drying") or {}).get("active"))

    @property
    def extra_state_attributes(self):
        drying = self.unit.get("drying") or {}
        return {
            "remaining_minutes": drying.get("remainingMinutes"),
            "target_temperature": drying.get("targetTemp"),
            "duration_hours": drying.get("durationHours"),
            "filament": drying.get("filament"),
        }


class AmsSlotProblemSensor(AmsSlotEntity, BinarySensorEntity):
    """Whether one slot carries an error or an archived spool."""

    _attr_translation_key = "slot_problem"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, ams_id):
        super().__init__(coordinator, "slot_problem", ams_id)

    @property
    def is_on(self):
        slot = self.slot
        return bool(slot.get("error") or slot.get("archived"))

    @property
    def extra_state_attributes(self):
        slot = self.slot
        return {"error": slot.get("error"), "archived": slot.get("archived")}


class AmsSlotActionSensor(AmsSlotEntity, BinarySensorEntity):
    """Whether the backend offers an action for one slot.

    On means a spool has to be created, merged or assigned in the Web UI before
    the slot can be booked against Spoolman.
    """

    _attr_translation_key = "slot_action_required"
    _attr_icon = "mdi:hand-pointing-up"

    def __init__(self, coordinator, ams_id):
        super().__init__(coordinator, "slot_action_required", ams_id)

    @property
    def is_on(self):
        return _needs_work(self.slot)

    @property
    def extra_state_attributes(self):
        return {"action": self.slot.get("option")}


class AmsSlotLinkedSensor(AmsSlotEntity, BinarySensorEntity):
    """Whether one slot is linked to a Spoolman spool.

    A link comes from the RFID tag or from a manual assignment, and only a
    linked slot has its consumption booked, which is the reason this is worth an
    entity of its own rather than an attribute alone.
    """

    _attr_translation_key = "slot_linked"
    _attr_icon = "mdi:link-variant"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, ams_id):
        super().__init__(coordinator, "slot_linked", ams_id)

    @property
    def is_on(self):
        slot = self.slot
        return bool(slot.get("connectedViaTag") or slot.get("connectedViaMapping"))

    @property
    def extra_state_attributes(self):
        slot = self.slot
        return {
            "connected_via_tag": slot.get("connectedViaTag"),
            "connected_via_mapping": slot.get("connectedViaMapping"),
            "spool_id": slot.get("spoolmanId"),
        }
