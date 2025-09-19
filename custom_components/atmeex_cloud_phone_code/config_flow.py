import logging

import voluptuous as vol
from .vendor.atmeexpy.atmeexpy.client import AtmeexClient

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_EMAIL
from .const import DOMAIN, CONF_ACCESS_TOKEN, CONF_REFRESH_TOKEN
from .const import CONF_AUTH_TYPE, AUTH_TYPE_BASIC, AUTH_TYPE_SMS

_LOGGER = logging.getLogger(__name__)


def _build_schema(auth_type: str | None):
    if auth_type == AUTH_TYPE_SMS:
        return vol.Schema(
            {
                vol.Required(CONF_AUTH_TYPE, default=AUTH_TYPE_SMS): vol.In([AUTH_TYPE_BASIC, AUTH_TYPE_SMS]),
                vol.Required(CONF_EMAIL): str,
            }
        )
    # default/basic
    return vol.Schema(
        {
            vol.Required(CONF_AUTH_TYPE, default=AUTH_TYPE_BASIC): vol.In([AUTH_TYPE_BASIC, AUTH_TYPE_SMS]),
            vol.Required(CONF_EMAIL): str,
            vol.Required(CONF_PASSWORD): str,
        }
    )


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for atmeex cloud."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=_build_schema(AUTH_TYPE_BASIC)
            )

        errors = {}

        auth_type = user_input.get(CONF_AUTH_TYPE, AUTH_TYPE_BASIC)

        # Если выбрано SMS — показываем только email и ставим заглушку
        if auth_type == AUTH_TYPE_SMS:
            errors["base"] = "sms_auth_not_implemented"
            return self.async_show_form(
                step_id="user", data_schema=_build_schema(AUTH_TYPE_SMS), errors=errors
            )

        # BASIC авторизация: ожидаем и email, и password
        try:
            atmeex = AtmeexClient(user_input.get(CONF_EMAIL), user_input.get(CONF_PASSWORD))
            devices = await atmeex.get_devices()
            if len(devices) == 0:
                errors["base"] = "no devices found in account"
            else:
                user_input[CONF_ACCESS_TOKEN] = atmeex.auth._access_token
                user_input[CONF_REFRESH_TOKEN] = atmeex.auth._refresh_token
                return self.async_create_entry(
                    title=user_input.get(CONF_EMAIL),
                    data=user_input,
                )
        except Exception as exc:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = str(exc)

        return self.async_show_form(
            step_id="user", data_schema=_build_schema(AUTH_TYPE_BASIC), errors=errors
        )
