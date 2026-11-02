"""Диагностика интеграции Ufanet Door Phone."""
from __future__ import annotations

from typing import Any, Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import UfanetDoorPhoneData
from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN

TO_REDACT = {CONF_PASSWORD}


def _dump(model: Any) -> Any:
    """Сериализовать pydantic-модель (v1 и v2)."""
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> Dict[str, Any]:
    """Вернуть диагностику по config entry без секретов."""
    data: UfanetDoorPhoneData = hass.data[DOMAIN][entry.entry_id]

    return {
        "entry": {
            "title": entry.title,
            "data": {
                CONF_USERNAME: entry.data.get(CONF_USERNAME),
                CONF_PASSWORD: "**REDACTED**",
            },
            "version": entry.version,
        },
        "coordinator": {
            "last_update_success": data.coordinator.last_update_success,
            "update_interval_seconds": (
                data.coordinator.update_interval.total_seconds()
                if data.coordinator.update_interval
                else None
            ),
        },
        "intercoms": [
            _dump(intercom) for intercom in (data.coordinator.data or {}).values()
        ],
        "devices": [
            {
                "intercom_id": device.intercom_id,
                "name": device.name,
                "cctv_number": device.cctv_number,
            }
            for device in data.devices
        ],
        "call_history": {
            "last_update_success": data.call_coordinator.last_update_success,
            "update_interval_seconds": (
                data.call_coordinator.update_interval.total_seconds()
                if data.call_coordinator.update_interval
                else None
            ),
            "by_intercom": {
                cctv_number: {
                    "calls_count": history.count,
                    "last_call_uuid": (
                        history.last_call.uuid
                        if history.last_call is not None
                        else None
                    ),
                    "calls": [_dump(call) for call in history.calls],
                }
                for cctv_number, history in (
                    data.call_coordinator.data or {}
                ).items()
            },
        },
    }
