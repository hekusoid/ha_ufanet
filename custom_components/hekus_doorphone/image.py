"""Платформа image интеграции Ufanet Door Phone: превью последнего вызова."""
from __future__ import annotations

import logging
import shutil
import time
from typing import Any, Optional

from haffmpeg.tools import IMAGE_JPEG, ImageFrame
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
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
    CALL_PREVIEW_SEEK_SECONDS,
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

    # Ufanet отдаёт превью вызова ссылкой на видео, поэтому кадр извлекает
    # ffmpeg. Он есть во всех официальных установках Home Assistant; если
    # бинаря нет, сущности создаются, но остаются недоступными, а остальные
    # сущности интеграции работают как обычно.
    ffmpeg_binary = await _async_get_ffmpeg_binary(hass)

    entities = []
    for device in data.devices:
        if not normalize_camera_number(device.cctv_number):
            continue
        entities.append(
            LastCallImage(hass, device, data.call_coordinator, ffmpeg_binary)
        )

    async_add_entities(entities)


async def _async_get_ffmpeg_binary(hass: HomeAssistant) -> Optional[str]:
    """Вернуть путь к ffmpeg, если он доступен, иначе ``None``.

    Компонент ``ffmpeg`` подключён как зависимость интеграции, поэтому его
    менеджер уже создан. Отсутствие бинаря не ошибка: превью просто не будет.
    """
    manager = hass.data.get(DATA_FFMPEG)
    if manager is None:
        _LOGGER.warning(
            "Компонент ffmpeg не инициализирован: превью вызова недоступно"
        )
        return None

    binary = manager.binary
    if await hass.async_add_executor_job(shutil.which, binary) is None:
        _LOGGER.warning(
            "ffmpeg не найден (%s): превью последнего вызова будет недоступно", binary
        )
        return None

    return binary


class LastCallImage(CoordinatorEntity[CallHistoryCoordinator], ImageEntity):
    """Превью последнего вызова домофона.

    Ufanet отдаёт превью звонка ссылкой на видео, поэтому кадр извлекает
    ffmpeg: он читает видео по ссылке и возвращает один кадр JPEG. Вызов
    относится к домофону, если ``camera_number`` вызова совпадает с
    ``cctv_number`` домофона. ``image_last_updated`` равен времени вызова,
    поэтому при новом звонке состояние меняется и Home Assistant сам
    перезапрашивает картинку. Кадр кэшируется в памяти: превью конкретного
    вызова не меняется, а ссылка на него — временная.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "last_call"
    _attr_content_type = "image/jpeg"

    def __init__(
        self,
        hass: HomeAssistant,
        device: DoorPhoneDevice,
        coordinator: CallHistoryCoordinator,
        ffmpeg_binary: Optional[str],
    ) -> None:
        """Создать сущность с превью для указанного домофона."""
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)

        self._device = device
        self._cctv_number = normalize_camera_number(device.cctv_number)
        self._ffmpeg_binary = ffmpeg_binary

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
        """Превью доступно, пока есть история, ссылка и ffmpeg."""
        return (
            super().available
            and self._ffmpeg_binary is not None
            and self._last_links() is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Данные вызова, к которому относится изображение."""
        call = self._last_call()
        if call is None:
            return {}
        return call_attributes(call, self._last_links())

    async def async_image(self) -> Optional[bytes]:
        """Вернуть JPEG с кадром из видео превью последнего вызова.

        Ufanet отдаёт превью вызова ссылкой на видео, поэтому кадр извлекает
        ffmpeg: он читает видео по ссылке и возвращает один кадр. Home Assistant
        вызывает метод при каждом обращении к картинке, поэтому байты
        кэшируются по ``uuid`` вызова, а после неудачной попытки делается
        пауза ``CALL_PREVIEW_RETRY_SECONDS``, чтобы не повторять запросы в цикле.
        """
        call = self._last_call()
        links = self._last_links()
        source = (links.preview or links.url) if links is not None else None
        binary = self._ffmpeg_binary
        if call is None or not source or binary is None:
            return None

        if self._image_uuid == call.uuid and self._image is not None:
            return self._image

        # Новый вызов: пробуем получить кадр сразу, не дожидаясь паузы после
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

        content = await self._async_grab_frame(binary, source)
        
        if not content or len(content) > CALL_PREVIEW_MAX_BYTES:
            self._failed_uuid = call.uuid
            self._failed_at = now
            content_length = len(content) if content else 0
            _LOGGER.debug(
                f"Кадр превью вызова {call.uuid} не получен или слишком большой ({content_length})", 
            )
            return None

        self._image_uuid = call.uuid
        self._image = content
        self._failed_uuid = None
        self._failed_at = None
        return content

    async def _async_grab_frame(self, binary: str, source: str) -> Optional[bytes]:
        """Извлечь один кадр JPEG из видео по ссылке через ffmpeg.

        Кадр берётся не с самого начала записи: первые кадры часто тёмные.
        Если ролик короче позиции перемотки, ffmpeg не вернёт кадр — тогда
        повторяем без перемотки.
        """
        seek = (
            f"-ss {CALL_PREVIEW_SEEK_SECONDS}" if CALL_PREVIEW_SEEK_SECONDS else None
        )
        try:
            content = await self._async_ffmpeg_frame(binary, source, seek)
            if content is None and seek is not None:
                content = await self._async_ffmpeg_frame(binary, source, None)
        except (OSError, ValueError) as err:
            _LOGGER.debug("Не удалось извлечь кадр из %s: %s", source, err)
            return None

        return content

    async def _async_ffmpeg_frame(
        self, binary: str, source: str, extra_cmd: Optional[str]
    ) -> Optional[bytes]:
        """Запустить ffmpeg и вернуть JPEG с одним кадром видео."""
        _LOGGER.debug(
                        f"Запрашиваем кадр из файла по ссылке [{source}]", 
                    )
        return await ImageFrame(binary).get_image(
            source,
            output_format=IMAGE_JPEG,
            extra_cmd=extra_cmd,
            timeout=CALL_PREVIEW_TIMEOUT,
        )
