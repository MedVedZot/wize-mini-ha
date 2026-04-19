"""Wyze Mini HA Integration."""
import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)
DOMAIN = "wyze_mini_ha"
PLATFORMS = [Platform.SENSOR]
CONF_INTERVAL = "update_interval"
CONF_KEY_ID = "key_id"
CONF_API_KEY = "api_key"
DEFAULT_INTERVAL = 3

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    config = {
        "email": entry.data[CONF_EMAIL],
        "password": entry.data[CONF_PASSWORD],
        "key_id": entry.data.get(CONF_KEY_ID),
        "api_key": entry.data.get(CONF_API_KEY)
    }
    interval = entry.options.get(CONF_INTERVAL, DEFAULT_INTERVAL)
    
    try:
        interval = int(interval)
    except (ValueError, TypeError):
        _LOGGER.warning("Invalid interval %s, using default %s", interval, DEFAULT_INTERVAL)
        interval = DEFAULT_INTERVAL
    
    if interval <= 0:
        _LOGGER.warning("Invalid interval %s, using default %s", interval, DEFAULT_INTERVAL)
        interval = DEFAULT_INTERVAL

    async def async_update_data():
        try:
            return await asyncio.to_thread(_fetch_data, config, entry.options.get("devices", []))
        except Exception as err:
            raise UpdateFailed(f"API Error: {err}") from err

    coord = DataUpdateCoordinator(hass, _LOGGER, name=DOMAIN, update_method=async_update_data, update_interval=timedelta(seconds=interval))
    await coord.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coord
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True

def _fetch_data(config: dict, selected_macs: list) -> dict:
    from .wyze_sync import WyzeClient
    devices = WyzeClient(config).get_full_state()
    if not devices:
        return {}
    if not selected_macs:
        return devices
    return {k: v for k, v in devices.items() if k in selected_macs}

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        if DOMAIN in hass.data:
            hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok