"""Платформа image интеграции Ufanet Door Phone: превью последнего вызова."""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

from aiohttp import ClientError, ClientTimeout
from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import UfanetDoorPhoneData
from .api.models import HistoryData, HistoryResult
from .calls import (
    CallHistory,
    CallHistoryCoordinator,
    call_attributes,
    call_datetime,
    normalize_camera_number,
)
from .const import (
    CALL_PREVIEW_MAX_BYTES,
    CALL_PREVIEW_RETRY_SECONDS,
    CALL_PREVIEW_TIMEOUT,
    DOMAIN,
)
from .device import DoorPhoneDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Добавляем превью последнего вызова для каждого домофона."""
    data: UfanetDoorPhoneData = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for device in data.devices:
        if not normalize_camera_number(device.cctv_number):
            continue
        entities.append(LastCallImage(hass, device, data.call_coordinator))

    async_add_entities(entities)


class LastCallImage(CoordinatorEntity[CallHistoryCoordinator], ImageEntity):
    """Превью последнего вызова домофона.

    Изображение — превью звонка из истории Ufanet. Вызов относится к домофону,
    если ``camera_number`` вызова совпадает с ``cctv_number`` домофона.
    ``image_last_updated`` равен времени вызова, поэтому при новом звонке
    состояние меняется и Home Assistant сам перезапрашивает картинку. Байты
    кэшируются в памяти: превью конкретного вызова не меняется, а ссылка на
    него — временная.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "last_call"
    _attr_content_type = "image/jpeg"

    def __init__(
        self,
        hass: HomeAssistant,
        device: DoorPhoneDevice,
        coordinator: CallHistoryCoordinator,
    ) -> None:
        """Создать сущность с превью для указанного домофона."""
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)

        self._device = device
        self._cctv_number = normalize_camera_number(device.cctv_number)

        self._attr_unique_id = f"intercom_{device.intercom_id}_last_call_preview"
        self._attr_device_info = device.device_info

        self._image_uuid: Optional[str] = None
        self._image: Optional[bytes] = None
        self._failed_uuid: Optional[str] = None
        self._failed_at: Optional[float] = None
        self._last_updated_uuid: Optional[str] = None

        self._refresh_image_timestamp()

    @property
    def _history(self) -> Optional[CallHistory]:
        """Вызовы этого домофона из последнего опроса истории."""
        return (self.coordinator.data or {}).get(self._cctv_number)

    def _last_call(self) -> Optional[HistoryResult]:
        """Последний вызов из истории."""
        history = self._history
        return history.last_call if history is not None else None

    def _last_links(self) -> Optional[HistoryData]:
        """Ссылки на запись и превью последнего вызова домофона."""
        history = self._history
        return history.last_links if history is not None else None

    def _refresh_image_timestamp(self) -> None:
        """Обновить отметку изображения, если у домофона новый вызов."""
        call = self._last_call()
        if call is None:
            self._last_updated_uuid = None
            self._attr_image_last_updated = None
            self._image_uuid = None
            self._image = None
            return

        # Дальше время вызова не меняется, поэтому не трогаем состояние на
        # каждом опросе истории: Home Assistant перезапросит картинку только
        # при смене image_last_updated.
        if call.uuid == self._last_updated_uuid:
            return

        self._last_updated_uuid = call.uuid
        self._attr_image_last_updated = call_datetime(call)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Отметить новое изображение, чтобы Home Assistant его перезапросил."""
        self._refresh_image_timestamp()
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Превью доступно, пока есть история и ссылка на превью."""
        return super().available and self._last_links() is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Данные вызова, к которому относится изображение."""
        call = self._last_call()
        if call is None:
            return {}
        return call_attributes(call, self._last_links())

    async def async_image(self) -> Optional[bytes]:
        """Вернуть JPEG с превью последнего вызова.

        Home Assistant вызывает метод при каждом обращении к картинке, поэтому
        байты кэшируются по ``uuid`` вызова, а после неудачной попытки делается
        пауза ``CALL_PREVIEW_RETRY_SECONDS``, чтобы не повторять запросы в цикле.
        """
        call = self._last_call()
        links = self._last_links()
        if call is None or links is None or not links.preview:
            return None

        if self._image_uuid == call.uuid and self._image is not None:
            return self._image

        # Новый вызов: пробуем скачать сразу, не дожидаясь паузы после
        # неудачной попытки для предыдущего вызова.
        if self._failed_uuid != call.uuid:
            self._failed_uuid = None
            self._failed_at = None

        now = time.monotonic()
        if (
            self._failed_uuid == call.uuid
            and self._failed_at is not None
            and now - self._failed_at < CALL_PREVIEW_RETRY_SECONDS
        ):
            return None

        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                links.preview, timeout=ClientTimeout(total=CALL_PREVIEW_TIMEOUT)
            ) as response:
                if response.status != 200:
                    raise ClientError(f"HTTP {response.status}")
                content_length = response.content_length
                if (
                    content_length is not None
                    and content_length > CALL_PREVIEW_MAX_BYTES
                ):
                    raise ClientError(f"ответ слишком большой: {content_length} байт")
                content = await response.read()
        except (ClientError, TimeoutError, ValueError) as err:
            self._failed_uuid = call.uuid
            self._failed_at = now
            _LOGGER.debug("Не удалось скачать превью вызова %s: %s", call.uuid, err)
            return None

        if not content or len(content) > CALL_PREVIEW_MAX_BYTES:
            self._failed_uuid = call.uuid
            self._failed_at = now
            _LOGGER.debug("Превью вызова %s пустое или слишком большое", call.uuid)
            return None

        self._image_uuid = call.uuid
        self._image = content
        self._failed_uuid = None
        self._failed_at = None
        return content
