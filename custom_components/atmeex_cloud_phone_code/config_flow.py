import logging

import voluptuous as vol
from .vendor.atmeexpy.atmeexpy.client import AtmeexClient

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_EMAIL
from .const import DOMAIN, CONF_ACCESS_TOKEN, CONF_REFRESH_TOKEN
from .const import CONF_AUTH_TYPE, AUTH_TYPE_BASIC, AUTH_TYPE_SMS, CONF_PHONE, CONF_CODE

_LOGGER = logging.getLogger(__name__)


def _user_schema(default_auth_type=None):
    return vol.Schema(
        {
            vol.Required(CONF_AUTH_TYPE, default=default_auth_type or AUTH_TYPE_BASIC): vol.In([AUTH_TYPE_BASIC, AUTH_TYPE_SMS]),
        }
    )


def _basic_schema(default_email=None):
    return vol.Schema(
        {
            vol.Required(CONF_EMAIL, default=default_email or ""): str,
            vol.Required(CONF_PASSWORD): str,
        }
    )


def _sms_schema(default_phone=None):
    return vol.Schema(
        {
            vol.Required(CONF_PHONE, default=default_phone or ""): str,
        }
    )


def _sms_code_schema(default_phone=None):
    return vol.Schema(
        {
            vol.Required(CONF_PHONE, default=default_phone or ""): str,
            vol.Required(CONF_CODE): str,
        }
    )


