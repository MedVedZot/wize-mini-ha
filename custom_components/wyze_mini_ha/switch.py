import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    selected = entry.options.get("devices", [])
    entities = [WyzeSpotlightSwitch(coordinator, mac) for mac in coordinator.data if mac in selected]
    async_add_entities(entities)

class WyzeSpotlightSwitch(CoordinatorEntity, SwitchEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _attr_icon = "mdi:lightbulb-spot"

    def __init__(self, coordinator, mac):
        super().__init__(coordinator)
        self._mac = mac
        self._attr_name = "Spotlight"
        self._attr_unique_id = f"{mac}_spotlight"

    @property
    def device_info(self):
        d = self.coordinator.data.get(self._mac, {})
        return DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=d.get("name"),
            manufacturer="Wyze",
            model=str(d.get("product_model")),
            sw_version=str(d.get("firmware")),
            hw_version=self._mac,
        )

    @property
    def is_on(self):
        return self.coordinator.data.get(self._mac, {}).get("spotlight")

    async def async_turn_on(self, **kwargs):
        client = await self.coordinator.wyze_client._ensure_client()
        model = self.coordinator.data[self._mac]["product_model"]
        await client.set_property(self._mac, model, "P1056", "1")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        client = await self.coordinator.wyze_client._ensure_client()
        model = self.coordinator.data[self._mac]["product_model"]
        await client.set_property(self._mac, model, "P1056", "0")
        await self.coordinator.async_request_refresh()