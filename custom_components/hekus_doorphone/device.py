"""Представление устройств интеграции Ufanet Door Phone."""
from __future__ import annotations

from typing import List

from .api.models import Intercom


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
