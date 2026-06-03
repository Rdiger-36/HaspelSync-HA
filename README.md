# Bambu AMS Monitoring — Home Assistant Integration

A custom [Home Assistant](https://www.home-assistant.io/) integration to monitor and control the filament monitoring of your **Bambu Lab 3D printer** via the [bambulab-ams-spoolman-filamentstatus](https://github.com/Rdiger-36/bambulab-ams-spoolman-filamentstatus) backend.

> **Note:** This integration depends on a working [bambulab-ams-spoolman-filamentstatus](https://github.com/Rdiger-36/bambulab-ams-spoolman-filamentstatus) environment.

## Features

* Toggle monitoring per printer directly from Home Assistant
* Auto-detects all available printers from your backend
* Availability tracking — entity shows as unavailable if the backend is unreachable
* Multi-printer support — add multiple printers in one integration instance
* Fully translatable — English and German included

## Requirements

| Requirement | Description |
|---|---|
| [bambulab-ams-spoolman-filamentstatus](https://github.com/Rdiger-36/bambulab-ams-spoolman-filamentstatus) | The backend service this integration connects to |
| [Spoolman](https://github.com/Donkie/Spoolman) | Filament management service |
| [HACS](https://hacs.xyz/) | Required for installation in Home Assistant |

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
| `switch.ams_monitoring_<printer_name>` | Enables / disables filament monitoring for this printer |

The switch reflects the actual monitoring state from the backend and updates automatically.

## Troubleshooting

**Config flow fails to load**
Make sure the backend is reachable at the URL you entered and responds at `/api/printers`.

**Entity shows as unavailable**
The backend is not reachable. Check if the service is running and the URL/port is correct.

**Changes after editing printers do not take effect**
The integration reloads automatically after saving. If not, restart Home Assistant manually.

## Related Projects

* [bambulab-ams-spoolman-filamentstatus](https://github.com/Rdiger-36/bambulab-ams-spoolman-filamentstatus) — The backend this integration depends on
* [Spoolman](https://github.com/Donkie/Spoolman) — Filament inventory management

## Version

Current version: **1.0.0** — See the [Releases](https://github.com/Rdiger-36/ha-bambulab-ams-spoolman-filamentstatus/releases) page for the full changelog.
