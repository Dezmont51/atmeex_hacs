from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
)

from .vendor.atmeexpy.atmeexpy.client import AtmeexClient

from .const import CONF_ACCESS_TOKEN, CONF_REFRESH_TOKEN, DOMAIN, PLATFORMS
from .const import CONF_AUTH_TYPE, AUTH_TYPE_BASIC, AUTH_TYPE_SMS, CONF_PHONE, CONF_CODE

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    hass.data[DOMAIN] = {}
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    auth_type = entry.data.get(CONF_AUTH_TYPE, AUTH_TYPE_BASIC)
    _LOGGER.debug("Init setup_entry auth_type=%s", auth_type)

    if auth_type == AUTH_TYPE_SMS:
        api = AtmeexClient(entry.data[CONF_PHONE], entry.data.get(CONF_CODE, ""))
    else:
        api = AtmeexClient(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])

    api.restore_tokens(entry.data.get(CONF_ACCESS_TOKEN), entry.data.get(CONF_REFRESH_TOKEN))

    coordinator = AtmeexDataCoordinator(hass, api, entry)
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await coordinator.async_refresh()

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(
                entry, platform
            )
        )
    return True

class AtmeexDataCoordinator(DataUpdateCoordinator):

    def __init__(self, hass: HomeAssistant, api: AtmeexClient, entry: ConfigEntry):
        super().__init__(
            hass,
            _LOGGER,
            name="Atmeex Coordinator",
            update_interval=timedelta(seconds=60),
        )

        self.hass = hass
        self.api = api
        self.devices = []
        self.entry: ConfigEntry = entry

    async def _async_update_data(self):
        self.devices = await self.api.get_devices()

        if self.entry.data[CONF_ACCESS_TOKEN] != self.api.auth._access_token or \
            self.entry.data[CONF_REFRESH_TOKEN] != self.api.auth._refresh_token:

            data = self.entry.data
            data[CONF_ACCESS_TOKEN] = self.api.auth._access_token
            data[CONF_REFRESH_TOKEN] = self.api.auth._refresh_token

            await self.hass.config_entries.async_update_entry(self.entry, data=data)
