import logging
import asyncio
import time
from datetime import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)
DOMAIN = "wyze_mini_ha"
PLATFORMS = [Platform.SENSOR]
CONF_INTERVAL, DEFAULT_INTERVAL = "update_interval", 3
CONF_KEY_ID, CONF_API_KEY = "key_id", "api_key"

class WyzeClient:
    def __init__(self, hass, config):
        self.hass = hass
        self._config = config
        self._client = None
        self._info_cache = {}

    async def _ensure_client(self):
        if self._client is None:
            from .wyze_api import WyzeApiClient
            self._client = WyzeApiClient(
                async_get_clientsession(self.hass),
                email=self._config[CONF_EMAIL],
                password=self._config[CONF_PASSWORD],
                key_id=self._config[CONF_KEY_ID],
                api_key=self._config[CONF_API_KEY]
            )
            await self._client.login()
        return self._client

    async def get_full_state(self):
        client = await self._ensure_client()
        devices = await client.get_devices()
        result = {}
        now_ms = int(time.time() * 1000)
        
        all_macs = [d.get("mac") for d in devices if d.get("mac")]
        events = []
        if all_macs:
            try:
                events = await client.get_event_list(all_macs, begin_time_ms=now_ms-10000, count=20)
            except: pass

        for dev in devices:
            mac = dev.get("mac")
            model = dev.get("product_model")
            if not mac: continue
            
            if mac not in self._info_cache:
                try:
                    info = await client.get_device_info(mac, model)
                    self._info_cache[mac] = info.get("firmware_ver", "Unknown")
                except:
                    self._info_cache[mac] = "Unknown"

            motion = any(e.get("device_id") == mac and e.get("event_value") == "13" for e in events)

            result[mac] = {
                "mac": mac,
                "name": dev.get("nickname"),
                "product_model": model,
                "firmware": self._info_cache[mac],
                "motion_detected": motion
            }
        return result

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = WyzeClient(hass, entry.data)
    
    async def async_update_data():
        try:
            selected = entry.options.get("devices", [])
            data = await client.get_full_state()
            if not selected: return data
            return {k: v for k, v in data.items() if k in selected}
        except Exception as err:
            raise UpdateFailed(f"API Error: {err}")

    coord = DataUpdateCoordinator(
        hass, _LOGGER, name=DOMAIN, 
        update_method=async_update_data, 
        update_interval=timedelta(seconds=entry.options.get(CONF_INTERVAL, DEFAULT_INTERVAL))
    )
    coord.wyze_client = client
    
    await coord.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coord
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(lambda h, e: h.config_entries.async_reload(e.entry_id)))
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok