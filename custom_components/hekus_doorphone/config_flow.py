"""Поток настройки интеграции Ufanet Door Phone."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, List, Mapping

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api.exceptions import (
    BadRequestUfanetIntercomAPIError,
    ClientConnectorUfanetIntercomAPIError,
    TimeoutUfanetIntercomAPIError,
    UnauthorizedUfanetIntercomAPIError,
    UfanetIntercomAPIError,
)
from .api.models import Intercom
from .api.ufanet_api import UfanetIntercomAPI
from .const import (
    CONF_ENABLED_INTERCOMS,
    CONF_EXCLUDED_INTERCOMS,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
)
from .device import DoorPhoneDevice, excluded_intercom_ids

if TYPE_CHECKING:
    from . import UfanetDoorPhoneData

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


def _options_schema(intercoms: List[Intercom], excluded: set[int]) -> vol.Schema:
    """Собрать форму выбора домофонов для потока опций.

    Отмечены домофоны, подключённые сейчас: всё, что пользователь не исключил.
    """
    options = [
        selector.SelectOptionDict(
            value=str(intercom.id),
            label=DoorPhoneDevice(intercom).name,
        )
        for intercom in sorted(intercoms, key=lambda item: item.id)
    ]
    default = [
        option["value"]
        for option in options
        if int(option["value"]) not in excluded
    ]
    return vol.Schema(
        {
            vol.Required(CONF_ENABLED_INTERCOMS, default=default): (
                selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            )
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Создать поток опций: выбор домофонов аккаунта."""
        return UfanetDoorPhoneOptionsFlow()

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


class UfanetDoorPhoneOptionsFlow(OptionsFlow):
    """Выбор домофонов аккаунта, подключённых к Home Assistant."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Показать список домофонов аккаунта и сохранить выбор."""
        # В Home Assistant 2024.4 у OptionsFlow ещё нет свойства config_entry,
        # поэтому запись достаём по идентификатору обработчика: он совпадает
        # с entry_id (см. OptionsFlowManager.async_create_flow).
        entry = self.hass.config_entries.async_get_entry(self.handler)
        if entry is None:
            return self.async_abort(reason="not_loaded")

        data: UfanetDoorPhoneData | None = self.hass.data.get(DOMAIN, {}).get(
            entry.entry_id
        )
        if data is None:
            return self.async_abort(reason="not_loaded")

        intercoms = list((data.coordinator.data or {}).values())
        if not intercoms:
            return self.async_abort(reason="no_devices")

        if user_input is not None:
            enabled = {int(value) for value in user_input[CONF_ENABLED_INTERCOMS]}
            excluded = sorted({intercom.id for intercom in intercoms} - enabled)
            return self.async_create_entry(
                data={
                    **entry.options,
                    CONF_EXCLUDED_INTERCOMS: excluded,
                }
            )

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(
                intercoms, excluded_intercom_ids(entry.options)
            ),
        )
