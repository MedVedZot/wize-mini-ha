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
PLATFORMS = [Platform.SENSOR, Platform.SWITCH]
CONF_INTERVAL, DEFAULT_INTERVAL = "update_interval", 3
CONF_KEY_ID, CONF_API_KEY = "key_id", "api_key"

class WyzeClient:
    def __init__(self, hass, config):
        self.hass, self._config, self._client = hass, config, None

    async def _ensure_client(self):
        if self._client is None:
            from .wyze_api import WyzeApiClient
            self._client = WyzeApiClient(async_get_clientsession(self.hass), 
                email=self._config[CONF_EMAIL], 
                password=self._config[CONF_PASSWORD], 
                key_id=self._config[CONF_KEY_ID], 
                api_key=self._config[CONF_API_KEY])
            await self._client.login()
        return self._client

    async def get_full_state(self):
        client = await self._ensure_client()
        # ОДИН запрос для получения базового списка
        devices = await client.get_devices()
        result = {}
        now = int(time.time() * 1000)

        for dev in devices:
            mac = dev.get("mac")
            if not mac: continue
            
            # Берем данные напрямую из объекта устройства (get_devices уже содержит это)
            p = dev.get("device_params", {})
            raw = dev.get("raw", {})
            
            # Для v4 Spotlight часто в P1056. Если в p нет, ищем в property_list (если есть)
            spotlight_val = p.get("floodlight_status") == 1 or p.get("power_switch") == 1
            
            result[mac] = {
                "mac": mac,
                "name": dev.get("nickname"),
                "product_model": dev.get("product_model"),
                "firmware": raw.get("firmware_ver") or dev.get("firmware_ver"),
                "local_ip": p.get("ipaddr") or dev.get("ip") or dev.get("local_ip"),
                "ssid": p.get("ssid") or dev.get("ssid"),
                "online": dev.get("conn_state") == 1,
                "motion_detected": False, # Обновим ниже
                "spotlight": spotlight_val
            }

        # ОДИН запрос событий для всех MAC сразу (минимум нагрузки)
        try:
            mac_list = list(result.keys())
            if mac_list:
                events = await client.get_event_list(mac_list, begin_time_ms=now-300000, count=20)
                for e in events:
                    eid = e.get("device_id")
                    if eid in result and e.get("event_value") == "13":
                        if (now - e.get("event_ts", 0)) < 40000:
                            result[eid]["motion_detected"] = True
        except Exception as err:
            _LOGGER.debug("Event fetch error: %s", err)

        return result

async def async_setup_entry(hass, entry):
    wyze_client = WyzeClient(hass, entry.data)
    
    async def async_update_data():
        try:
            data = await wyze_client.get_full_state()
            selected = entry.options.get("devices", [])
            if not selected: return data
            return {k: v for k, v in data.items() if k in selected}
        except Exception as err:
            if "429" in str(err): return coord.data
            raise UpdateFailed(f"API Error: {err}")

    coord = DataUpdateCoordinator(hass, _LOGGER, name=DOMAIN, 
        update_interval=timedelta(seconds=entry.options.get(CONF_INTERVAL, DEFAULT_INTERVAL)),
        update_method=async_update_data)
    
    coord.wyze_client = wyze_client
    await coord.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coord
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(lambda h, e: h.config_entries.async_reload(e.entry_id)))
    return True

async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)