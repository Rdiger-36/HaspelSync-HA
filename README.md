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
  <img src="https://img.shields.io/github/downloads/Rdiger-36/ha-bambulab-ams-spoolman-filamentstatus/total?style=flat-square&label=downloads&color=blue" alt="total downloads" />
  <img src="https://img.shields.io/github/last-commit/Rdiger-36/ha-bambulab-ams-spoolman-filamentstatus?style=flat-square&label=last%20commit" alt="last commit" />
</p>

---

> **Note:** This integration depends on a working [bambulab-ams-spoolman-filamentstatus](https://github.com/Rdiger-36/bambulab-ams-spoolman-filamentstatus) environment.

## Features

* Toggle monitoring per printer directly from Home Assistant
* Auto-detects all available printers from your backend
* Availability tracking: the entity shows as unavailable if the backend is unreachable
* Multi-printer support: add multiple printers in one integration instance, and the same printer in several instances
* Fully translatable, English and German included

## Requirements

| Requirement | Description |
|---|---|
| [bambulab-ams-spoolman-filamentstatus](https://github.com/Rdiger-36/bambulab-ams-spoolman-filamentstatus) | The backend service this integration connects to |
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
4. Select the printer(s) you want to monitor
5. Enjoy your toggle switch

## Configuration

After setup, you can edit the printer selection at any time:

1. Go to **Settings → Devices & Services**
2. Find **Bambu AMS Monitoring** and click **Configure**
3. Adjust your printer selection and save

## Entities

For each configured printer, the integration creates a switch entity:

| Entity | Description |
|---|---|
| `switch.ams_monitoring_<printer_name>` | Enables or disables filament monitoring for this printer |

The switch reflects the actual monitoring state from the backend and updates automatically.

The same printer may be configured in more than one integration instance, and the same backend may be added more than once. Each instance creates its own switch, so the second one is named `switch.ams_monitoring_<printer_name>_2`. All switches of a printer control the same backend state and follow each other on the next update.

## Troubleshooting

**Config flow fails to load**
Make sure the backend is reachable at the URL you entered and responds at `/api/printers`.

**Entity shows as unavailable**
Either the backend is not reachable, or it does not know the printer ID the entity was configured with. Check that the service is running and that the URL and port are correct:

```
curl http://<backend>:4000/api/printers
```

The IDs in that answer are the ones the backend accepts. An ID left over from an earlier version of this integration is corrected automatically when the integration loads, so a reload of the integration is worth trying before anything else.

**Changes after editing printers do not take effect**
The integration reloads automatically after saving. If not, restart Home Assistant manually.

## Related Projects

* [bambulab-ams-spoolman-filamentstatus](https://github.com/Rdiger-36/bambulab-ams-spoolman-filamentstatus): the backend this integration depends on
* [Spoolman](https://github.com/Donkie/Spoolman): filament inventory management
