"""История вызовов домофона: опрос API и подготовка данных для сущностей."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Collection, Dict, Iterable, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api.exceptions import (
    ClientConnectorUfanetIntercomAPIError,
    TimeoutUfanetIntercomAPIError,
    UnauthorizedUfanetIntercomAPIError,
    UfanetIntercomAPIError,
)
from .api.models import HistoryData, HistoryResult
from .api.ufanet_api import UfanetIntercomAPI
from .const import (
    CALL_HISTORY_LINKED_CALLS,
    CALL_HISTORY_LINK_ATTEMPTS,
    CALL_HISTORY_PAGE_SIZE,
    CALL_HISTORY_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Ключи атрибутов сущностей истории вызовов
ATTR_CALLS = "calls"
ATTR_CALLS_COUNT = "calls_count"
ATTR_CALLS_TOTAL = "calls_total"
ATTR_CCTV_NUMBER = "cctv_number"
ATTR_RECORDING_URL = "recording_url"
ATTR_PREVIEW_URL = "preview_url"


def normalize_camera_number(value: Optional[str]) -> str:
    """Привести номер камеры к виду, пригодному для сравнения."""
    return (value or "").strip().casefold()


def call_datetime(call: HistoryResult) -> datetime:
    """Время вызова в часовом поясе Home Assistant.

    ``called_at`` может прийти без смещения — тогда используется пояс из поля
    ``timezone`` самого вызова, а если он неизвестен, то пояс Home Assistant.
    """
    called_at = call.called_at

    if called_at.tzinfo is None:
        try:
            called_at = called_at.replace(tzinfo=ZoneInfo(call.timezone))
        except (ZoneInfoNotFoundError, ValueError):
            called_at = called_at.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)

    return dt_util.as_local(called_at)


def calls_by_time(calls: Iterable[HistoryResult]) -> List[HistoryResult]:
    """Вызовы от новых к старым по полю ``called_at``.

    Порядок ответа API не гарантируется, поэтому время вызова сравнивается
    явно. Сортируется только копия: исходный список остаётся как пришёл от
    API. Ключ — нормализованное время, поэтому сравнение корректно и при
    разных часовых поясах; ``uuid`` служит тай-брейком при равном времени.
    """
    return sorted(
        calls,
        key=lambda call: (call_datetime(call), call.uuid),
        reverse=True,
    )


@dataclass
class CallHistory:
    """Вызовы одного домофона и ссылки на записи этих вызовов.

    ``calls`` хранится в том порядке, в котором вызовы пришли от API: так его
    видно в атрибутах датчика и в диагностике. Последний вызов и самые свежие
    вызовы определяются по времени ``called_at``.
    """

    calls: List[HistoryResult] = field(default_factory=list)
    links: Dict[str, HistoryData] = field(default_factory=dict)
    total_count: int = 0

    @property
    def count(self) -> int:
        """Сколько вызовов домофона попало в загруженную страницу истории."""
        return len(self.calls)

    @property
    def last_call(self) -> Optional[HistoryResult]:
        """Самый свежий вызов домофона по полю ``called_at``."""
        if not self.calls:
            return None
        return max(self.calls, key=call_datetime)

    def recent_calls(self, limit: int) -> List[HistoryResult]:
        """Самые свежие вызовы домофона по полю ``called_at``.

        Используются для запроса ссылок на запись и превью: у старых вызовов
        эти ссылки уже не нужны, а порядок ответа API на них не влияет.
        """
        if limit <= 0:
            return []
        return calls_by_time(self.calls)[:limit]

    @property
    def last_links(self) -> Optional[HistoryData]:
        """Ссылки на запись и превью последнего вызова домофона."""
        call = self.last_call
        return self.links.get(call.uuid) if call is not None else None


def call_attributes(
    call: HistoryResult, links: Optional[HistoryData] = None
) -> Dict[str, Any]:
    """Описание вызова для атрибутов датчика последнего вызова."""
    attributes: Dict[str, Any] = {
        "uuid": call.uuid,
        "called_at": call_datetime(call).isoformat(),
        "address": call.address,
        "porch": call.porch,
        "flat": call.flat,
        "house_id": call.house_id,
        "camera_number": call.camera_number,
        "skud_mac": call.skud_mac,
        "timezone": call.timezone,
    }

    if links is not None:
        attributes[ATTR_RECORDING_URL] = links.url
        attributes[ATTR_PREVIEW_URL] = links.preview

    return attributes


class CallHistoryCoordinator(DataUpdateCoordinator[Dict[str, CallHistory]]):
    """Опрос истории вызовов с распределением вызовов по домофонам.

    API отдаёт историю всего договора и не умеет фильтровать её по камере,
    поэтому запрашивается одна страница вызовов, а затем она делится по номеру
    камеры: ``camera_number`` вызова совпадает с ``cctv_number`` домофона.
    Порядок вызовов в ответе API не гарантируется: последний вызов и самые
    свежие вызовы определяются по времени ``called_at``.
    Ссылки на запись и превью запрашиваются отдельным методом API, получаются
    один раз на вызов и переиспользуются при следующих опросах.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        api: UfanetIntercomAPI,
        username: str,
        cctv_numbers: Collection[str],
    ) -> None:
        """Создать координатор истории вызовов для домофонов договора."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_call_history",
            update_interval=timedelta(seconds=CALL_HISTORY_SCAN_INTERVAL),
        )
        self._api = api
        self._username = username
        # Номера камер домофонов договора в виде, пригодном для сравнения.
        # Список, а не множество: порядок нужен для стабильного вывода данных.
        self._cctv_numbers: List[str] = list(
            dict.fromkeys(
                number
                for number in map(normalize_camera_number, cctv_numbers)
                if number
            )
        )
        self._links: Dict[str, HistoryData] = {}
        self._link_failures: Dict[str, int] = {}
        self._unmatched_logged: set[str] = set()

    async def _async_update_data(self) -> Dict[str, CallHistory]:
        """Запросить историю договора и распределить вызовы по домофонам."""
        try:
            history = await self._api.get_call_history(
                page=1, page_size=CALL_HISTORY_PAGE_SIZE
            )
        except UnauthorizedUfanetIntercomAPIError as err:
            raise ConfigEntryAuthFailed(
                f"Токен Ufanet для договора {self._username} больше не действителен"
            ) from err
        except (ClientConnectorUfanetIntercomAPIError, TimeoutUfanetIntercomAPIError) as err:
            raise UpdateFailed(f"Ошибка обмена с Ufanet API: {err}") from err
        except UfanetIntercomAPIError as err:
            raise UpdateFailed(f"Не удалось получить историю вызовов: {err}") from err

        calls = list(history.results)
        self._prune(calls)

        calls_by_camera: Dict[str, List[HistoryResult]] = {}
        unmatched: List[HistoryResult] = []
        for call in calls:
            camera_number = normalize_camera_number(call.camera_number)
            if camera_number not in self._cctv_numbers:
                unmatched.append(call)
                continue
            calls_by_camera.setdefault(camera_number, []).append(call)

        self._log_unmatched(unmatched)

        data: Dict[str, CallHistory] = {}
        for cctv_number in self._cctv_numbers:
            history_calls = CallHistory(
                calls=calls_by_camera.get(cctv_number, []),
                total_count=history.count,
            )

            # Ссылки нужны только свежим вызовам домофона, а порядок ответа API
            # не гарантируется: время вызова сравнивается явно по called_at.
            for call in history_calls.recent_calls(CALL_HISTORY_LINKED_CALLS):
                await self._async_ensure_links(call)

            history_calls.links = {
                call.uuid: self._links[call.uuid]
                for call in history_calls.calls
                if call.uuid in self._links
            }
            data[cctv_number] = history_calls

        return data

    def _log_unmatched(self, calls: List[HistoryResult]) -> None:
        """Записать в лог вызовы, не относящиеся ни к одному домофону договора."""
        for call in calls:
            if call.uuid in self._unmatched_logged:
                continue
            self._unmatched_logged.add(call.uuid)
            _LOGGER.debug(
                "Вызов %s с камеры %s не относится ни к одному домофону договора",
                call.uuid,
                call.camera_number,
            )

    def _prune(self, calls: List[HistoryResult]) -> None:
        """Выбросить из кэша ссылки на вызовы, которых уже нет в истории."""
        uuids = {call.uuid for call in calls}
        self._links = {
            uuid: links for uuid, links in self._links.items() if uuid in uuids
        }
        self._link_failures = {
            uuid: attempts
            for uuid, attempts in self._link_failures.items()
            if uuid in uuids
        }
        self._unmatched_logged &= uuids

    async def _async_ensure_links(self, call: HistoryResult) -> None:
        """Получить ссылки на запись и превью, если их ещё нет в кэше.

        Запись звонка появляется не сразу, поэтому неудачные попытки
        повторяются при следующих опросах, но не больше
        ``CALL_HISTORY_LINK_ATTEMPTS`` раз на вызов.
        """
        if call.uuid in self._links:
            return

        if self._link_failures.get(call.uuid, 0) >= CALL_HISTORY_LINK_ATTEMPTS:
            return

        try:
            self._links[call.uuid] = await self._api.get_call_history_links(call.uuid)
        except UnauthorizedUfanetIntercomAPIError as err:
            raise ConfigEntryAuthFailed(
                f"Токен Ufanet для договора {self._username} больше не действителен"
            ) from err
        except UfanetIntercomAPIError as err:
            attempts = self._link_failures.get(call.uuid, 0) + 1
            self._link_failures[call.uuid] = attempts
            _LOGGER.debug(
                "Ссылки на запись вызова %s не получены (попытка %s из %s): %s",
                call.uuid,
                attempts,
                CALL_HISTORY_LINK_ATTEMPTS,
                err,
            )
