import httpx
import typing

from .const import ATMEEX_API_BASE_URL, COMMON_HEADERS


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

    def auth_flow(self, request: httpx.Request) -> typing.Generator[httpx.Request, httpx.Response, None]:
        if self._access_token == "":
            if self.phone and self.phone_code:
                yield from self.auth_with_phone_code()
            elif self.email and self.password:
                yield from self.auth_with_email()
            else:
                raise ValueError("Необходимо указать либо phone+phone_code, либо email+password для авторизации")

        request.headers["authorization"] = f"Bearer {self._access_token}"
        response = yield request

        if response.status_code == 401:
            yield from self.refresh_token()
            request.headers["authorization"] = f"Bearer {self._access_token}"
            yield request

    def refresh_token(self) -> typing.Generator[httpx.Request, httpx.Response, None]:
        if self._refresh_token == "":
            if self.phone and self.phone_code:
                yield from self.auth_with_phone_code()
            elif self.email and self.password:
                yield from self.auth_with_email()
            else:
                raise ValueError("Необходимо указать либо phone+phone_code, либо email+password для обновления токена")
            return

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
        }
        response = yield httpx.Request("POST", ATMEEX_API_BASE_URL + "/auth/signin", json=payload, headers=COMMON_HEADERS)
        if response.status_code == 401:
            yield from self.auth_with_email()
        else:
            self.handle_auth_response(response)

    def auth_with_email(self) -> typing.Generator[httpx.Request, httpx.Response, None]:
        payload = {
            "email": self.email,
            "password": self.password,
            "grant_type": "basic",
        }
        response = yield httpx.Request("POST", ATMEEX_API_BASE_URL + "/auth/signin", json=payload, headers=COMMON_HEADERS)
        self.handle_auth_response(response)

    def auth_with_phone_code(self) -> typing.Generator[httpx.Request, httpx.Response, None]:
        payload = {
            "phone": self.phone,
            "phone_code": self.phone_code,
            "grant_type": "phone_code",
        }
        response = yield httpx.Request("POST", ATMEEX_API_BASE_URL + "/auth/signin", json=payload, headers=COMMON_HEADERS)
        self.handle_auth_response(response)

    def request_sms_code(self, phone: str) -> typing.Generator[httpx.Request, httpx.Response, None]:
        """
        Запрос SMS кода для авторизации по телефону
        
        Args:
            phone: Номер телефона в формате "+7(900)123-45-67"
        """
        payload = {
            "grant_type": "phone_code",
            "phone": phone,
        }
        response = yield httpx.Request("POST", ATMEEX_API_BASE_URL + "/auth/signup", json=payload, headers=COMMON_HEADERS)
        response.raise_for_status()
        return response

    def handle_auth_response(self, response: httpx.Response):
        response.raise_for_status()

        data = response.json()
        self._refresh_token = data["refresh_token"]
        self._access_token = data["access_token"]