import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify
from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    selected = entry.options.get("devices", [])
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    existing_entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    for ent in existing_entries:
        mac = ent.unique_id.split('_')[0]
        if mac not in selected or not ent.unique_id.endswith("_motion"):
            entity_registry.async_remove(ent.entity_id)
            if mac not in selected:
                device = device_registry.async_get_device(identifiers={(DOMAIN, mac)})
                if device:
                    device_registry.async_remove_device(device.id)

    for mac, data in coordinator.data.items():
        if mac not in selected: continue
        name = data.get("name")
        device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, mac)},
            name=name,
            manufacturer="Wyze",
            model=data.get("product_model"),
            sw_version=data.get("firmware"),
            hw_version=mac
        )
        
        new_prefix = slugify(name)
        entity_entries = er.async_entries_for_device(entity_registry, device.id)
        for ee in entity_entries:
            if ee.unique_id.endswith("_motion"):
                expected_id = f"sensor.{new_prefix}_motion"
                if ee.entity_id != expected_id and not entity_registry.async_is_registered(expected_id):
                    try:
                        entity_registry.async_update_entity(ee.entity_id, new_entity_id=expected_id)
                    except Exception: pass

    entities = []
    for mac in coordinator.data:
        if mac in selected:
            entities.append(WyzeMotionSensor(coordinator, mac))
            
    async_add_entities(entities)

class WyzeMotionSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, mac):
        super().__init__(coordinator)
        self._mac = mac
        self._attr_name = "Motion"
        self._attr_icon = "mdi:motion-sensor"
        self._attr_unique_id = f"{mac}_motion"
        self._attr_has_entity_name = True

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
    def native_value(self):
        val = self.coordinator.data.get(self._mac, {}).get("motion_detected")
        return "Detected" if val else "Clear"