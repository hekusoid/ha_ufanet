# AGENTS.md — структура и правила проекта hekus_doorphone

> Читать первым при любом анализе проекта: файл заменяет повторное сканирование
> репозитория. Обновлять при добавлении, удалении или переименовании модулей.
> Снимок состояния: 2026-11-16, версия интеграции 0.6.0, HEAD `5c8c14b`.

## 1. Что это за проект

HACS-интеграция «Hekus DoorPhone» (домен `hekus_doorphone`) для сервиса
«Умный дом Ufanet» (dom.ufanet.ru). На каждый домофон договора создаются три
сущности: замок для открытия двери, датчик времени последнего вызова и
изображение-превью последнего вызова.

- Репозиторий: https://github.com/hekusoid/ha_ufanet, codeowner `@hekusoid`
- `integration_type: hub`, `iot_class: cloud_polling`, `config_flow: true`
- Зависимости: `aiohttp`, `pydantic`; платформенные — `ffmpeg` + `haffmpeg`
- Минимальная версия Home Assistant: **2024.11.0** (`hacs.json`, `info.md`)
- Тестов, CI, линтеров и файлов зависимостей в проекте нет

## 2. Карта репозитория

Корень:

| Путь | Назначение |
| --- | --- |
| `README.md` | единственная документация (русский), её рендерит HACS |
| `hacs.json`, `info.md` | метаданные HACS, `homeassistant: 2024.11.0` — держать синхронно |
| `icon.png` | иконка репозитория |
| `scripts/ufanet_api_example.py` | автономная проверка API без Home Assistant |
| `AGENTS.md` | этот файл |

`custom_components/hekus_doorphone/`:

| Файл | Назначение | Ключевые символы | Строк |
| --- | --- | --- | --- |
| `__init__.py` | setup/unload записи, два координатора, хук удаления устройства | `UfanetDoorPhoneData`, `PLATFORMS`, `async_remove_config_entry_device` | 182 |
| `const.py` | все константы интеграции | `DEFAULT_SCAN_INTERVAL`, `UNLOCK_COOLDOWN`, `CALL_*`, `CONF_*` | 33 |
| `device.py` | описание устройства домофона | `DoorPhoneDevice`, `DEVICE_ID_PREFIX`, `excluded_intercom_ids` | 110 |
| `calls.py` | опрос истории вызовов, подготовка данных | `CallHistoryCoordinator`, `CallHistory`, `call_datetime`, `ATTR_*` | 222 |
| `config_flow.py` | user/reauth/reconfigure/options | `UfanetDoorPhoneConfigFlow`, `UfanetDoorPhoneOptionsFlow`, `validate_credentials` | 334 |
| `lock.py` | платформа lock, защита от повторного открытия | `DoorPhoneLock` | 139 |
| `sensor.py` | платформа sensor — последний вызов | `LastCallSensor` | 96 |
| `image.py` | платформа image — кадр превью через ffmpeg | `LastCallImage`, `_async_get_ffmpeg_binary` | 207 |
| `diagnostics.py` | выгрузка диагностики без пароля | `async_get_config_entry_diagnostics` | 71 |
| `manifest.json` | версия, зависимости, метаданные интеграции | — | 12 |
| `strings.json` | источник переводов (английский) | — | 89 |
| `translations/en.json`, `translations/ru.json` | локали | — | ~89 |
| `api/ufanet_api.py` | асинхронный клиент dom.ufanet.ru | `UfanetIntercomAPI`, `BASE_URL`, пути эндпоинтов | 205 |
| `api/models.py` | pydantic-модели ответов API | `Intercom`, `Camera`, `History`, `HistoryData`, `Token` | 104 |
| `api/exceptions.py` | исключения клиента | `UfanetIntercomAPIError` и 6 наследников | 15 |
| `README.md` | **пустой файл (0 байт), но в git** — не ошибка анализа | — | 0 |

Чего в проекте нет (не искать): `tests/`, `.github/`, `pyproject.toml`,
`setup.cfg`, `ruff.toml`, `pytest.ini`, `requirements*.txt`,
`.pre-commit-config.yaml`, `mypy.ini`.

## 3. Архитектура и потоки данных

`async_setup_entry` (`__init__.py`):

1. Создаётся `UfanetIntercomAPI(contract=username, password=password,
   session=async_get_clientsession(hass))` и вызывается `async_authenticate()`:
   400/401 → `ConfigEntryAuthFailed`, сеть/таймаут → `ConfigEntryNotReady`.
2. `DataUpdateCoordinator` домофонов с `DEFAULT_SCAN_INTERVAL = 300` с; данные —
   `{intercom.id: Intercom}`. 401 → `ConfigEntryAuthFailed`, сеть → `UpdateFailed`.
3. `CallHistoryCoordinator` со своим интервалом `CALL_HISTORY_SCAN_INTERVAL = 300` с;
   его `async_config_entry_first_refresh()` не валит загрузку — только warning.
