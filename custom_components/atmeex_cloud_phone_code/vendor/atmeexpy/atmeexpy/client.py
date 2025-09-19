import httpx

from .auth import AtmeexAuth
from .const import COMMON_HEADERS, ATMEEX_API_BASE_URL
from .device import Device


class AtmeexClient:

    def __init__(self, first_param: str, second_param: str = None) -> None:
        # Определяем тип авторизации по наличию @ в первом параметре
        if "@" in first_param:
            # Email/password авторизация
            if not second_param:
                raise ValueError("Для email авторизации необходимо указать пароль")
            self.auth = AtmeexAuth(email=first_param, password=second_param)
            # Создаем клиент С авторизацией
            self.http_client = httpx.AsyncClient(auth=self.auth, headers=COMMON_HEADERS, base_url=ATMEEX_API_BASE_URL)
        elif second_param is None:
            # Только номер телефона (для запроса SMS) - БЕЗ авторизации
            self.auth = AtmeexAuth(phone=first_param)
            # НЕ создаем http_client - он создается временно в request_sms_code()
            self.http_client = None
        else:
            # Phone/code авторизация
            self.auth = AtmeexAuth(phone=first_param, phone_code=second_param)
            # Создаем клиент С авторизацией
            self.http_client = httpx.AsyncClient(auth=self.auth, headers=COMMON_HEADERS, base_url=ATMEEX_API_BASE_URL)


    def restore_tokens(self, access_token: str, refresh_token: str):
        self.auth._access_token = access_token
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
        temp_client = httpx.AsyncClient(headers=COMMON_HEADERS, base_url=ATMEEX_API_BASE_URL)
        
        try:
            payload = {
                "grant_type": "phone_code",
                "phone": phone,
            }
            response = await temp_client.post("/auth/signup", json=payload)
            response.raise_for_status()
            return True
        finally:
            await temp_client.aclose()

    async def get_devices(self):
        if self.http_client is None:
            raise ValueError("Клиент создан только для запроса SMS. Создайте новый клиент с кодом для получения устройств.")

        resp = await self.http_client.get("/devices")
        devices_list = resp.json()
        try:
            devices = [Device(self.http_client, device_dict) for device_dict in devices_list]
        except Exception:
            print(devices_list)
            return []
        return devices

    def set_temp(self, device_id, temp):
        pass