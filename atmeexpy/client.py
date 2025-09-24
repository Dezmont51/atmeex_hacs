import httpx
import asyncio
import ssl
import logging

from .auth import AtmeexAuth
from .const import COMMON_HEADERS, ATMEEX_API_BASE_URL
from .device import Device


class AtmeexClient:

    def __init__(
        self,
        first_param: str = None,
        second_param: str = None,
        *,
        email: str = "",
        password: str = "",
        phone: str = "",
        code: str = "",
        refresh_token: str = "",
    ) -> None:
        self._logger = logging.getLogger(__name__)
        self._ssl_context = None

        # 1) Явные именованные параметры имеют приоритет
        if refresh_token:
            self.auth = AtmeexAuth(refresh_token=refresh_token)
            self.http_client = None
            return

        if email:
            if not password:
                raise ValueError(
                    "Для email авторизации необходимо указать пароль"
                )
            self.auth = AtmeexAuth(email=email, password=password)
            self.http_client = None
            return

        if phone:
            if code:
                # Phone/code авторизация
                self.auth = AtmeexAuth(phone=phone, phone_code=code)
                self.http_client = None
            else:
                # Только номер телефона (для запроса SMS) - БЕЗ авторизации
                self.auth = AtmeexAuth(phone=phone)
                self.http_client = None
            return

        # 2) Обратная совместимость с позиционными параметрами
        if first_param is None:
            raise ValueError("Не указаны параметры авторизации")

        if second_param is not None:
            # Полная совместимость с самой первой версией:
            # 2 позиционных → email/password
            self.auth = AtmeexAuth(email=first_param, password=second_param)
            self.http_client = None
        else:
            # Только номер телефона (для запроса SMS) - БЕЗ авторизации
            self.auth = AtmeexAuth(phone=first_param)
            self.http_client = None

    async def _ensure_ssl_context(self) -> ssl.SSLContext:
        if self._ssl_context is None:
            self._logger.debug("HTTP: building SSL context")

            def _build_ctx():
                return ssl.create_default_context()
            self._ssl_context = await asyncio.to_thread(_build_ctx)
            self._logger.debug("HTTP: SSL context ready")
        return self._ssl_context

    async def _ensure_http_client(self) -> None:
        if self.http_client is None:
            self._logger.debug("HTTP: creating AsyncClient")
            ssl_ctx = await self._ensure_ssl_context()
            transport = httpx.AsyncHTTPTransport(retries=2)
            self.http_client = httpx.AsyncClient(
                auth=self.auth,
                headers=COMMON_HEADERS,
                base_url=ATMEEX_API_BASE_URL,
                verify=ssl_ctx,
                timeout=httpx.Timeout(15.0),
                http2=False,
                trust_env=True,
                follow_redirects=True,
                transport=transport,
            )
            self._logger.debug("HTTP: AsyncClient ready")

    def restore_tokens(self, access_token: str, refresh_token: str):
        # Не перезатираем токены, если переданы None или пустые строки
        if access_token:
            self.auth._access_token = access_token
        if refresh_token:
            self.auth._refresh_token = refresh_token

    async def request_sms_code(self, phone: str = None) -> bool:
        """
        Запросить SMS код для авторизации

        Args:
            phone: Номер телефона (если не указан, используется из клиента)

        Returns:
            bool: True если SMS отправлен успешно
        """
        if phone is None:
            phone = self.auth.phone

        if not phone:
            raise ValueError("Необходимо указать номер телефона")

        # Создаем временный HTTP клиент без авторизации для запроса SMS
        ssl_ctx = await self._ensure_ssl_context()
        transport = httpx.AsyncHTTPTransport(retries=2)
        temp_client = httpx.AsyncClient(
            headers=COMMON_HEADERS,
            base_url=ATMEEX_API_BASE_URL,
            verify=ssl_ctx,
            timeout=httpx.Timeout(15.0),
            http2=False,
            trust_env=True,
            follow_redirects=True,
            transport=transport
        )

        try:
            self._logger.debug("API request_sms_code phone=%s", phone)
            payload = {
                "grant_type": "phone_code",
                "phone": phone,
            }
            response = await temp_client.post("/auth/signup", json=payload)
            response.raise_for_status()
            self._logger.debug(
                "API request_sms_code status=%s", response.status_code
            )
            return True
        finally:
            await temp_client.aclose()

    async def get_devices(self):
        if self.http_client is None:
            await self._ensure_http_client()

        resp = await self.http_client.get("/devices")
        devices_list = resp.json()
        try:
            devices = [
                Device(self.http_client, device_dict)
                for device_dict in devices_list
            ]
        except Exception:
            print(devices_list)
            return []
        return devices

    def set_temp(self, device_id, temp):
        pass
