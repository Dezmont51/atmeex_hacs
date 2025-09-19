import logging

import voluptuous as vol
from .vendor.atmeexpy.atmeexpy.client import AtmeexClient

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_EMAIL
from .const import DOMAIN, CONF_ACCESS_TOKEN, CONF_REFRESH_TOKEN
from .const import CONF_AUTH_TYPE, AUTH_TYPE_BASIC, AUTH_TYPE_SMS, CONF_PHONE

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


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for atmeex cloud."""

    VERSION = 1

    def __init__(self) -> None:
        self._auth_type = AUTH_TYPE_BASIC
        self._email = None
        self._phone = None

    async def async_step_user(self, user_input=None):
        """Step 1: choose auth type only."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=_user_schema(self._auth_type)
            )

        self._auth_type = user_input.get(CONF_AUTH_TYPE, AUTH_TYPE_BASIC)

        if self._auth_type == AUTH_TYPE_SMS:
            return await self.async_step_sms()
        return await self.async_step_basic()

    async def async_step_basic(self, user_input=None):
        """Step 2 (basic): ask for email and password (code)."""
        if user_input is None:
            return self.async_show_form(
                step_id="basic", data_schema=_basic_schema(self._email)
            )

        errors = {}

        try:
            atmeex = AtmeexClient(user_input.get(CONF_EMAIL), user_input.get(CONF_PASSWORD))
            devices = await atmeex.get_devices()
            if len(devices) == 0:
                errors["base"] = "no devices found in account"
            else:
                data = {
                    CONF_EMAIL: user_input.get(CONF_EMAIL),
                    CONF_PASSWORD: user_input.get(CONF_PASSWORD),
                    CONF_AUTH_TYPE: AUTH_TYPE_BASIC,
                    CONF_ACCESS_TOKEN: atmeex.auth._access_token,
                    CONF_REFRESH_TOKEN: atmeex.auth._refresh_token,
                }
                return self.async_create_entry(
                    title=data.get(CONF_EMAIL),
                    data=data,
                )
        except Exception as exc:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = str(exc)

        return self.async_show_form(
            step_id="basic", data_schema=_basic_schema(user_input.get(CONF_EMAIL)), errors=errors
        )

    async def async_step_sms(self, user_input=None):
        """Step 2 (sms): ask for phone (stubbed)."""
        if user_input is None:
            return self.async_show_form(
                step_id="sms", data_schema=_sms_schema(self._phone)
            )

        errors = {}
        self._phone = user_input.get(CONF_PHONE)

        # Заглушка: пока не реализуем реальную SMS-авторизацию
        errors["base"] = "sms_auth_not_implemented"
        return self.async_show_form(
            step_id="sms", data_schema=_sms_schema(self._phone), errors=errors
        )
