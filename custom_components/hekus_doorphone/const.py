"""Константы интеграции Ufanet Door Phone."""

DOMAIN = "hekus_doorphone"
NAME = "Hekus DoorPhone"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# Интервал опроса списка домофонов, в секундах
DEFAULT_SCAN_INTERVAL = 300

# Время, в течение которого дверь нельзя открыть повторно, в секундах
UNLOCK_COOLDOWN = 8
