import httpx
import logging
import typing

from .const import ATMEEX_API_BASE_URL, COMMON_HEADERS

_LOGGER = logging.getLogger(__name__)


class AtmeexAuth(httpx.Auth):
    requires_response_body = True

    def __init__(self, email: str = "",
                 password: str = "",
                 phone: str = "",
                 phone_code: str = "",
                 access_token: str = "",
                 refresh_token: str = ""):
        self.email = email
        self.password = password
        self.phone = phone
        self.phone_code = phone_code
        self._access_token = access_token
        self._refresh_token = refresh_token

    def auth_flow(
        self, request: httpx.Request
    ) -> typing.Generator[httpx.Request, httpx.Response, None]:
        if self._access_token == "":
            # Если есть refresh_token — пробуем авторизоваться по нему
            if self._refresh_token:
                _LOGGER.debug("auth_flow: no access token, try refresh")
                yield from self.refresh_token()
            elif self.phone and self.phone_code:
                _LOGGER.debug("auth_flow: no access token, use phone_code")
                yield from self.auth_with_phone_code()
            elif self.email and self.password:
                _LOGGER.debug("auth_flow: no access token, use email/password")
                yield from self.auth_with_email()
            else:
                raise ValueError(
                    "Необходимо указать refresh_token или phone+phone_code, "
                    "или email+password для авторизации"
                )

        request.headers["authorization"] = f"Bearer {self._access_token}"
        _LOGGER.debug(
            "auth_flow: sending original request %s %s",
            request.method, request.url
        )

        response = yield request

        if response.status_code == 401:
            _LOGGER.debug("auth_flow: got 401, refresh and retry")
            yield from self.refresh_token()
            request.headers["authorization"] = f"Bearer {self._access_token}"

            response = yield request

    def refresh_token(
        self
    ) -> typing.Generator[httpx.Request, httpx.Response, None]:
        if self._refresh_token == "":
            if self.phone and self.phone_code:
                yield from self.auth_with_phone_code()
            elif self.email and self.password:
                yield from self.auth_with_email()
            else:
                raise ValueError(
                    "Необходимо указать либо phone+phone_code, либо "
                    "email+password для обновления токена"
                )
            return

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
        }
        _LOGGER.debug("auth.refresh: POST /auth/signin")
        try:
            response = yield httpx.Request(
                "POST",
                ATMEEX_API_BASE_URL + "/auth/signin",
                json=payload,
                headers=COMMON_HEADERS
            )
        except Exception as exc:
            _LOGGER.exception("auth.refresh: request failed: %s", exc)
            raise
        _LOGGER.debug("auth.refresh: status=%s", response.status_code)
        try:
            _data = response.json()
            _LOGGER.debug(
                "auth.refresh: response tokens access_token=%s "
                "refresh_token=%s",
                _data.get("access_token"),
                _data.get("refresh_token"),
            )
        except Exception as exc:
            _LOGGER.debug(
                "auth.refresh: failed to parse JSON for tokens: %s", exc
            )
        if response.status_code == 401:
            # Refresh-токен невалиден/истёк.
            # Не используем одноразовый phone_code для фолбэка.
            if self.email and self.password:
                yield from self.auth_with_email()
            else:
                raise ValueError(
                    "Не удалось обновить токен: требуется "
                    "повторная авторизация"
                )
        else:
            self.handle_auth_response(response)

    def auth_with_email(
        self
    ) -> typing.Generator[httpx.Request, httpx.Response, None]:
        payload = {
            "email": self.email,
            "password": self.password,
            "grant_type": "basic",
        }
        _LOGGER.debug("auth.email: POST /auth/signin for %s", self.email)
        try:
            response = yield httpx.Request(
                "POST",
                ATMEEX_API_BASE_URL + "/auth/signin",
                json=payload,
                headers=COMMON_HEADERS
            )
        except Exception as exc:
            _LOGGER.exception("auth.email: request failed: %s", exc)
            raise
        finally:
            pass
        self.handle_auth_response(response)

    def auth_with_phone_code(
        self
    ) -> typing.Generator[httpx.Request, httpx.Response, None]:
        payload = {
            "phone": self.phone,
            "phone_code": self.phone_code,
            "grant_type": "phone_code",
        }
        _LOGGER.debug("auth.phone_code: POST /auth/signin for %s", self.phone)
        try:
            response = yield httpx.Request(
                "POST",
                ATMEEX_API_BASE_URL + "/auth/signin",
                json=payload,
                headers=COMMON_HEADERS
            )
        except Exception as exc:
            _LOGGER.exception("auth.phone_code: request failed: %s", exc)
            raise
        finally:
            pass
        self.handle_auth_response(response)

    def request_sms_code(
        self, phone: str
    ) -> typing.Generator[httpx.Request, httpx.Response, None]:
        """
        Запрос SMS кода для авторизации по телефону

        Args:
            phone: Номер телефона в формате "+7(900)123-45-67"
        """
        payload = {
            "grant_type": "phone_code",
            "phone": phone,
        }
        response = yield httpx.Request(
            "POST",
            ATMEEX_API_BASE_URL + "/auth/signup",
            json=payload,
            headers=COMMON_HEADERS
        )
        _LOGGER.debug("auth.response: status=%s", response.status_code)
        response.raise_for_status()
        return response

    def handle_auth_response(self, response: httpx.Response):
        response.raise_for_status()

        data = response.json()
        self._refresh_token = data["refresh_token"]
        self._access_token = data["access_token"]
