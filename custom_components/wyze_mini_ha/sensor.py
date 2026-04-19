"""Wyze Mini HA Sensors."""
import logging
import re

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEVICE_INFO_FIELDS = {"mac", "name", "product_model", "local_ip"}

async def async_setup_entry(hass, entry, async_add_entities):
    _LOGGER.info("Setting up sensors for entry %s", entry.entry_id)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    selected = entry.options.get("devices", [])
    _LOGGER.debug("Selected devices from options: %s", selected)
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    existing_entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    
    for ent in existing_entries:
        if ent.unique_id and ent.unique_id.endswith("_motion"):
            mac = ent.unique_id.replace("_motion", "")
            if mac not in selected:
                entity_registry.async_remove(ent.entity_id)

    for mac, data in coordinator.data.items():
        name = data.get("name")
        if not name:
            continue

        device = device_registry.async_get_device(identifiers={(DOMAIN, mac)})
        if device and device.name != name:
            device_registry.async_update_device(device.id, name=name)

        if not device:
            continue

        new_prefix = slugify(name) or ""
        if not new_prefix:
            _LOGGER.debug("Skipping device %s: empty slugified name", mac)
            continue
            
        entity_entries = er.async_entries_for_device(entity_registry, device.id, include_disabled_entities=True)

        for entity_entry in entity_entries:
            if entity_entry.domain != "sensor":
                continue
            if not entity_entry.unique_id:
                continue

            if not entity_entry.unique_id.endswith("_motion"):
                continue
            
            expected_entity_id = f"sensor.{new_prefix}_motion"
            
            if entity_entry.entity_id == expected_entity_id:
                continue
            if entity_registry.async_is_registered(expected_entity_id):
                continue

            try:
                entity_registry.async_update_entity(entity_entry.entity_id, new_entity_id=expected_entity_id)
            except ValueError as e:
                _LOGGER.debug("Could not update entity ID %s to %s: %s", entity_entry.entity_id, expected_entity_id, e)

    _LOGGER.debug("Coordinator data has %d devices", len(coordinator.data))
    entities = []
    for mac, device_data in coordinator.data.items():
        _LOGGER.debug("Processing device MAC: %s, Selected: %s", mac, mac in selected)
        if mac in selected:
            entities.append(WyzeMotionSensor(coordinator, mac))
    _LOGGER.info("Creating %d motion sensors", len(entities))
    async_add_entities(entities)

class WyzeMotionSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, mac):
        super().__init__(coordinator)
        self._mac = mac
        device_data = coordinator.data.get(mac, {})
        self._attr_unique_id = f"{mac}_motion"
        self._attr_native_unit_of_measurement = None
        self._attr_state_class = None
        self._attr_icon = "mdi:motion-sensor"
        self._attr_has_entity_name = True

    @property
    def name(self):
        return "Motion"

    @property
    def device_info(self):
        data = self.coordinator.data.get(self._mac, {})
        return DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=data.get("name"),
            manufacturer="Wyze",
            model=str(data.get("product_model")),
            serial_number=data.get("mac"),
        )

    @property
    def native_value(self):
        device_data = self.coordinator.data.get(self._mac, {})
        return device_data.get("motion_detected")