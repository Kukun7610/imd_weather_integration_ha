# IMD Weather for Home Assistant (HACS)

Unofficial integration for the India Meteorological Department public API
(https://api.imd.gov.in/public/api_reference.html).

## Install (custom repository)
1. HACS > Integrations > ⋮ > Custom repositories > add this repo, category **Integration**.
2. Download, restart Home Assistant.
3. Settings > Devices & services > Add integration > **IMD Weather**.

## Setup: two location modes
- **India > State > District > Subdivision > City**
- **Latitude / Longitude** (nearest IMD city station is picked automatically, then State > District > Subdivision for warnings/nowcast)

Optional `custom_components/imd_weather/data/hierarchy.json` filters the subdivision and city
dropdowns (state -> subdivisions, district -> city station codes). Without it the lists are unfiltered.

## Status (v0.1.0 skeleton)
| Feature | Status |
|---|---|
| Weather forecast (7 day) + current | Done: `weather` entity |
| Current weather & nowcast | Done: `current_wx` (weather entity), `districtnowcast` sensor |
| Warnings | Done: district + subdivision sensors |
| Rainfall | Done: district daily sensor (weekly/monthly as attributes) |
| Marine | Done: sea + coastal bulletin sensor (port/fishermen warnings TODO) |
| Cyclone | Done: track sensor (wind radii + cone GeoJSON TODO) |
| Astronomical | Done: sunrise/sunset/moonrise/moonset |
| Radar & lightning | TODO: endpoint details not yet read |
| Agromet advisory | TODO: endpoint details not yet read |
| Seasonal rainfall forecast | TODO: no API, web page only (scrape, best effort) |
| Custom dashboard card | TODO: separate JS repo (HACS category "Dashboard") |

## Must verify against live responses (could not be fetched while developing)
- `cityforecast_mapping` / `cityforecastloc` field names (`Station_Code`, `Latitude`, `Longitude` assumed from the docs).
- Whether `current_wx?id=` accepts the same ID as the city forecast station code. If not, add a nearest-AWS lookup via `aws_data` (has lat/lon).
- Whether the API needs registration or an IP whitelist.
- `state_district_rainfall_forecast` returns every district (used to build State > District).
