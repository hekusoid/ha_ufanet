"""Представление устройств интеграции Ufanet Door Phone."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List

from .api.models import Intercom

# Поля Intercom, которые интеграция уже использует в логике (название устройства,
# DeviceInfo.model, доступность сущности) или которые уже отдаются отдельными
# атрибутами замка (intercom_id, address, role). Повторно в атрибуты не попадают.
USED_INTERCOM_FIELDS = frozenset(
    {
        "id",
        "custom_name",
        "string_view",
        "role",
        "model",
        "is_blocked",
        "disable_button",
    }
)


def dump_model(model: Any) -> Dict[str, Any]:
    """Сериализовать pydantic-модель (v1 и v2)."""
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _json_safe(value: Any) -> Any:
    """Привести значение к виду, который Home Assistant сможет сериализовать."""
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def intercom_attributes(intercom: Intercom) -> Dict[str, Any]:
    """Атрибуты сущности из параметров домофона, которые ещё не используются."""
    data = dump_model(intercom)
    return {
        key: _json_safe(value)
        for key, value in data.items()
        if key not in USED_INTERCOM_FIELDS
    }


class DoorPhoneDevice:
    """Домофон, доступный в аккаунте Ufanet."""

    def __init__(self, intercom: Intercom) -> None:
        """Создать описание устройства по домофону из API."""
        self.intercom = intercom

    @property
    def intercom_id(self) -> int:
        """Идентификатор домофона в API Ufanet."""
        return self.intercom.id

    @property
    def device_id(self) -> str:
        """Идентификатор устройства в реестре устройств Home Assistant."""
        return f"ufanet_doorphone_{self.intercom.id}"

    @property
    def name(self) -> str:
        """Понятное человеку название домофона."""
        if self.intercom.custom_name:
            return self.intercom.custom_name
        return f"{self.intercom.string_view} ({self.intercom.role.name})"

    @property
    def model(self) -> str:
        """Модель для реестра устройств."""
        return f"Intercom (model {self.intercom.model})"


def create_devices(intercoms: List[Intercom]) -> List[DoorPhoneDevice]:
    """Обернуть домофоны из API в устройства интеграции."""
    return [DoorPhoneDevice(intercom) for intercom in intercoms]
