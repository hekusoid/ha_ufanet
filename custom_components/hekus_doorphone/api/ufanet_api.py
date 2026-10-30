"""Асинхронный клиент облачного API домофонов Ufanet (dom.ufanet.ru)."""
from __future__ import annotations

import asyncio
import logging
from json.decoder import JSONDecodeError
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin
from uuid import UUID, uuid4

import aiohttp
from aiohttp import ClientSession, ClientTimeout
from aiohttp.client_exceptions import ClientConnectorError, ContentTypeError

from .exceptions import (
    BadRequestUfanetIntercomAPIError,
    ClientConnectorUfanetIntercomAPIError,
    TimeoutUfanetIntercomAPIError,
    UnauthorizedUfanetIntercomAPIError,
    UfanetIntercomAPIError,
    UnknownUfanetIntercomAPIError,
)
from .models import History, HistoryData, Intercom, Token

BASE_URL = "https://dom.ufanet.ru/"

AUTH_BY_CONTRACT_PATH = "api/v1/auth/auth_by_contract/"
TOKEN_VERIFY_PATH = "api-token-verify/"
INTERCOMS_PATH = "api/v0/skud/shared/"
CALL_HISTORY_PATH = "api/v1/skuds/call-history/"
CALL_HISTORY_LINKS_PATH = "api/v1/cctv/history/"


