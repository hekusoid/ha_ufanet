"""Поток настройки интеграции Ufanet Door Phone."""
from __future__ import annotations

import logging
from typing import Any, Mapping

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api.exceptions import (
    BadRequestUfanetIntercomAPIError,
    ClientConnectorUfanetIntercomAPIError,
    TimeoutUfanetIntercomAPIError,
    UnauthorizedUfanetIntercomAPIError,
    UfanetIntercomAPIError,
)
from .api.ufanet_api import UfanetIntercomAPI
from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class CannotConnect(HomeAssistantError):
    """Не удалось подключиться к API Ufanet."""


class InvalidAuth(HomeAssistantError):
    """Неверный номер договора или пароль."""


def _bad_request_message(err: BadRequestUfanetIntercomAPIError) -> str:
    """Достать осмысленное сообщение из ответа 400."""
    payload = err.args[0] if err.args else None
    if isinstance(payload, dict):
        for key in ("non_field_errors", "detail", "contract", "password"):
            value = payload.get(key)
            if isinstance(value, (list, tuple)) and value:
                return str(value[0])
            if isinstance(value, str) and value:
                return value
    return "Неверный номер договора или пароль"


async def validate_credentials(hass: HomeAssistant, data: Mapping[str, Any]) -> None:
    """Проверить учётные данные, подняв InvalidAuth / CannotConnect."""
    api = UfanetIntercomAPI(
        contract=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
        logger_name=f"{DOMAIN}.config_flow",
    )

    try:
        await api.async_authenticate()
    except BadRequestUfanetIntercomAPIError as err:
        raise InvalidAuth(_bad_request_message(err)) from err
    except UnauthorizedUfanetIntercomAPIError as err:
        raise InvalidAuth("Неверный номер договора или пароль") from err
    except (ClientConnectorUfanetIntercomAPIError, TimeoutUfanetIntercomAPIError) as err:
        raise CannotConnect(str(err)) from err
    except UfanetIntercomAPIError as err:
        raise CannotConnect(str(err)) from err


class UfanetDoorPhoneConfigFlow(ConfigFlow, domain=DOMAIN):
    """Поток настройки Ufanet Door Phone."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Обработать шаг ввода номера договора и пароля."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()

            try:
                await validate_credentials(self.hass, user_input)
            except InvalidAuth as err:
                _LOGGER.warning("Ошибка аутентификации в Ufanet: %s", err)
                errors["base"] = "invalid_auth"
            except CannotConnect as err:
                _LOGGER.error("Не удалось подключиться к Ufanet API: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 - показываем пользователю любую ошибку
                _LOGGER.exception("Неожиданная ошибка при проверке учётных данных")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"Домофон Ufanet (договор №{user_input[CONF_USERNAME]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Запустить поток повторной аутентификации."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Запросить пароль заново и проверить его."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        errors: dict[str, str] = {}

        if entry is None:
            return self.async_abort(reason="unknown")

        if user_input is not None:
            credentials = {**entry.data, **user_input}
            try:
                await validate_credentials(self.hass, credentials)
            except InvalidAuth as err:
                _LOGGER.warning("Ошибка аутентификации в Ufanet: %s", err)
                errors["base"] = "invalid_auth"
            except CannotConnect as err:
                _LOGGER.error("Не удалось подключиться к Ufanet API: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Неожиданная ошибка при проверке учётных данных")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders={
                "username": str(entry.data.get(CONF_USERNAME, ""))
            },
        )
