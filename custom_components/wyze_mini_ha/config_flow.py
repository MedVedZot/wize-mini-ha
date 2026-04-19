"""Config flow for Wyze Mini HA."""
import asyncio
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import AbortFlow

from . import CONF_INTERVAL, DEFAULT_INTERVAL, DOMAIN, CONF_KEY_ID, CONF_API_KEY

_LOGGER = logging.getLogger(__name__)

def _get_client(data):
    from .wyze_sync import WyzeClient
    return WyzeClient(data)

async def validate_auth(data):
    def _validate():
        try:
            return _get_client(data).get_full_state()
        except Exception as err:
            _LOGGER.error("Auth validation error: %s", err)
            raise
    return await asyncio.to_thread(_validate)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input:
            try:
                devices = await validate_auth(user_input)
                if not devices:
                    errors["base"] = "no_devices"
                else:
                    await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
                    self._abort_if_unique_id_configured()
                    self._data = user_input
                    return await self.async_step_devices()
            except AbortFlow:
                raise
            except Exception as err:
                _LOGGER.error("User step error: %s", err)
                if "401" in str(err) or "unauthorized" in str(err).lower():
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_KEY_ID): str,
                vol.Required(CONF_API_KEY): str
            }),
            errors=errors
        )

    async def async_step_reconfigure(self, user_input=None):
        errors = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if user_input:
            try:
                await validate_auth(user_input)
                return self.async_update_reload_and_abort(entry, data={**entry.data, **user_input})
            except AbortFlow:
                raise
            except Exception as err:
                _LOGGER.error("Reconfigure error: %s", err)
                if "401" in str(err) or "unauthorized" in str(err).lower():
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL, default=entry.data[CONF_EMAIL]): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_KEY_ID, default=entry.data[CONF_KEY_ID]): str,
                vol.Required(CONF_API_KEY, default=entry.data[CONF_API_KEY]): str
            }),
            errors=errors
        )

    async def async_step_devices(self, user_input=None):
        errors = {}
        try:
            states = await asyncio.to_thread(lambda: _get_client(self._data).get_full_state())
        except Exception as err:
            _LOGGER.error("Devices step error: %s", err)
            states = {}

        if user_input is not None:
            selected = []
            for k, v in user_input.items():
                if v:
                    if "(" in k:
                        device_key = k.split(" (")[0]
                    else:
                        device_key = k
                    selected.append(device_key)
            
            if not selected:
                errors["base"] = "no_devices_selected"
            else:
                return self.async_create_entry(
                    title=self._data[CONF_EMAIL],
                    data=self._data,
                    options={"devices": selected, CONF_INTERVAL: DEFAULT_INTERVAL}
                )

        schema_dict = {}
        for mac, data in sorted(states.items()):
            name = data.get("name", mac)
            model = data.get("product_model", "")
            label = f"{name} ({model})"
            schema_dict[vol.Optional(label, default=False)] = bool

        return self.async_show_form(step_id="devices", data_schema=vol.Schema(schema_dict), errors=errors)

class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, entry):
        self.entry = entry

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            new_data = dict(self.entry.data)
            new_options = dict(self.entry.options)
            
            pwd = user_input.get(CONF_PASSWORD) or self.entry.data[CONF_PASSWORD]
            key_id = user_input.get(CONF_KEY_ID) or self.entry.data.get(CONF_KEY_ID)
            api_key = user_input.get(CONF_API_KEY) or self.entry.data.get(CONF_API_KEY)
            
            check_data = {
                CONF_EMAIL: self.entry.data[CONF_EMAIL],
                CONF_PASSWORD: pwd,
                CONF_KEY_ID: key_id,
                CONF_API_KEY: api_key
            }
            
            selected = []
            for k, v in user_input.items():
                if v and k not in {CONF_PASSWORD, CONF_KEY_ID, CONF_API_KEY, CONF_INTERVAL}:
                    if "(" in k:
                        device_key = k.split(" (")[0]
                    else:
                        device_key = k
                    selected.append(device_key)
            
            if not selected:
                errors["base"] = "no_devices_selected"
            else:
                try:
                    await validate_auth(check_data)
                    if user_input.get(CONF_PASSWORD):
                        new_data[CONF_PASSWORD] = user_input.pop(CONF_PASSWORD)
                    else:
                        user_input.pop(CONF_PASSWORD, None)
                    
                    if user_input.get(CONF_KEY_ID):
                        new_data[CONF_KEY_ID] = user_input.pop(CONF_KEY_ID)
                    else:
                        user_input.pop(CONF_KEY_ID, None)
                    
                    if user_input.get(CONF_API_KEY):
                        new_data[CONF_API_KEY] = user_input.pop(CONF_API_KEY)
                    else:
                        user_input.pop(CONF_API_KEY, None)

                    new_options[CONF_INTERVAL] = user_input.pop(CONF_INTERVAL)
                    new_options["devices"] = selected

                    self.hass.config_entries.async_update_entry(self.entry, data=new_data)
                    return self.async_create_entry(title="", data=new_options)
                except Exception as err:
                    _LOGGER.error("Options init error: %s", err)
                    if "401" in str(err) or "unauthorized" in str(err).lower():
                        errors["base"] = "invalid_auth"
                    else:
                        errors["base"] = "cannot_connect"

        coordinator = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id)
        current_devices = self.entry.options.get("devices", [])
        current_interval = self.entry.options.get(CONF_INTERVAL, DEFAULT_INTERVAL)

        schema_dict = {
            vol.Optional(CONF_PASSWORD): str,
            vol.Optional(CONF_KEY_ID): str,
            vol.Optional(CONF_API_KEY): str,
            vol.Required(CONF_INTERVAL, default=current_interval): cv.positive_int,
        }

        display_devices = {}
        try:
            if coordinator and hasattr(coordinator, 'data') and coordinator.data:
                display_devices = coordinator.data
        except Exception as err:
            _LOGGER.error("Error getting devices for options: %s", err)
            display_devices = {}

        for mac, data in sorted(display_devices.items()):
            name = data.get("name", mac)
            model = data.get("product_model", "")
            label = f"{name} ({model})"
            schema_dict[vol.Optional(label, default=mac in current_devices)] = bool

        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema_dict), errors=errors)