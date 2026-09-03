<p align="center">
  <img src="custom_components/bambu_ams_monitoring/icon.png" width="120" alt="Bambu AMS Monitoring icon" />
</p>

<h1 align="center">Bambu AMS Monitoring</h1>

<p align="center">
  A custom Home Assistant integration to monitor and control your Bambu Lab AMS filament status.<br/>
  Connects to the <a href="https://github.com/Rdiger-36/bambulab-ams-spoolman-filamentstatus">bambulab-ams-spoolman-filamentstatus</a> backend with a simple toggle switch per printer.
</p>

<p align="center">
  <img src="https://img.shields.io/github/v/release/Rdiger-36/ha-bambulab-ams-spoolman-filamentstatus?style=flat-square&label=version&color=blue" alt="version" />
  <img src="https://img.shields.io/badge/HACS-Custom-orange?style=flat-square&logo=home-assistant&logoColor=white" alt="HACS" />
  <img src="https://img.shields.io/badge/Home%20Assistant-compatible-41BDF5?style=flat-square&logo=home-assistant&logoColor=white" alt="Home Assistant" />
  <img src="https://img.shields.io/badge/license-GPL--3.0-green?style=flat-square" alt="license" />
  <img src="https://img.shields.io/badge/maintained-yes-brightgreen?style=flat-square" alt="maintained" />
</p>

<p align="center">
  <img src="https://img.shields.io/github/stars/Rdiger-36/ha-bambulab-ams-spoolman-filamentstatus?style=flat-square&color=yellow" alt="stars" />
  <img src="https://img.shields.io/github/forks/Rdiger-36/ha-bambulab-ams-spoolman-filamentstatus?style=flat-square&color=orange" alt="forks" />
  <img src="https://img.shields.io/github/issues/Rdiger-36/ha-bambulab-ams-spoolman-filamentstatus?style=flat-square" alt="open issues" />
  <img src="https://img.shields.io/github/last-commit/Rdiger-36/ha-bambulab-ams-spoolman-filamentstatus?style=flat-square&label=last%20commit" alt="last commit" />
</p>

---

