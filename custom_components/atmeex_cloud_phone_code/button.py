import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AtmeexDataCoordinator
from .const import DOMAIN
from .vendor.atmeexpy.atmeexpy.device import Device

_LOGGER = logging.getLogger(__name__)


BUTTON_TYPES = (
    ("power_toggle", "toggle_power", "mdi:power"),
    ("vent_passive", "ventilation_passive", "mdi:weather-windy"),
    ("recuperation", "recuperation", "mdi:sync"),
    ("supply_valve", "supply_mode", "mdi:valve"),
)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    coordinator: AtmeexDataCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[ButtonEntity] = []

    for device in coordinator.devices:
        for key, action, icon in BUTTON_TYPES:
            entities.append(AtmeexButtonEntity(device, coordinator, key, action, icon))

    async_add_entities(entities)


class AtmeexButtonEntity(CoordinatorEntity, ButtonEntity):
    def __init__(self, device: Device, coordinator: AtmeexDataCoordinator, key: str, action: str, icon: str):
        CoordinatorEntity.__init__(self, coordinator=coordinator)
        self.coordinator = coordinator
        self.device = device
        self._key = key
        self._action = action
        self._attr_icon = icon

        device_mac = getattr(self.device.model, "mac", None)
        device_id = str(getattr(self.device.model, "id", "unknown"))
        unique_base = (device_mac or device_id)
        self._attr_unique_id = f"{unique_base}_button_{key}"

        manufacturer = "Atmeex"
        model_name = getattr(self.device.model, "model", None)
        sw_ver = getattr(self.device.model, "fw_ver", None)
        device_name = getattr(self.device.model, "name", None)
        identifier_value = device_mac or f"id-{device_id}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, identifier_value)},
            "manufacturer": manufacturer,
            "model": model_name,
            "name": device_name,
            "sw_version": sw_ver,
        }

        names = {
            "power_toggle": "Вкл/Выкл",
            "vent_passive": "Проветривание",
            "recuperation": "Рекуперация",
            "supply_valve": "Приточный клапан",
        }
        self._attr_name = f"{device_name} {names.get(key, key)}"

    async def async_press(self) -> None:
        try:
            if self._action == "toggle_power":
                await self.device.set_power(not self.device.model.settings.u_pwr_on)
            elif self._action == "ventilation_passive":
                await self.device.enable_passive_ventilation()
            elif self._action == "recuperation":
                await self.device.enable_recuperation()
            elif self._action == "supply_mode":
                # Приточный режим: питание вкл, заслонка открыта
                await self.device.enable_supply_mode()
            else:
                _LOGGER.error("Unknown button action: %s", self._action)
                return

            await self.coordinator.async_request_refresh()
        except Exception:
            _LOGGER.exception("Failed to execute button action %s", self._action)

    def _handle_coordinator_update(self) -> None:
        device_id = self.device.model.id
        same_devices = [d for d in self.coordinator.devices if d.model.id == device_id]
        if same_devices:
            self.device = same_devices[0]
        self.async_write_ha_state()


