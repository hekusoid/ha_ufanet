"""История вызовов домофона: опрос API и подготовка данных для сущностей."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
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
    CALL_HISTORY_LINK_ATTEMPTS,
    CALL_HISTORY_PAGE_SIZE,
    CALL_HISTORY_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Ключи атрибутов сущностей истории вызовов
ATTR_CALLS = "calls"
ATTR_CALLS_COUNT = "calls_count"
ATTR_RECORDING_URL = "recording_url"
ATTR_PREVIEW_URL = "preview_url"


@dataclass
class CallHistory:
    """Последние вызовы домофона и ссылки на записи этих вызовов."""

    count: int
    calls: List[HistoryResult]
    links: Dict[str, HistoryData] = field(default_factory=dict)

    @property
    def last_call(self) -> Optional[HistoryResult]:
        """Самый свежий вызов: API отдаёт историю от новых к старым."""
        return self.calls[0] if self.calls else None


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


class CallHistoryCoordinator(DataUpdateCoordinator[CallHistory]):
    """Опрос истории вызовов с кэшем ссылок на записи и превью.

    Ссылки на запись конкретного вызова запрашиваются отдельным методом API,
    поэтому они получаются один раз на новый вызов и переиспользуются при
    следующих опросах.
    """

    def __init__(
        self, hass: HomeAssistant, api: UfanetIntercomAPI, username: str
    ) -> None:
        """Создать координатор истории вызовов для указанного договора."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_call_history",
            update_interval=timedelta(seconds=CALL_HISTORY_SCAN_INTERVAL),
        )
        self._api = api
        self._username = username
        self._links: Dict[str, HistoryData] = {}
        self._link_failures: Dict[str, int] = {}

    async def _async_update_data(self) -> CallHistory:
        """Запросить первую страницу истории вызовов и ссылки на записи."""
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

        for call in calls:
            await self._async_ensure_links(call)

        return CallHistory(count=history.count, calls=calls, links=dict(self._links))

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