class UfanetIntercomAPI:
    """Небольшой асинхронный клиент HTTP API домофонов Ufanet.

    Клиент держит JWT в памяти, при истечении токена заново авторизуется по
    номеру договора и паролю и повторяет неудавшийся запрос ровно один раз.
    """

    def __init__(
        self,
        contract: str,
        password: str,
        session: Optional[ClientSession] = None,
        timeout: int = 30,
        logger_name: str = "UfanetIntercom",
    ) -> None:
        """Создать клиент: учётные данные и, при необходимости, готовая сессия."""
        self._LOGGER = logging.getLogger(logger_name)
        self._contract = contract
        self._password = password
        self._token: Union[str, None] = None
        self._base_url: str = BASE_URL
        self._timeout = ClientTimeout(total=timeout)

        # Здесь намеренно ничего не создаётся: сессию aiohttp нужно создавать
        # внутри работающего цикла событий. Home Assistant передаёт свою сессию,
        # собственная ClientSession создаётся лениво и только если её не передали.
        self._session: Optional[ClientSession] = session
        self._owns_session = session is None

    @property
    def session(self) -> ClientSession:
        """Вернуть сессию aiohttp, используемую для запросов."""
        if self._session is None or self._session.closed:
            self._session = ClientSession(timeout=self._timeout)
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Закрыть сессию, если её создал сам клиент."""
        if self._owns_session and self._session is not None:
            if not self._session.closed:
                await self._session.close()
            self._session = None

    async def _send_request(self, url: str, method: str = "GET", params: Dict[str, Any] = None,
                            json: Dict[str, Any] = None,
                            auth_retry: bool = True) -> Union[Dict[str, Any], List[Dict[str, Any]], None]:
        """Выполнить авторизованный запрос, повторно авторизуясь не более одного раза."""
        retried = False

        while True:
            headers = {"Authorization": f"JWT {self._token}"}
            request_id = uuid4().hex
            self._LOGGER.debug("Request=%s method=%s url=%s params=%s json=%s",
                               request_id, method, url, params, json)
            try:
                async with self.session.request(method, url, params=params, json=json,
                                                headers=headers) as response:
                    if response.status == 401:
                        raise UnauthorizedUfanetIntercomAPIError

                    json_response = await self._decode_json(response)

                    if 200 <= response.status < 300:
                        self._LOGGER.debug("Response=%s json_response=%s", request_id, json_response)
                        return json_response

                    self._LOGGER.error(
                        "Response=%s неуспешный запрос json_response=%s status=%s reason=%s",
                        request_id, json_response, response.status, response.reason,
                    )
                    if response.status == 400:
                        raise BadRequestUfanetIntercomAPIError(json_response)
                    raise UnknownUfanetIntercomAPIError(json_response)

            except asyncio.TimeoutError as err:
                self._LOGGER.error("Response=%s TimeoutUfanetIntercomAPIError", request_id)
                raise TimeoutUfanetIntercomAPIError(
                    "Истекло время ожидания ответа API Ufanet"
                ) from err

            except ClientConnectorError as err:
                self._LOGGER.error("Response=%s ClientConnectorUfanetIntercomAPIError", request_id)
                raise ClientConnectorUfanetIntercomAPIError(
                    "Не удалось соединиться с API Ufanet"
                ) from err

            except UnauthorizedUfanetIntercomAPIError as err:
                if not auth_retry or retried:
                    self._LOGGER.error("Response=%s запрос не авторизован, прекращаем попытки",
                                       request_id)
                    raise

                self._LOGGER.debug("Response=%s запрос не авторизован, обновляем JWT", request_id)
                retried = True
                await self._set_token()
                continue

    @staticmethod
    async def _decode_json(response: aiohttp.ClientResponse) -> Any:
        """Разобрать тело ответа, если возможно, иначе вернуть ``None``."""
        if not 200 <= response.status < 500:
            return None
        if response.content_length == 0:
            return None

        try:
            return await response.json(content_type=None)
        except (JSONDecodeError, ContentTypeError, ValueError):
            return None

    async def _prepare_token(self) -> None:
        """Убедиться, что есть действующий токен."""
        if self._token is None:
            await self._set_token()
            return

        try:
            await self.token_verify()
        except UnauthorizedUfanetIntercomAPIError:
            await self._set_token()

    async def async_authenticate(self) -> None:
        """Авторизоваться по номеру договора и паролю."""
        await self._set_token()

    async def _set_token(self) -> None:
        """Запросить новую пару токенов и оставить ту, которую принял API."""
        url = urljoin(self._base_url, AUTH_BY_CONTRACT_PATH)
        payload = {"contract": self._contract, "password": self._password}
        response = await self._send_request(url=url, method="POST", json=payload, auth_retry=False)
        token = Token(**response["token"])

        # Ufanet возвращает пару access/refresh. В зависимости от аккаунта API
        # принимает в заголовке "Authorization: JWT" любой из них, поэтому берём
        # токен, который подтвердил api-token-verify/. Refresh-токен остаётся
        # запасным вариантом, чтобы сохранить прежнее поведение интеграции.
        for candidate in (token.access, token.refresh):
            if candidate and await self._is_token_valid(candidate):
                self._token = candidate
                return

        self._LOGGER.debug("Не удалось подтвердить ни один токен, используем refresh-токен")
        self._token = token.refresh

    async def _is_token_valid(self, token: str) -> bool:
        """Проверить токен через эндпоинт api-token-verify/."""
        url = urljoin(self._base_url, TOKEN_VERIFY_PATH)
        try:
            await self._send_request(url=url, method="POST", json={"token": token}, auth_retry=False)
        except (UnauthorizedUfanetIntercomAPIError, BadRequestUfanetIntercomAPIError):
            return False
        except UfanetIntercomAPIError:
            # Эндпоинт проверки недоступен — доверяем кандидату.
            return True
        return True

    async def token_verify(self) -> None:
        """Проверить текущий токен; бросает исключение, если он больше не валиден."""
        url = urljoin(self._base_url, TOKEN_VERIFY_PATH)
        await self._send_request(url=url, method="POST", json={"token": self._token}, auth_retry=False)

    async def get_intercoms(self) -> List[Intercom]:
        """Вернуть все домофоны, доступные аккаунту."""
        url = urljoin(self._base_url, INTERCOMS_PATH)
        response = await self._send_request(url=url)
        return [Intercom(**item) for item in response]

    async def open_intercom(self, intercom_id: int) -> bool:
        """Открыть дверь указанного домофона."""
        url = urljoin(self._base_url, f"api/v0/skud/shared/{intercom_id}/open/")
        response = await self._send_request(url=url)
        return bool(response.get("result")) if isinstance(response, dict) else False

    async def get_call_history(self, page: int = 1, page_size: int = 25) -> History:
        """Вернуть историю вызовов домофона."""
        url = urljoin(self._base_url, CALL_HISTORY_PATH)
        params = {"page": page, "page_size": page_size}
        response = await self._send_request(url=url, params=params)
        return History(**response)

    async def get_call_history_links(self, uuid: Union[UUID, str]) -> HistoryData:
        """Вернуть ссылки на запись и превью для вызова из истории."""
        url = urljoin(self._base_url, CALL_HISTORY_LINKS_PATH)
        response = await self._send_request(url=url, method="POST", json={"uuid": str(uuid)})
        return HistoryData(**response)

