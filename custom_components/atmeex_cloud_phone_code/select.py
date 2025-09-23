import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AtmeexDataCoordinator
from .const import DOMAIN
from .vendor.atmeexpy.atmeexpy.device import Device

_LOGGER = logging.getLogger(__name__)

OPTIONS = [
    "Выкл",
    "Проветривание",
    "Рекуперация",
    "Приточный клапан",
]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    coordinator: AtmeexDataCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[SelectEntity] = [AtmeexModeSelect(device, coordinator) for device in coordinator.devices]
    async_add_entities(entities)


class AtmeexModeSelect(CoordinatorEntity, SelectEntity):
    _attr_options = OPTIONS

    def __init__(self, device: Device, coordinator: AtmeexDataCoordinator):
        CoordinatorEntity.__init__(self, coordinator=coordinator)
        self.coordinator = coordinator
        self.device = device

        device_mac = getattr(self.device.model, "mac", None)
        device_id = str(getattr(self.device.model, "id", "unknown"))
        unique_base = (device_mac or device_id)
        self._attr_unique_id = f"{unique_base}_mode_select"

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

        self._attr_name = f"{device_name} Режим"
        self._update_state()

    def _current_mode_name(self) -> str:
        s = self.device.model.settings
        if not s.u_pwr_on:
            if s.u_damp_pos == 0:
                return "Проветривание"  # пассивное
            return "Выкл"
        # питание включено
        if s.u_damp_pos == 1:
            return "Рекуперация"
        if s.u_damp_pos == 0:
            return "Приточный клапан"
        return "Выкл"

    def _update_state(self):
        self._attr_current_option = self._current_mode_name()

    async def async_select_option(self, option: str) -> None:
        try:
            if option == "Выкл":
                await self.device.set_power(False)
            elif option == "Проветривание":
                await self.device.enable_passive_ventilation()
            elif option == "Рекуперация":
                await self.device.enable_recuperation()
            elif option == "Приточный клапан":
                await self.device.enable_supply_mode()
            else:
                _LOGGER.error("Unknown option: %s", option)
                return

            await self.coordinator.async_request_refresh()
        except Exception:
            _LOGGER.exception("Failed to set mode: %s", option)

    def _handle_coordinator_update(self) -> None:
        device_id = self.device.model.id
        same_devices = [d for d in self.coordinator.devices if d.model.id == device_id]
        if same_devices:
            self.device = same_devices[0]
            self._update_state()
        self.async_write_ha_state()


