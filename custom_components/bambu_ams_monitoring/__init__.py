import asyncio
import logging
import re

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BackendUnauthorized, BackendUnreachable, async_fetch_printers
from .const import DOMAIN, CONF_BASE_URL, CONF_PRINTERS, CONF_API_KEY, PLATFORMS, DATA_COORDINATORS
from .coordinator import AmsPrinterCoordinator

_LOGGER = logging.getLogger(__name__)

# Printer IDs the removed duplicate handling produced: the backend ID with a
# counter appended, e.g. 22E8BJ581201877_2.
_SUFFIXED_ID = re.compile(r"^(?P<base>.+?)(?:_\d+)+$")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data.setdefault(DOMAIN, {})

    await _async_repair_printer_ids(hass, entry)
    _async_migrate_unique_ids(hass, entry)

    session = async_get_clientsession(hass)
    base_url = entry.data[CONF_BASE_URL]
    api_key = entry.data.get(CONF_API_KEY)

    coordinators = {
        printer["id"]: AmsPrinterCoordinator(hass, entry, session, base_url, api_key, printer["id"], printer["name"])
        for printer in entry.data[CONF_PRINTERS]
    }

    # Refreshed rather than set up strictly: a backend that is down must not
    # keep the entry from loading, because its entities carry the history of
    # this installation and going unavailable says more than disappearing does.
    await asyncio.gather(*(coordinator.async_refresh() for coordinator in coordinators.values()))

    hass.data[DOMAIN][entry.entry_id] = {
        CONF_BASE_URL: base_url,
        CONF_API_KEY: api_key,
        CONF_PRINTERS: entry.data[CONF_PRINTERS],
        DATA_COORDINATORS: coordinators,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_repair_printer_ids(hass: HomeAssistant, entry: ConfigEntry):
    """Point stored printer IDs back at IDs the backend actually knows.

    Earlier versions rewrote duplicate printer IDs by appending a counter. The
    backend resolves /api/status/<id> against its own list, so such an ID can
    only ever answer 404 and its switch stays unavailable forever. The rewrite
    is undone here: a stored ID the backend does not know is matched against the
    backend list without the counter and case-insensitively, because the backend
    upper-cases every serial it stores.

    A rejected API key aborts the setup into the reauth flow. Everything below
    this point would fail the same way, and asking for a key once is a better
    answer than a set of entities that all go unavailable.
    """
    stored = entry.data.get(CONF_PRINTERS, [])
    if not stored:
        return

    base_url = entry.data[CONF_BASE_URL].rstrip("/")
    session = async_get_clientsession(hass)

    try:
        backend = await async_fetch_printers(session, base_url, entry.data.get(CONF_API_KEY))
    except BackendUnauthorized as err:
        raise ConfigEntryAuthFailed("The backend does not accept the API key of this entry") from err
    except BackendUnreachable as err:
        # Nothing to repair against; the next setup tries again.
        _LOGGER.debug("Cannot read the printer list for the ID repair: %s", err)
        return

    known = {p["id"] for p in backend}
    by_upper = {p["id"].upper(): p["id"] for p in backend}

    repaired = []
    changes = {}

    for printer in stored:
        pid = printer["id"]
        if pid in known:
            repaired.append(printer)
            continue

        candidate = pid
        match = _SUFFIXED_ID.match(pid)
        if match:
            candidate = match.group("base")

        new_id = by_upper.get(candidate.upper())
        if not new_id:
            repaired.append(printer)
            continue

        changes[pid] = new_id
        repaired.append({**printer, "id": new_id})

    if not changes:
        return

    for old_id, new_id in changes.items():
        _LOGGER.info("Repaired printer ID %s to %s, the ID the backend reports", old_id, new_id)

    _async_move_devices(hass, entry, changes)
    hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_PRINTERS: repaired})


def _async_move_devices(hass: HomeAssistant, entry: ConfigEntry, changes: dict):
    """Carry a device over to the repaired printer ID, keeping its entities."""
    registry = dr.async_get(hass)

    for old_id, new_id in changes.items():
        device = registry.async_get_device(identifiers={(DOMAIN, old_id)})
        if not device:
            continue
        if registry.async_get_device(identifiers={(DOMAIN, new_id)}):
            # The target already exists; the entity below simply moves onto it.
            continue
        registry.async_update_device(device.id, new_identifiers={(DOMAIN, new_id)})


def _async_migrate_unique_ids(hass: HomeAssistant, entry: ConfigEntry):
    """Rewrite entity unique IDs to the entry-scoped scheme.

    They used to be `ams_monitoring_<printer>`, which is the same string in
    every integration instance, so a second instance holding the same printer
    lost its entity. Migrating rather than renaming keeps the entity ID and the
    history of an existing installation.
    """
    registry = er.async_get(hass)

    for printer in entry.data.get(CONF_PRINTERS, []):
        new_unique_id = f"{entry.entry_id}_ams_monitoring_{printer['id']}"
        if registry.async_get_entity_id("switch", DOMAIN, new_unique_id):
            continue

        for old_unique_id in _legacy_unique_ids(printer["id"]):
            entity_id = registry.async_get_entity_id("switch", DOMAIN, old_unique_id)
            if not entity_id:
                continue
            if registry.async_get(entity_id).config_entry_id != entry.entry_id:
                # Belongs to another instance, which keeps its own entity.
                continue
            registry.async_update_entity(entity_id, new_unique_id=new_unique_id)
            break


def _legacy_unique_ids(printer_id: str):
    """The unique IDs an earlier version could have written for this printer."""
    yield f"ams_monitoring_{printer_id}"
    # The repair above may just have renamed the printer; its entity still
    # carries the ID the old duplicate handling invented.
    for suffix in range(2, 11):
        yield f"ams_monitoring_{printer_id}_{suffix}"


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Apply options changes by merging them into entry.data and reloading."""
    if entry.options:
        hass.config_entries.async_update_entry(entry, data={**entry.data, **entry.options}, options={})
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
