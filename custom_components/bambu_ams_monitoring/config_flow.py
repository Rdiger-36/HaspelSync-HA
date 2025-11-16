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
    """Config flow for the Bambu AMS Monitoring integration."""

    VERSION = 1

    def __init__(self):
        self._base_url = None
        self._printers_raw = None
        self._backend_dup_list = []
        self._ha_dup_results = None


    # -------------------------------------------------------------------------
    # STEP 1 – ENTER BASE URL
    # -------------------------------------------------------------------------
    async def async_step_user(self, user_input=None):
        errors = {}
        placeholders = {}

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required(CONF_BASE_URL): str,
                }),
                errors=errors,
                description_placeholders=placeholders
            )

        base_url = user_input[CONF_BASE_URL].rstrip("/")

        await self.async_set_unique_id(base_url)
        self._abort_if_unique_id_configured()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{base_url}/api/printers") as resp:
                    if resp.status != 200:
                        raise Exception()
                    printers = await resp.json()

        except Exception:
            errors["base"] = CONF_ERR_CANNOT_CONNECT

        else:
            # Backend-Duplikate normalisieren
            normalized = []
            seen = {}
            backend_dups = []

            for p in printers:
                pid = p["id"]
                if pid not in seen:
                    seen[pid] = 1
                    normalized.append(p)
                else:
                    backend_dups.append(pid)
                    seen[pid] += 1
                    new_id = f"{pid}_{seen[pid]}"
                    new_p = p.copy()
                    new_p["id"] = new_id
                    normalized.append(new_p)

            self._base_url = base_url
            self._printers_raw = normalized
            self._backend_dup_list = backend_dups

            return await self.async_step_select_printers()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_BASE_URL, default=base_url): str
            }),
            errors=errors,
            description_placeholders=placeholders
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

        if self._backend_dup_list:
            placeholders = {
                "backend_dup_fixed":
                    "Automatically corrected duplicate printer IDs: " +
                    ", ".join(self._backend_dup_list)
            }
        else:
            placeholders = {"backend_dup_fixed": ""}

        if user_input is None:
            return self.async_show_form(
                step_id="select_printers",
                data_schema=vol.Schema({
                    vol.Required(CONF_PRINTERS): cv.multi_select(printer_names)
                }),
                errors={},
                description_placeholders=placeholders
            )

        selected = user_input[CONF_PRINTERS]

        # HA-weiten Duplikatcheck
        existing_ids = set()
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.entry_id == self.context.get("entry_id"):
                continue
            for p in entry.data.get(CONF_PRINTERS, []):
                existing_ids.add(p["id"])

        def base_id(pid: str):
            return pid.split("_")[0] if "_" in pid else pid

        existing_base_ids = {base_id(pid) for pid in existing_ids}
        selected_base_ids = {base_id(pid) for pid in selected}

        real_conflicts = selected_base_ids.intersection(existing_base_ids)

        if real_conflicts:
            self._ha_dup_results = []

            for pid in selected:
                base = base_id(pid)

                if base in real_conflicts:
                    # Anzahl bisheriger IDs mit dieser Basis
                    existing_count = sum(1 for e in existing_ids if base_id(e) == base)
                    # neue eindeutige ID
                    new_id = f"{pid}_{existing_count + 1}"

                    self._ha_dup_results.append({
                        "old": pid,
                        "new": new_id
                    })
                else:
                    self._ha_dup_results.append({
                        "old": pid,
                        "new": pid
                    })

            return await self.async_step_fix_duplicates()

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

    async def async_step_fix_duplicates(self, user_input=None):
        """Show screen explaining duplicate fix."""
        assert self._ha_dup_results is not None

        msg = ""
        for item in self._ha_dup_results:
            if item["old"] != item["new"]:
                msg += f"● {item['old']} → {item['new']}\n"
            else:
                msg += f"● {item['old']} (unchanged)\n"

        if user_input is None:
            return self.async_show_form(
                step_id="fix_duplicates",
                data_schema=vol.Schema({}),
                errors={},
                description_placeholders={"duplicate_list": msg}
            )

        fixed_ids = [i["new"] for i in self._ha_dup_results]

        # Map der originellen IDs → Namen
        printer_map = {p["id"]: p["name"] for p in self._printers_raw}

        # Erzeugte Entities
        printers_final = []

        for item in self._ha_dup_results:
            old = item["old"]
            new = item["new"]

            # Name immer basierend auf der originalen ID
            name = printer_map.get(old)

            printers_final.append({
                "id": new,
                "name": name
            })

        return self.async_create_entry(
            title=f"Bambu AMS Monitoring ({self._base_url})",
            data={
                CONF_BASE_URL: self._base_url,
                CONF_PRINTERS: printers_final
            }
        )

