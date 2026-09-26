# Bambu AMS Monitoring

A Home Assistant custom integration. It toggles the monitoring state of an external backend, [bambulab-ams-spoolman-filamentstatus](https://github.com/Rdiger-36/bambulab-ams-spoolman-filamentstatus), and mirrors what that backend knows about a printer: its AMS slots, its AMS units and its current print. It holds no printer logic of its own: every state it shows comes from that backend over HTTP.

## Intent Layer

**Before modifying code in a subdirectory, read its AGENTS.md first** to understand local patterns and invariants.

The whole integration is roughly 5k tokens in a single package, so it carries no child nodes. Add one under `custom_components/bambu_ams_monitoring/` only if that package grows past 20k tokens.

## Entry Points

| File | Role |
|------|------|
| `custom_components/bambu_ams_monitoring/__init__.py` | Sets up and unloads a config entry, repairs stored printer IDs, migrates entity unique IDs |
| `custom_components/bambu_ams_monitoring/config_flow.py` | Two step setup: base URL, then printer selection |
| `custom_components/bambu_ams_monitoring/options_flow.py` | Edits the printer selection of an existing entry |
| `custom_components/bambu_ams_monitoring/coordinator.py` | One `DataUpdateCoordinator` per printer, polls status, spools and print job |
| `custom_components/bambu_ams_monitoring/entity.py` | Entity bases for a printer, an AMS unit and a slot, plus the discovery helper |
| `custom_components/bambu_ams_monitoring/switch.py` | One `SwitchEntity` per configured printer |
| `custom_components/bambu_ams_monitoring/sensor.py` | Printer, AMS unit and slot sensors |
| `custom_components/bambu_ams_monitoring/binary_sensor.py` | Connection, attention, drying and slot state binary sensors |
| `custom_components/bambu_ams_monitoring/const.py` | Domain, config keys, platform list and polling constants |
| `custom_components/bambu_ams_monitoring/translations/` | English and German strings, keys must match the step and error IDs in both flows |

## Backend Contract

Six endpoints, all unauthenticated, backend default port 4000:

| Call | Answer |
|------|--------|
| `GET /api/printers` | `[{"id": "...", "name": "..."}]` |
| `GET /api/status/<id>` | `monitoringEnabled`, `mqttStatus`, `spoolmanStatus`, `lastMqttUpdate`, `lastMqttAmsUpdate`, `gcodeState`, `amsEnv`, `VERSION`, `MODE`, `LEGACY_MODE`, plus 404 when the ID is unknown |
| `GET /api/spools/<id>` | One entry per AMS slot: `amsId`, `slotState`, `slot`, `existingSpool`, `connectedViaTag`, `connectedViaMapping`, `archived`, `option`, `error`, `correctedRemain`, `correctedWeight` |
| `GET /api/print/<id>` | `gcodeState`, `jobName`, `layerNum`, `totalLayers`, `consumption`, `consumptionBooked`. May fetch the sliced file over FTPS, so it is the slow one |
| `POST /api/printer/<id>/monitoring/start` | `{"ok": true}`, or `{"ok": false, "message": "..."}` when it was already on |
| `POST /api/printer/<id>/monitoring/stop` | Same shape |

`amsId` is the slot label the backend builds, `A1` to `D4`, `HT-A` for an AMS HT and `External` for the spool holder. An `amsEnv` entry carries the unit letter alone. The backend defines both in `src/utils.js`, `convertAMSandSlot()`.

The backend upper cases every printer serial it stores, and it resolves `<id>` by exact match against its own list.

## Contracts and Invariants

- A printer ID is used exactly as `GET /api/printers` reports it. Never rewrite, suffix or case fold one before sending it. An invented ID answers 404 forever and its switch stays permanently unavailable, which is the bug the duplicate handling in the config flow used to cause.
- Entity unique IDs are scoped to the config entry: `{entry_id}_ams_monitoring_{printer_id}`. The same printer may be configured in several instances, and Home Assistant drops the second entity of a duplicate unique ID.
- The device identifier stays `(DOMAIN, printer_id)`, so all instances holding one printer attach to a single device.
- Nothing aborts on a duplicate: neither a base URL that is already configured nor a printer that another entry already holds.
- Changing a unique ID scheme or an ID stored in an entry requires a migration in `__init__.py`. Without one, existing installations lose their entity ID and their history.
- An unreachable backend must never shrink an entry. The options flow keeps configured printers selectable when the printer list cannot be fetched, and a backend that is down at setup leaves the entry loaded with unavailable entities rather than raising `ConfigEntryNotReady`.
- `/api/status` decides whether a printer is reachable. The spool and print endpoints are allowed to fail on their own, so a slow sliced file cannot take the connection sensors down.
- The remaining weight and percentage of a slot follow the same resolution the backend dashboard makes, see `_remaining()` in `sensor.py`. Both have to keep agreeing, otherwise the same spool reads differently in the two places. The single deviation is the AMS reading of -1, which means no reading and becomes an empty state here rather than a negative percentage.
- Slots and AMS units are discovered on every coordinator update, not only at setup. The backend answers with an empty spool list until its first AMS update, so entities built once at setup would be missing on a fresh install.
- The options flow relies on the `config_entry` property of its base class, which needs Home Assistant 2024.11. Assigning `self.config_entry` is removed in 2025.12. `hacs.json` pins that minimum.
- `manifest.json` `version` and the git tag belong together. HACS reads the manifest.

## Patterns

Adding a platform, for example a number:

1. Write the platform module next to `switch.py`.
2. Add it to `PLATFORMS` in `const.py`, which both `async_forward_entry_setups` and `async_unload_platforms` read.
3. Derive from `AmsEntity`, `AmsUnitEntity` or `AmsSlotEntity` in `entity.py`. They build the unique ID as `{entry_id}_{key}_{printer_id}`, attach the printer device and answer availability.
4. Read from the coordinator rather than from the network. Nothing below `coordinator.py` opens an HTTP request of its own, apart from the switch, which posts an action.

Adding an entity that exists per slot or per AMS unit: register it in the `async_track_members` call of its platform, so it appears with a unit that is plugged in later.

Adding a value to an entity: give every new entity a `translation_key` and add its name to both translation files under `entity`. A slot or unit name uses the `{slot}` or `{ams}` placeholder, which the entity bases fill in.

Adding a flow step: add the step ID and every data key to both `translations/en.json` and `translations/de.json`. A missing key shows up as a raw key in the UI.

## Anti-patterns

- Do not open an `aiohttp.ClientSession` in the entity layer. The shared Home Assistant session is passed in.
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

`.github/workflows/release.yml` publishes on a `vX.Y.Z` tag and refuses one whose version does not equal `manifest.json` `version`, so bump the manifest in the same change that will be tagged. A suffix such as `1.0.2-rc.1` is published as a pre-release. The release is titled `Version X.Y.Z`, which is how every release of this repository is named, and a pre-release carries `(DEV)` behind it. No archive is attached: HACS installs this repository by copying `custom_components/bambu_ams_monitoring` out of the tag, and an asset it never reads only suggests otherwise.

Label every pull request when it is opened, and in any case before it is merged: `enhancement`, `bug`, `deprecation`, `documentation` or `maintenance` (refactor, build, CI, dependencies, version bump), with `ignore-for-release` to leave one out entirely. A pull request that does two things takes both labels and is listed once, under whichever section comes first. `breaking` goes on top of one of those whenever an existing installation can stop working the way it did, a caller that suddenly needs credentials for example. The generated notes are grouped by `.github/release.yml` in the same order as the backend's: Breaking Changes, New Features, Fixes, Deprecations, Documentation, Maintenance. An unlabelled pull request is not lost, it lands under Other Changes, which is where the whole of Version 1.0.2 ended up. A label added after the merge changes nothing about notes that are already written.

`.github/workflows/validate.yml` runs hassfest and the HACS action on every pull request, on `main`, and weekly, because HACS validates against requirements that move on their own.

## Verification

There is no test suite and the code cannot run outside Home Assistant. Before handing work over:

1. `python3 -m py_compile custom_components/bambu_ams_monitoring/*.py`
2. Load the integration in a real Home Assistant, check the log for the ID repair line, toggle a switch, then add a second instance holding the same printer and confirm both switches appear and follow each other.
3. Reach the backend directly to tell an integration bug from a backend one: `curl http://<backend>:4000/api/printers`

## Related Context

- Backend repository, its own AGENTS.md and `src/routes.js` define every endpoint used here: https://github.com/Rdiger-36/bambulab-ams-spoolman-filamentstatus
