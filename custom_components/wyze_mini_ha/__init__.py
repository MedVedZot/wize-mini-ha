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
CONF_INTERVAL = "update_interval"
CONF_KEY_ID = "key_id"
CONF_API_KEY = "api_key"
DEFAULT_INTERVAL = 3

class WyzeClient:
    def __init__(self, hass, config):
        self.hass = hass
        self._config = config
        self._client = None
        self._seen_events = set()

    async def _ensure_client(self):
        if self._client is None:
            from .wyze_api import WyzeApiClient
            self._client = WyzeApiClient(
                async_get_clientsession(self.hass),
                email=self._config["email"],
                password=self._config["password"],
                key_id=self._config["key_id"],
                api_key=self._config["api_key"]
            )
            await self._client.login()
        return self._client

    async def get_full_state(self):
        client = await self._ensure_client()
        devices_list = await client.get_devices()
        result = {}

        for dev in devices_list:
            mac = dev.get("mac")
            model = dev.get("product_model")
            if not mac: continue

            info = await client.get_device_info(mac, model)
            props = {p["pid"]: p["value"] for p in info.get("property_list", [])}
            
            motion = False
            try:
                now = int(time.time() * 1000)
                evts = await client.get_event_list([mac], begin_time_ms=now-300000, end_time_ms=now+60000, count=5)
                if evts:
                    latest_evt = evts[0]
                    if (now - latest_evt.get("event_ts", 0)) < 30000 and latest_evt.get("event_value") == "13":
                        motion = True
            except Exception: pass

            result[mac] = {
                "mac": mac,
                "name": info.get("nickname"),
                "product_model": model,
                "firmware": info.get("firmware_ver"),
                "local_ip": info.get("ip"),
                "ssid": info.get("ssid"),
                "online": info.get("dtls") == 1,
                "motion_detected": motion,
                "spotlight": props.get("P1056") == "1"
            }
        return result

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = WyzeClient(hass, entry.data)
    interval = max(int(entry.options.get(CONF_INTERVAL, DEFAULT_INTERVAL)), 1)

    async def async_update_data():
        try:
            selected = entry.options.get("devices", [])
            devices = await client.get_full_state()
            if not selected: return devices
            return {k: v for k, v in devices.items() if k in selected}
        except Exception as err:
            if "429" in str(err): return coord.data
            raise UpdateFailed(f"Error: {err}")

    coord = DataUpdateCoordinator(hass, _LOGGER, name=DOMAIN, update_method=async_update_data, update_interval=timedelta(seconds=interval))
    coord.wyze_client = client
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coord
    await coord.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)