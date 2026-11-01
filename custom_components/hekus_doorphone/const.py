"""Константы интеграции Ufanet Door Phone."""

DOMAIN = "hekus_doorphone"
NAME = "Hekus DoorPhone"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# Интервал опроса списка домофонов, в секундах
DEFAULT_SCAN_INTERVAL = 300

# Время, в течение которого дверь нельзя открыть повторно, в секундах
UNLOCK_COOLDOWN = 8

# Интервал опроса истории вызовов, в секундах. Меньше интервала опроса
# домофонов, чтобы звонок попадал в Home Assistant с небольшой задержкой.
CALL_HISTORY_SCAN_INTERVAL = 60

# Сколько последних вызовов запрашивать из истории
CALL_HISTORY_PAGE_SIZE = 10

# Сколько раз пытаться получить ссылки на запись звонка: запись и превью
# появляются не сразу после вызова
CALL_HISTORY_LINK_ATTEMPTS = 3