4. `PLATFORMS = [IMAGE, LOCK, SENSOR]`, затем в `hass.data[DOMAIN][entry.entry_id]`
   кладётся `UfanetDoorPhoneData(api, coordinator, call_coordinator, devices)`
   и подписывается `_async_options_updated` → `hass.config_entries.async_reload`.
5. `async_unload_entry` выгружает платформы и вызывает `api.close()`; сессию,
   переданную Home Assistant, интеграция не закрывает.

История вызовов (`calls.py`):

- запрашивается одна страница на весь договор, `CALL_HISTORY_PAGE_SIZE = 30`:
  API не умеет фильтровать историю по камере;
- вызов относится к домофону, если `normalize_camera_number(call.camera_number)`
  совпадает с `normalize_camera_number(device.cctv_number)`;
- последний вызов — `max(calls, key=call_datetime)`; ссылки на запись и превью
  (`get_call_history_links`) запрашиваются только для него, кэш `_links`, лимит
  попыток `CALL_HISTORY_LINK_ATTEMPTS = 3`, неудачные попытки повторяются при опросах;
- `called_at` без смещения получает часовой пояс из поля `timezone` самого вызова.

API-клиент (`api/ufanet_api.py`):

- `BASE_URL = "https://dom.ufanet.ru/"`, JWT хранится в памяти, при 401 запрос
  повторяется после повторной авторизации ровно один раз;
- при восстановлении токена кандидаты проверяются через `api-token-verify/`;
- эндпоинты: `api/v1/auth/auth_by_contract/`, `api-token-verify/`,
  `api/v0/skud/shared/` (и `{id}/open/`), `api/v1/cctv/`,
  `api/v1/skuds/call-history/`, `api/v1/cctv/history/`.

Сущности:

- `unique_id` — `intercom_{id}_lock` и `intercom_{id}_last_call`;
- `_attr_has_entity_name = True` + `translation_key` (`door_lock`, `last_call`);
- устройство: `identifiers={(DOMAIN, "ufanet_doorphone_{id}")}`, manufacturer `Ufanet`,
  имя — `custom_name` домофона или `"{string_view} ({role.name})"`;
- датчик и превью создаются только для домофонов с непустым `cctv_number`;
- замок работает в `assumed_state`, повторное открытие ограничено `UNLOCK_COOLDOWN = 8` с,
  недоступен при `is_blocked` или `disable_button`.

## 4. Config flow, reauth и перенастройка (`config_flow.py`)

- `user`: номер договора и пароль → `async_set_unique_id(username)` →
  `_abort_if_unique_id_configured()` → `validate_credentials`.
- `reauth` → `reauth_confirm`: спрашивает только пароль, при успехе
  `async_update_reload_and_abort(entry, data_updates=user_input)`.
- `reconfigure`: `async_show_menu` с пунктами `credentials` и `devices`.
  - `credentials`: форма с текущими значениями (`default=` у `vol.Required`, поэтому
    значения сохраняются при повторном показе после ошибки), пароль проверяется через
    API; при успехе обновляются `unique_id`, `title` и `data`
    (`hass.config_entries.async_update_entry`), затем
    `async_update_reload_and_abort(entry, data_updates=..., reason="reconfigure_successful")`.
    Дубли `unique_id` проверяются вручную по `_async_current_entries()`: стандартный
    `_abort_if_unique_id_configured()` нашёл бы саму изменяемую запись.
  - `devices`: та же схема и селектор, что в options flow (`_options_schema`),
    записывает `CONF_EXCLUDED_INTERCOMS` в options и перезагружает запись.
- Смена учётных данных не трогает options и реестр устройств — добавление и удаление
  устройств продолжают работать как раньше.
- Исключённые домофоны (`excluded_intercoms` в options) пополняются меню/опциями и хуком
  `async_remove_config_entry_device`; вычитание отмеченных делает общий хелпер
  `_excluded_from_selection`.
- Причины аборта: `already_configured`, `reauth_successful`, `reconfigure_successful`,
  `not_loaded`, `no_devices`, `unknown`; ошибки форм: `invalid_auth`, `cannot_connect`,
  `unknown`.

## 5. Совместимость с версиями Home Assistant

- Код использует `data_updates=` в `async_update_reload_and_abort` (reauth и перенастройка).
  Параметр есть не во всех версиях HA: при выпуске 0.6.0 проверено, что он появился в
  2024.11, поэтому минимальная версия — 2024.11.0; на 2024.4 смена учётных данных упала бы
  с `TypeError`. Версии в `hacs.json` и `info.md` менять только вместе. Если понадобится
  поддержка 2024.4 — обновлять запись через `hass.config_entries.async_update_entry`
  + `async_reload` и завершать поток через `async_abort(reason="reconfigure_successful")`.