def _normalize_phone(raw_phone: str) -> str:
    # Удаляем всё, кроме цифр
    digits = "".join(ch for ch in (raw_phone or "") if ch.isdigit())
    if not digits:
        raise ValueError("empty")
    # Если 10 цифр, считаем, что это без кода страны (Россия)
    if len(digits) == 10:
        digits = "7" + digits
    # Если начинается на 8 и длина 11 — приводим к 7
    if len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    # Требуем 11 цифр и ведущую 7
    if len(digits) != 11 or digits[0] not in ("7",):
        raise ValueError("invalid")
    return "+" + digits


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for atmeex cloud."""

    VERSION = 1

    def __init__(self) -> None:
        self._auth_type = AUTH_TYPE_BASIC
        self._email = None
        self._phone = None

    async def async_step_user(self, user_input=None):
        _LOGGER.debug("CF user step start, user_input=%s", {k: ('***' if k in [CONF_PASSWORD, CONF_CODE] else v) for k, v in (user_input or {}).items()})
        """Step 1: choose auth type only."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=_user_schema(self._auth_type)
            )

        self._auth_type = user_input.get(CONF_AUTH_TYPE, AUTH_TYPE_BASIC)
        _LOGGER.debug("CF user selected auth_type=%s", self._auth_type)

        if self._auth_type == AUTH_TYPE_SMS:
            return await self.async_step_sms()
        return await self.async_step_basic()

    async def async_step_basic(self, user_input=None):
        _LOGGER.debug("CF basic step, user_input=%s", {k: ('***' if k in [CONF_PASSWORD] else v) for k, v in (user_input or {}).items()})
        """Step 2 (basic): ask for email and password (code)."""
        if user_input is None:
            return self.async_show_form(
                step_id="basic", data_schema=_basic_schema(self._email)
            )

        errors = {}

        try:
            email = (user_input.get(CONF_EMAIL) or "").strip().lower()
            unique_id = f"user:{email}"
            # Устанавливаем уникальный ID записи и предотвращаем дублирование
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            _LOGGER.debug("CF basic auth: email=%s", user_input.get(CONF_EMAIL))
            atmeex = AtmeexClient(user_input.get(CONF_EMAIL), user_input.get(CONF_PASSWORD))
            devices = await atmeex.get_devices()
            _LOGGER.debug("CF basic devices_count=%s", len(devices) if isinstance(devices, list) else 'N/A')
            if len(devices) == 0:
                errors["base"] = "no_devices"
            else:
                data = {
                    CONF_EMAIL: user_input.get(CONF_EMAIL),
                    CONF_PASSWORD: "***",
                    CONF_AUTH_TYPE: AUTH_TYPE_BASIC,
                    CONF_ACCESS_TOKEN: atmeex.auth._access_token,
                    CONF_REFRESH_TOKEN: atmeex.auth._refresh_token,
                }
                _LOGGER.debug("CF basic success create_entry title=%s", data.get(CONF_EMAIL))
                return self.async_create_entry(
                    title=data.get(CONF_EMAIL),
                    data={**data, CONF_PASSWORD: user_input.get(CONF_PASSWORD)},
                )
        except Exception as exc:
            _LOGGER.exception("CF basic unexpected exception: %s", exc)
            errors["base"] = str(exc)

        return self.async_show_form(
            step_id="basic", data_schema=_basic_schema(user_input.get(CONF_EMAIL)), errors=errors
        )

    async def async_step_sms(self, user_input=None):
        _LOGGER.debug("CF sms step, user_input=%s", user_input)
        """Step 2 (sms): request SMS code for provided phone."""
        if user_input is None:
            return self.async_show_form(
                step_id="sms", data_schema=_sms_schema(self._phone)
            )

        errors = {}
        raw_phone = user_input.get(CONF_PHONE)
        try:
            phone = _normalize_phone(raw_phone)
            _LOGGER.debug("CF sms normalized phone=%s", phone)
            # Устанавливаем уникальный ID записи сразу, как только знаем телефон
            await self.async_set_unique_id(f"phone:{phone}")
            self._abort_if_unique_id_configured()
        except Exception as norm_exc:
            _LOGGER.debug("CF sms invalid phone input=%s, err=%s", raw_phone, norm_exc)
            errors["base"] = "invalid_phone"
            return self.async_show_form(
                step_id="sms", data_schema=_sms_schema(raw_phone), errors=errors
            )

        try:
            _LOGGER.debug("CF sms requesting code for phone=%s", phone)
            sms_client = AtmeexClient(phone)
            ok = await sms_client.request_sms_code()
            _LOGGER.debug("CF sms request result=%s", ok)
            if not ok:
                errors["base"] = "sms_send_failed"
                return self.async_show_form(
                    step_id="sms", data_schema=_sms_schema(phone), errors=errors
                )
            self._phone = phone
            return await self.async_step_sms_code()
        except Exception as exc:
            _LOGGER.exception("CF sms request error: %s", exc)
            errors["base"] = "sms_send_failed"
            return self.async_show_form(
                step_id="sms", data_schema=_sms_schema(raw_phone), errors=errors
            )

    async def async_step_sms_code(self, user_input=None):
        _LOGGER.debug("CF sms_code step, user_input=%s", {k: ('***' if k in [CONF_CODE] else v) for k, v in (user_input or {}).items()})
        """Step 3 (sms_code): verify code and create entry."""
        if user_input is None:
            return self.async_show_form(
                step_id="sms_code", data_schema=_sms_code_schema(self._phone)
            )

        errors = {}
        raw_phone = user_input.get(CONF_PHONE) or self._phone
        code = user_input.get(CONF_CODE)
        try:
            phone = _normalize_phone(raw_phone)
        except Exception as norm_exc:
            _LOGGER.debug("CF sms_code invalid phone input=%s, err=%s", raw_phone, norm_exc)
            errors["base"] = "invalid_phone"
            return self.async_show_form(
                step_id="sms_code", data_schema=_sms_code_schema(raw_phone), errors=errors
            )

        try:
            _LOGGER.debug("CF sms_code trying auth for phone=%s", phone)
            client = AtmeexClient(phone, code)
            devices = await client.get_devices()
            _LOGGER.debug("CF sms_code devices_count=%s", len(devices) if isinstance(devices, list) else 'N/A')
            if len(devices) == 0:
                errors["base"] = "no_devices"
            else:
                data = {
                    CONF_AUTH_TYPE: AUTH_TYPE_SMS,
                    CONF_PHONE: phone,
                    CONF_CODE: "***",
                    CONF_ACCESS_TOKEN: client.auth._access_token,
                    CONF_REFRESH_TOKEN: client.auth._refresh_token,
                }
                _LOGGER.debug("CF sms_code success create_entry title=%s", phone)
                return self.async_create_entry(
                    title=phone,
                    data={**data, CONF_CODE: code},
                )
        except Exception as exc:
            _LOGGER.exception("CF sms_code unexpected exception: %s", exc)
            errors["base"] = str(exc)

        return self.async_show_form(
            step_id="sms_code", data_schema=_sms_code_schema(raw_phone), errors=errors
        )