> **Note:** This integration depends on a working [bambulab-ams-spoolman-filamentstatus](https://github.com/Rdiger-36/bambulab-ams-spoolman-filamentstatus) environment.

## Features

* Toggle monitoring per printer directly from Home Assistant
* One sensor per AMS slot: filament, material, vendor, colour, remaining weight and the Spoolman link
* Humidity, temperature and drying state per AMS unit
* Print state and progress, plus connection sensors for the printer and for Spoolman
* Auto-detects all available printers from your backend
* Availability tracking: the entities show as unavailable if the backend is unreachable
* Multi-printer support: add multiple printers in one integration instance, and the same printer in several instances
* Fully translatable, English and German included

## Requirements

| Requirement | Description |
|---|---|
| [bambulab-ams-spoolman-filamentstatus](https://github.com/Rdiger-36/bambulab-ams-spoolman-filamentstatus) | The backend service this integration connects to |
| An API key of that backend | Backend 1.3.0 and newer answers its API only to the Web UI and to callers carrying a key. Create one on the settings page of the backend, under **Network access** |
| [Spoolman](https://github.com/Donkie/Spoolman) | Filament management service |
| [HACS](https://hacs.xyz/) | Required for installation in Home Assistant |
| Home Assistant 2024.11 or newer | Older versions do not provide the config entry to the options flow, so editing the printer selection fails |

## Installation

To use this integration you need HACS. Copy the repository URL and add it as a custom repository in HACS. Then search for **Bambu AMS Monitoring** and install the integration.

```
https://github.com/Rdiger-36/ha-bambulab-ams-spoolman-filamentstatus
```

## Setup

1. Go to **Settings → Devices & Services**
2. Click **Add Integration** and search for `Bambu AMS Monitoring`
3. Enter the base URL of your backend, for example:
   ```
   http://192.168.1.100:4000
   https://ams-server.example.com
   https://myserver.com/ams
   ```
4. Enter an API key of that backend. It is created on the backend settings page under **Network access**, starts with `ams_` and is shown only once, so copy it before closing the dialog
5. Select the printer(s) you want to monitor
6. Enjoy your toggle switch

A backend older than 1.3.0 does not know API keys and ignores the one sent to it, so the field can be filled with anything there.

## Configuration

After setup, you can edit the printer selection and the API key at any time:

1. Go to **Settings → Devices & Services**
2. Find **Bambu AMS Monitoring** and click **Configure**
3. Adjust your printer selection and save

The key field of that dialog starts empty and the stored key is never shown. Leave it empty to keep the key the integration already holds, and fill it in only to replace it, for example after the key was revoked in the backend. A key the backend rejects is not saved, so the form comes back with the error rather than leaving the integration with a key that cannot work.

## Entities

Every printer becomes one device. All of its entities are polled together every 30 seconds, which is the pace the backend itself works at.

Per printer:

| Entity | Description |
|---|---|
| `switch.ams_monitoring_<printer_name>` | Enables or disables filament monitoring for this printer |
| `sensor.<printer>_print_state` | The G-code state, with job name, layer and total layers as attributes |
| `sensor.<printer>_print_progress` | The print progress in percent, derived from the layer count |
| `sensor.<printer>_last_ams_update` | When the backend last processed AMS data of this printer |
| `sensor.<printer>_last_printer_message` | When the last MQTT message arrived, diagnostic |
| `sensor.<printer>_backend_version` | The backend version, with mode and Spoolman URL as attributes, diagnostic |
| `binary_sensor.<printer>_printer_connection` | Whether the backend holds the MQTT connection, with the exact state as an attribute |
| `binary_sensor.<printer>_spoolman_connection` | Whether the backend reaches Spoolman, diagnostic |
| `binary_sensor.<printer>_needs_attention` | On when any slot reports an error or waits for an action, with the slot list as attributes |

Per AMS unit, for example A:

| Entity | Description |
|---|---|
| `sensor.<printer>_ams_a_humidity` | Humidity in percent |
| `sensor.<printer>_ams_a_humidity_level` | The level 1 to 5 the AMS shows as drop icons, diagnostic |
| `sensor.<printer>_ams_a_temperature` | Temperature inside the unit |
| `binary_sensor.<printer>_ams_a_drying` | On while the unit is drying, with target temperature and duration as attributes |
| `sensor.<printer>_ams_a_drying_remaining` | Minutes of drying left |

The last two exist only on a unit with a dryer, an AMS 2 Pro or an AMS HT. An AMS Lite reports no readings at all, so it has none of these entities while its slots are still there.

Per AMS slot, for example A1, and for the external spool holder:

| Entity | Description |
|---|---|
| `sensor.<printer>_slot_a1` | The filament in the slot, with material, vendor, colour, weights, spool ID and slot state as attributes |
| `sensor.<printer>_slot_a1_remaining_weight` | Grams left, from Spoolman where the slot is linked |
| `sensor.<printer>_slot_a1_remaining` | The same figure in percent |
| `binary_sensor.<printer>_slot_a1_problem` | On when the backend reports an error for the slot or the spool is archived |
| `binary_sensor.<printer>_slot_a1_action_required` | On when a spool has to be created, merged or assigned in the backend Web UI |
| `binary_sensor.<printer>_slot_a1_linked_to_spoolman` | Whether the slot is linked by RFID tag or by a manual assignment, diagnostic |

Slots and AMS units appear as soon as the backend reports them, so a unit plugged in later brings its entities with it without a reload.

The switch reflects the actual monitoring state from the backend and updates automatically.

The same printer may be configured in more than one integration instance, and the same backend may be added more than once. Each instance creates its own switch, so the second one is named `switch.ams_monitoring_<printer_name>_2`. All switches of a printer control the same backend state and follow each other on the next update.

## Troubleshooting

**Config flow fails to load**
Make sure the backend is reachable at the URL you entered and responds at `/api/printers`.

**Home Assistant asks to re-authenticate the integration**
The backend answered with HTTP 401, which means it does not accept the API key any more: the key was revoked, or the backend was updated to 1.3.0 while this integration still held none. Create a key under **Network access** on the backend settings page and enter it in the dialog Home Assistant shows. Nothing else about the entry changes, and every entity keeps its history.

**Entities show as unavailable**
Either the backend is not reachable, or it does not know the printer ID the entity was configured with. Check that the service is running and that the URL and port are correct:

```
curl -H "Authorization: Bearer ams_your_key" http://<backend>:4000/api/printers
```

The IDs in that answer are the ones the backend accepts. An ID left over from an earlier version of this integration is corrected automatically when the integration loads, so a reload of the integration is worth trying before anything else.

**Slot or AMS entities are missing**
The backend reports slots only after its first AMS update, and it reports environment readings only for an AMS that has them. Turn monitoring on, wait for one update interval, and check what the backend answers:

```
curl -H "Authorization: Bearer ams_your_key" http://<backend>:4000/api/spools/<printer-id>
```

**Changes after editing printers do not take effect**
The integration reloads automatically after saving. If not, restart Home Assistant manually.

## Related Projects

* [bambulab-ams-spoolman-filamentstatus](https://github.com/Rdiger-36/bambulab-ams-spoolman-filamentstatus): the backend this integration depends on
* [Spoolman](https://github.com/Donkie/Spoolman): filament inventory management
