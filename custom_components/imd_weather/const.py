"""Constants for the IMD Weather integration."""
from datetime import timedelta

DOMAIN = "imd_weather"
BASE_URL = "https://api.imd.gov.in/api/v1"

# Config entry keys
CONF_MODE = "location_mode"
MODE_HIERARCHY = "hierarchy"
MODE_COORDS = "coordinates"
CONF_STATE = "state"
CONF_DISTRICT = "district"
CONF_DISTRICT_ID = "district_id"
CONF_SUBDIVISION = "subdivision"
CONF_CITY_ID = "city_id"
CONF_CITY_NAME = "city_name"

# Update intervals (be gentle with a government API)
INTERVAL_FORECAST = timedelta(hours=2)
INTERVAL_CURRENT = timedelta(minutes=30)
INTERVAL_NOWCAST = timedelta(minutes=15)
INTERVAL_WARNING = timedelta(minutes=30)
INTERVAL_RAINFALL = timedelta(hours=3)
INTERVAL_MARINE = timedelta(hours=3)
INTERVAL_CYCLONE = timedelta(minutes=30)
INTERVAL_ASTRO = timedelta(hours=6)

# Coordinator keys
K_FORECAST = "forecast"
K_CURRENT = "current"
K_NOWCAST = "nowcast"
K_WARNING = "warning"
K_SUBDIV_WARNING = "subdiv_warning"
K_RAINFALL = "rainfall"
K_MARINE = "marine"
K_CYCLONE = "cyclone"
K_ASTRO = "astro"

# From the IMD API reference: district warning codes
WARNING_CODES = {
    1: "No Warning", 2: "Heavy Rain", 3: "Heavy Snow",
    4: "Thunderstorm & Lightning, Squall etc", 5: "Hailstorm",
    6: "Dust Storm", 7: "Dust Raising Winds", 8: "Strong Surface Winds",
    9: "Heat Wave", 10: "Hot Day", 11: "Warm Night", 12: "Cold Wave",
    13: "Cold Day", 14: "Ground Frost", 15: "Fog", 16: "Very Heavy Rain",
    17: "Extremely Heavy Rain",
}
# District warning colour codes (note: 1 = RED in the warning API,
# the opposite of the nowcast API where 1 = green)
WARNING_COLORS = {1: "red", 2: "orange", 3: "yellow", 4: "green"}
NOWCAST_COLORS = {1: "green", 2: "yellow", 3: "orange", 4: "red"}
