"""Constants for Ufanet Door Phone integration."""

DOMAIN = "ufanet_doorphone"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_DEVICE_ID = "device_id"

DEFAULT_NAME = "Ufanet Door Phone"
DEFAULT_SCAN_INTERVAL = 30

ATTR_CALL_STATUS = "call_status"
ATTR_DOOR_STATUS = "door_status"
ATTR_LAST_CALL = "last_call_time"

SERVICE_OPEN_DOOR = "open_door"
SERVICE_ANSWER_CALL = "answer_call"
SERVICE_REJECT_CALL = "reject_call"

UFANET_API_BASE = "https://api.ufanet.ru"
UFANET_API_AUTH = f"{UFANET_API_BASE}/auth"
UFANET_API_DEVICES = f"{UFANET_API_BASE}/devices"
UFANET_API_DOOR_ACTION = f"{UFANET_API_BASE}/door/open"