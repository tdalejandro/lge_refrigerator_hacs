"""Constants for the LGE Refrigerator integration."""

from __future__ import annotations

DOMAIN = "lge_refrigerator"
PLATFORMS = ["binary_sensor", "climate", "sensor", "switch"]

CONF_COUNTRY = "country"
CONF_LANGUAGE = "language"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_OAUTH_URL = "oauth_url"
CONF_CLIENT_ID = "client_id"
CONF_DEVICE_ID = "device_id"
CONF_HOMEKIT_NAME = "homekit_name"
CONF_HOMEKIT_PORT = "homekit_port"
CONF_HOMEKIT_PIN = "homekit_pin"

DEFAULT_COUNTRY = "MX"
DEFAULT_LANGUAGE = "es-MX"
DEFAULT_HOMEKIT_PORT = 21100
DEFAULT_HOMEKIT_PIN = "518-08-582"
DEFAULT_SCAN_INTERVAL = 300

DATA_COORDINATOR = "coordinator"
DATA_HOMEKIT = "homekit"

FEATURE_ECO_FRIENDLY = "eco_friendly"
FEATURE_EXPRESS_FREEZER = "express_mode"
FEATURE_EXPRESS_FRIDGE = "express_fridge"
FEATURE_ICE_PLUS = "ice_plus"
FEATURE_FRESH_AIR_FILTER = "fresh_air_filter_remain_perc"
FEATURE_WATER_FILTER = "water_filter_remain_perc"

STORAGE_FILE_PREFIX = ".lge_refrigerator_homekit_"
