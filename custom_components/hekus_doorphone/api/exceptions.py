"""Исключения клиента API домофонов Ufanet."""


class UfanetIntercomAPIError(Exception):
    """Базовая ошибка клиента API домофонов Ufanet."""


class ClientConnectorUfanetIntercomAPIError(UfanetIntercomAPIError):
    """Не удалось установить соединение с API Ufanet."""


class UnauthorizedUfanetIntercomAPIError(UfanetIntercomAPIError):
    """API отклонил токен или учётные данные (HTTP 401)."""


class TimeoutUfanetIntercomAPIError(UfanetIntercomAPIError):
    """Истекло время ожидания ответа API Ufanet."""


class UnknownUfanetIntercomAPIError(UfanetIntercomAPIError):
    """Неизвестная ошибка API Ufanet: неожиданный статус ответа."""


class InvalidTokenUfanetIntercomAPIError(UfanetIntercomAPIError):
    """Токен не прошёл проверку api-token-verify/."""


class BadRequestUfanetIntercomAPIError(UfanetIntercomAPIError):
    """API отклонил запрос (HTTP 400); тело ответа лежит в args[0]."""