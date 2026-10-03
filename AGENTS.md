# HaspelSync for Home Assistant

A Home Assistant custom integration. It toggles the monitoring state of an external backend, [HaspelSync](https://github.com/Rdiger-36/HaspelSync), called bambulab-ams-spoolman-filamentstatus before its 1.3.0, and mirrors what that backend knows about a printer: its AMS slots, its AMS units and its current print. It holds no printer logic of its own: every state it shows comes from that backend over HTTP.

## Intent Layer

**Before modifying code in a subdirectory, read its AGENTS.md first** to understand local patterns and invariants.

The whole integration is roughly 5k tokens in a single package, so it carries no child nodes. Add one under `custom_components/haspelsync/` only if that package grows past 20k tokens.

## Entry Points

| File | Role |
|------|------|
| `custom_components/haspelsync/__init__.py` | Sets up and unloads a config entry, repairs stored printer IDs, migrates entity unique IDs |
| `custom_components/haspelsync/api.py` | Auth header and the printer list read, shared by both flows and the setup |
| `custom_components/haspelsync/config_flow.py` | Two step setup: base URL and API key, then printer selection, plus the reauth step |
| `custom_components/haspelsync/options_flow.py` | Edits the printer selection of an existing entry, and replaces its API key when the key field is filled in |
| `custom_components/haspelsync/coordinator.py` | One `DataUpdateCoordinator` per printer, polls status, spools and print job |
| `custom_components/haspelsync/entity.py` | Entity bases for a printer, an AMS unit and a slot, plus the discovery helper |
| `custom_components/haspelsync/switch.py` | One `SwitchEntity` per configured printer |
| `custom_components/haspelsync/sensor.py` | Printer, AMS unit and slot sensors |
| `custom_components/haspelsync/binary_sensor.py` | Connection, attention, storage, sliced file, drying and slot state binary sensors |
| `custom_components/haspelsync/button.py` | Clear print result and reconnect buttons per printer |
| `custom_components/haspelsync/const.py` | Domain, config keys, platform list and polling constants |
| `custom_components/haspelsync/translations/` | English and German strings, keys must match the step and error IDs in both flows |

## Backend Contract

Eight endpoints, backend default port 4000. Backend 1.3.0 is the oldest this integration is built for: it is the first release that hands out API keys, the tray details and the active slot. Every endpoint needs an API key from that release on: the backend answers `/api/` only to its own Web UI and to a caller carrying a key, whether or not a Web UI password is set. The key travels as `Authorization: Bearer <key>`, is created on the backend settings page under Network access and starts with `ams_`. A backend older than that ignores the header, which is why an entry without a key is not repaired into one until a request is actually refused.

| Call | Answer |
|------|--------|
| `GET /api/printers` | `[{"id": "...", "name": "..."}]` |
| `GET /api/status/<id>` | `monitoringEnabled`, `mqttStatus`, `spoolmanStatus`, `lastMqttUpdate`, `lastMqttAmsUpdate`, `gcodeState`, `amsEnv`, `VERSION`, `MODE`, `LEGACY_MODE`, `SPOOLMAN_URL`, `activeSlot`, the slot label or null while nothing is loaded, plus 404 when the ID is unknown |
| `GET /api/spools/<id>` | One entry per AMS slot: `amsId`, `slotState`, `slot`, `existingSpool`, `connectedViaTag`, `connectedViaMapping`, `archived`, `option`, `error`, `correctedRemain`, `amsWeight`, `filamentName`, `material`, `vendor`, `spoolmanId` |
| `GET /api/print/<id>` | `gcodeState`, `jobName`, `modelTitle`, `layerNum`, `totalLayers`, `consumption`, `consumptionBooked`, `storagePresent`, `sliceFetch`, `lastPrintSummary`, and while a print is active `stage`, `stageCode`, `preparing`, `remainingMinutes`, `startedAt`, `estimatedEndAt`, the two times in epoch milliseconds. May fetch the sliced file over FTPS, so it is the slow one |
| `POST /api/printer/<id>/monitoring/start` | `{"ok": true}`, or `{"ok": false, "message": "..."}` when it was already on |
| `POST /api/printer/<id>/monitoring/stop` | Same shape |
| `POST /api/print/<id>/clear` | `{"ok": true}`, or HTTP 409 with `{"ok": false, "error": "...", "code": "clearWhilePrinting", "params": {"printer": "...", "state": "..."}}` while a print is active |
| `POST /api/printers/reconnect` | `{"ok": true, "reconnected": [...], "skipped": n}`, acts on every printer of the backend at once |

A refused call is answered with HTTP 401 and a body carrying `apiKeyRequired` when no Web UI password is set, `authRequired` when one is. Neither field is read here: the status code alone decides, because both mean the same thing for a caller that has no browser.

HTTP 403 means the backend refused the host name of the base URL. From 1.3.0 on it answers only to an IP address, `localhost`, a `.local` name and the names listed under Allowed host names on its settings page. It sends the same status for a cross site write, which a caller without an `Origin` header never triggers, so here 403 always means the host name. The flows show `host_not_allowed` for it and the coordinator logs the setting that fixes it.

A failed answer is `{"ok": false, "error": "..."}` with a 4xx or 5xx status, and from 1.3.0 on it carries `code`, a stable word such as `printerNotFound`, and `params`, the values the sentence names, wherever the backend has them. `_WORDED_ERRORS` in `button.py` maps the codes a button can meet to a translation key, so the refusal is worded in the language of Home Assistant, and a code it does not know falls back to the English sentence of the backend. `lastPrintSummary.printErrorDetails` is built the same way, a list of `{kind, code, texts}` with Bambu Lab's sentence per language, which the last print sensor reads in the Home Assistant language under `error_details`.

`slot` carries the tray fields the backend picks in `pickSlot()`, `src/uispool.js`: `tag_uid`, `tray_diameter`, `nozzle_temp_min`, `nozzle_temp_max`, `bed_temp`, `drying_temp`, `drying_time` and `k`, as numbers or null. The printer reports 0 for what it does not know and the backend turns that into null, so `k` and `bed_temp` read None on most slots.

`slot.tray_weight` is passed through as the printer sends it, a string such as `"1000"`, and an empty slot carries the number 0. `_grams()` in `sensor.py` reads it. `amsWeight` is the weight the backend derives from the RFID reading, null while there is none.

The backend publishes the whole contract as OpenAPI at `GET /api/openapi.json`.

`amsId` is the slot label the backend builds, `A1` to `D4`, `HT-A` for an AMS HT, `External` for the spool holder and `External-2` for the second holder of a dual nozzle printer. An `amsEnv` entry carries the unit letter alone, plus the `model` the printer reports for it. The backend defines both in `src/utils.js`, `convertAMSandSlot()`.

The backend upper cases every printer serial it stores, and it resolves `<id>` by exact match against its own list.

## Contracts and Invariants

- A printer ID is used exactly as `GET /api/printers` reports it. Never rewrite, suffix or case fold one before sending it. An invented ID answers 404 forever and its switch stays permanently unavailable, which is the bug the duplicate handling in the config flow used to cause.
- Entity unique IDs are scoped to the config entry: `{entry_id}_ams_monitoring_{printer_id}`. The same printer may be configured in several instances, and Home Assistant drops the second entity of a duplicate unique ID.
- The device identifier stays `(DOMAIN, printer_id)`, so all instances holding one printer attach to a single device. An AMS unit is a device of its own, `(DOMAIN, f"{printer_id}_ams_{unit}")` with the printer as `via_device`, built by `ams_device_info()` in `entity.py`. Its readings and the slots of the unit attach to it, the external holders stay on the printer.
- Nothing aborts on a duplicate: neither a base URL that is already configured nor a printer that another entry already holds.
- Changing a unique ID scheme or an ID stored in an entry requires a migration in `__init__.py`. Without one, existing installations lose their entity ID and their history.
- The domain is `haspelsync` and stays so. It was `bambu_ams_monitoring` before 1.2.0, and that rename cost every installation a manual reinstall, because Home Assistant cannot move a config entry between domains and no migration can run on an entry of a domain that no longer exists. The entity keys kept their old names across it, `ams_monitoring` for the switch for example, so the entity IDs a reinstall produces equal the old ones and the recorder history continues.
- A 401 is not a connection problem and is never retried into one. Everything that talks to the backend turns it into `ConfigEntryAuthFailed`, which is what puts the reauth step in front of the user. An entry set up before the backend asked for a key holds none, so this is also the upgrade path of every existing installation.
- The API key field of the options flow is empty on every render and the stored key is never put into it. An empty field means the stored key is kept, so it can never mean the key was cleared, and a screenshot of that dialog carries no secret.
- The API key is optional in the stored entry data and read with `entry.data.get()`. An entry written before it existed carries no key, and that is the upgrade path: the first 401 of an updated backend puts such an entry into reauth rather than failing its setup.
- An unreachable backend must never shrink an entry. The options flow keeps configured printers selectable when the printer list cannot be fetched, and a backend that is down at setup leaves the entry loaded with unavailable entities rather than raising `ConfigEntryNotReady`.
- `/api/status` decides whether a printer is reachable. The spool and print endpoints are allowed to fail on their own, so a slow sliced file cannot take the connection sensors down.
- The remaining weight and percentage of a slot follow the same resolution the backend dashboard makes, see `_remaining()` in `sensor.py`. Both have to keep agreeing, otherwise the same spool reads differently in the two places. A slot counts as linked there when it is linked by tag, by mapping or holds an archived spool. The single deviation is the AMS reading of -1, which means no reading and becomes an empty state here rather than a negative percentage.
- Slots and AMS units are discovered on every coordinator update, not only at setup. The backend answers with an empty spool list until its first AMS update, so entities built once at setup would be missing on a fresh install.
- The options flow relies on the `config_entry` property of its base class, which needs Home Assistant 2024.11. Assigning `self.config_entry` is removed in 2025.12. `hacs.json` pins that minimum.
- `manifest.json` `version` and the git tag belong together. HACS reads the manifest.

## Patterns

Adding a platform, for example a number:

1. Write the platform module next to `switch.py`.
2. Add it to `PLATFORMS` in `const.py`, which both `async_forward_entry_setups` and `async_unload_platforms` read.
3. Derive from `AmsEntity`, `AmsUnitEntity` or `AmsSlotEntity` in `entity.py`. They build the unique ID as `{entry_id}_{key}_{printer_id}`, attach the printer device and answer availability.
4. Read from the coordinator rather than from the network. Nothing below `coordinator.py` opens an HTTP request of its own, apart from the switch and the buttons, which post an action through `async_post_action()` in `api.py`.

Adding an entity that exists per slot or per AMS unit: register it in the `async_track_members` call of its platform, so it appears with a unit that is plugged in later.

Adding a value to an entity: give every new entity a `translation_key` and add its name to both translation files under `entity`. A slot name uses the `{slot}` placeholder, which the entity base fills in, because four slots share one AMS device. A unit entity needs none: its device already names the unit.

Raising an error to the user, from a button for example: raise `HomeAssistantError` with `translation_domain=DOMAIN` and a `translation_key`, and add the message to both translation files under `exceptions`. A message written into the code stays English whatever language is set. A refusal the backend answers with a `code` gets a line in `_WORDED_ERRORS` in `button.py`, naming the `params` the message uses as placeholders, because a placeholder without a value leaves the message unrendered.

Adding a flow step: add the step ID and every data key to both `translations/en.json` and `translations/de.json`. A missing key shows up as a raw key in the UI.

## Anti-patterns

- Do not open an `aiohttp.ClientSession` in the entity layer, and no longer in a flow either. The shared Home Assistant session is passed in or taken from `async_get_clientsession()`.
- Do not send a request to the backend without `auth_headers()`. Every call needs the key, and a new call site that forgets it fails only on an installation that has one.
- Do not treat HTTP 200 alone as success on the start and stop endpoints. They answer `ok: false` when the state was already set.
- Do not make the config flow claim a unique ID. That would block the second instance for a printer or a backend.
- Do not add blocking IO to the update path. It runs on the event loop.
- Do not poll per entity. Everything about one printer is read in a single coordinator cycle.

## House Rules

### Language

- Identifiers, code comments, log messages, commit messages and pull request text are written in English. User facing strings live in `translations/`, English and German.

### Punctuation

- Never use a dash as punctuation, neither an em dash nor a standalone hyphen. This covers UI strings, doc comments, inline comments, log messages, commit messages and pull request text. Use a comma, colon or full stop.
- Not punctuation, and therefore allowed: a hyphen inside a compound word (`3rd-party`, `API-Key` in German strings), and the hyphen as a structural marker, such as a bullet in a list.

### Comments

- Every function gets a comment block saying what it does. Go deep only where the behaviour is not obvious, one line for self explanatory members. Document parameters and return values only where they add something the signature does not say.
- Inline comments carry the WHY: a hidden constraint, a workaround, a subtle invariant. Never restate the code.

### Git

- Commits and pull requests carry no attribution: no `Co-Authored-By` trailer in a commit message and no "Generated with Claude Code" line in a pull request description. The repository is the owner's, and those lines are noise in the history and in the release notes.
- Commit messages are short. The subject names the change itself with a `feat:`, `fix:`, `docs:` or `chore:` prefix. A body only where the why is not obvious, and then a few lines at most.
- Branch before changing anything while on `main`. Name the branch after everything it ends up holding, and rename it when the scope grows. Rename it before its pull request is opened: GitHub closes an open pull request whose head branch is renamed.
- Never open a pull request without an explicit go ahead for that specific pull request. A general permission is not a standing one, so ask again for the next. A merged pull request is a status, not a request for the next step.
- A version bump and the tag that publishes it wait for the same explicit go, because the owner decides when a build is cut and what goes into it.
- The git remote is named `main`, not `origin`. Push with `git push -u main <branch>`. No branch may be named `main/<something>`.

### Scope

- GUI and design changes, and changes touching many references, are discussed before they are applied.
- The backend is a separate repository and is never changed from a task in this one. Where the integration needs a field the backend does not report, the integration reads it ahead and the owner builds the backend side.

## Releasing

`.github/workflows/release.yml` publishes on a `vX.Y.Z` tag and refuses one whose version does not equal `manifest.json` `version`, so bump the manifest in the same change that will be tagged. A suffix such as `1.0.2-rc.1` is published as a pre-release. The release is titled `Version X.Y.Z`, which is how every release of this repository is named, and a pre-release carries `(DEV)` behind it. No archive is attached: HACS installs this repository by copying `custom_components/haspelsync` out of the tag, and an asset it never reads only suggests otherwise.

Label every pull request when it is opened, and in any case before it is merged: `enhancement`, `bug`, `deprecation`, `documentation` or `maintenance` (refactor, build, CI, dependencies, version bump), with `ignore-for-release` to leave one out entirely. A pull request that does two things takes both labels and is listed once, under whichever section comes first. `breaking` goes on top of one of those whenever an existing installation can stop working the way it did, a caller that suddenly needs credentials for example. The generated notes are grouped by `.github/release.yml` in the same order as the backend's: Breaking Changes, New Features, Fixes, Deprecations, Documentation, Maintenance. An unlabelled pull request is not lost, it lands under Other Changes, which is where the whole of Version 1.0.2 ended up. A label added after the merge changes nothing about notes that are already written.

`.github/workflows/validate.yml` runs hassfest and the HACS action on every pull request, on `main`, and weekly, because HACS validates against requirements that move on their own.

## Verification

There is no test suite and the code cannot run outside Home Assistant. Before handing work over:

1. `python3 -m py_compile custom_components/haspelsync/*.py`
2. Load the integration in a real Home Assistant, check the log for the ID repair line, toggle a switch, then add a second instance holding the same printer and confirm both switches appear and follow each other.
3. Reach the backend directly to tell an integration bug from a backend one: `curl -H "Authorization: Bearer ams_<key>" http://<backend>:4000/api/printers`. Without the header a backend from 1.3.0 on answers 401, which says nothing about the integration.

## Related Context

- Backend repository, its own AGENTS.md and `src/routes.js` define every endpoint used here: https://github.com/Rdiger-36/HaspelSync