- Обходы для старых версий, которые уже есть в коде и не надо «улучшать»:
  - `OptionsFlow.config_entry` в 2024.4 нет → запись берётся по `self.handler`;
  - в reconfigure запись берётся по `self.context["entry_id"]` в свойстве
    `_entry_to_reconfigure` (метода `_get_reconfigure_entry()` в старых версиях нет);
  - `title`/`unique_id` обновляются через `hass.config_entries.async_update_entry`,
    а не параметрами `async_update_reload_and_abort`.

## 6. Правила кода

- Язык докстрингов, комментариев и сообщений в лог — русский; комментарий объясняет
  «почему», а не «что» делает строка.
- В каждом модуле `from __future__ import annotations`.
- Типизация: в `api/*` — `Dict/List/Optional` (как в pydantic-моделях), в остальных
  модулях — `dict[str, Any]` и `X | None`.
- Слой `api/` не импортирует `homeassistant` — только `aiohttp` и `pydantic`;
  всё, что знает про HA, живёт в корневых модулях пакета.
- Числовые настройки, таймауты и строковые ключи — только в `const.py`.
- Широкий `except Exception` допустим только в config flow, с `# noqa: BLE001`.
- Логи: `_LOGGER.debug` для диагностики, `warning`/`error` для проблем, влияющих
  на пользователя; f-строки в логах не использовать — только `%s`.

## 7. Переводы

- `strings.json` — источник на английском; `translations/en.json` обязан совпадать
  с ним по структуре, `translations/ru.json` — русская локализация.
- Новые `config.step.*`, `config.error.*`, `config.abort.*`, `options.*`, `entity.*`
  добавлять во все три файла одновременно, ключи держать в одинаковом порядке.
- `menu_options` описывается в переводе шага `reconfigure`.

## 8. Релиз

- При изменениях для пользователя поднимать `version` в `manifest.json`
  (история: 0.5.0 → 0.6.0 — меню перенастройки).
- `homeassistant` в `hacs.json` и `info.md` держать одинаковым и не ниже реально
  используемого API HA.
- Новые возможности описывать в корневом `README.md` (разделы «Возможности»,
  «Настройка», «Сущности»); `info.md` — только шапка метаданных.

## 9. Проверки (автотестов нет)

```powershell
# PowerShell не раскрывает маску *.py для python — компилируем каталог целиком
python -m compileall -q custom_components/hekus_doorphone; "compileall exit=$LASTEXITCODE"
python -c "import json; [json.load(open(p,encoding='utf-8')) for p in ['custom_components/hekus_doorphone/strings.json','custom_components/hekus_doorphone/translations/en.json','custom_components/hekus_doorphone/translations/ru.json']]; print('json ok')"
```

- `compileall` создаёт каталоги `__pycache__` (они в `.gitignore`) — после проверки их
  можно удалить, в коммит они не попадают.
- Пакет `homeassistant` локально не установлен, поэтому проверить импорты и сигнатуры HA
  в этой среде нельзя: опираемся на `compileall` и ручной прогон в Home Assistant.
- После правок переводов проверять паритет ключей (одинаковый набор путей в трёх файлах)
  и наличие перевода для каждого `step_id`/`reason`, использованного в config flow.
- Функциональная проверка — ручная в Home Assistant: карточка интеграции → «Настроить»
  (меню, форма учётных данных, домофоны), reauth, кнопка «Удалить» в карточке устройства.

## 10. Git-правила

- Коммит делать только по явной просьбе пользователя; после коммита дальше не коммитить.
- Сообщения на русском: короткий заголовок в императиве, при необходимости — тело
  маркированным списком (см. коммит `5c8c14b`).
- В рабочей копии файлы с CRLF, в индексе LF — предупреждения
  «CRLF will be replaced by LF» ожидаемы, настройки git не менять.
- `scripts/ufanet_api_example.py` может содержать локальные отладочные правки
  (`logging.DEBUG`, закомментированные вызовы) — в коммиты их не включать.
- Перед любой git-операцией смотреть `git status`: в рабочей копии могут быть
  чужие незакоммиченные изменения.

## 11. Окружение и инструменты

- ОС Windows, оболочка PowerShell (`powershell.exe`), кодировка консоли ломает кириллицу.
- Вывод git в терминале может отображаться как мусор — проверять содержимое через
  `Start-Process -FilePath git -ArgumentList ... -RedirectStandardOutput файл` и читать файл.
- В Plan mode запись в репозиторий запрещена, включая `Out-File` внутри проекта;
  временные файлы складывать в `%TEMP%`.
- Для правок файлов использовать редактор с UTF-8 без BOM; коммит-сообщения при
  необходимости передавать через файл и `git commit -F`.

## 12. Открытые вопросы и известные особенности

- Подтвердить минимальную версию HA 2024.11.0 (альтернатива — убрать `data_updates=`
  и опустить планку до 2024.4).
- `custom_components/hekus_doorphone/README.md` пуст: HACS использует корневой `README.md`.
- Автотестов нет; регрессии ловятся только ручной проверкой и `compileall`.
- `custom_components/hekus_doorphone/` содержит `icon.png` и `logo.png` для HACS-брендинга.


