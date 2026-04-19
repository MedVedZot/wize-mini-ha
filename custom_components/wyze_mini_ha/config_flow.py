import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import AbortFlow

from . import CONF_INTERVAL, DEFAULT_INTERVAL, DOMAIN, CONF_KEY_ID, CONF_API_KEY, WyzeClient

_LOGGER = logging.getLogger(__name__)

async def validate_auth(hass, data):
    client = WyzeClient(hass, data)
    try:
        return await client.get_full_state()
    except Exception as err:
        _LOGGER.error("Auth validation error: %s", err)
        raise

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input:
            try:
                await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
                self._abort_if_unique_id_configured()

                _LOGGER.info("Validating auth for email: %s", user_input[CONF_EMAIL])
                devices = await validate_auth(self.hass, user_input)
                
                if not devices:
                    errors["base"] = "no_devices"
                else:
                    self._data = user_input
                    return await self.async_step_devices()
            except AbortFlow:
                raise
            except Exception as err:
                _LOGGER.error("User step error: %s", err)
                errors["base"] = "invalid_auth" if "401" in str(err) else "cannot_connect"
        
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

    async def async_step_devices(self, user_input=None):
        errors = {}
        client = WyzeClient(self.hass, self._data)
        try:
            states = await client.get_full_state()
        except Exception:
            states = {}

        if user_input is not None:
            label_to_mac = {f"{d.get('name', m)} ({d.get('product_model', '')})": m for m, d in states.items()}
            selected = [label_to_mac[k] for k, v in user_input.items() if v and k in label_to_mac]
            
            if not selected:
                errors["base"] = "no_devices_selected"
            else:
                return self.async_create_entry(
                    title=self._data[CONF_EMAIL],
                    data=self._data,
                    options={"devices": selected, CONF_INTERVAL: DEFAULT_INTERVAL}
                )

        schema_dict = {vol.Optional(f"{d.get('name', m)} ({d.get('product_model', '')})", default=True): bool for m, d in sorted(states.items())}
        return self.async_show_form(step_id="devices", data_schema=vol.Schema(schema_dict), errors=errors)

class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, entry):
        self.entry = entry

    async def async_step_init(self, user_input=None):
        errors = {}
        client = WyzeClient(self.hass, self.entry.data)
        try:
            display_devices = await client.get_full_state()
        except Exception as err:
            _LOGGER.error("Error updating devices in options: %s", err)
            display_devices = {}

        current_devices = self.entry.options.get("devices", [])
        current_interval = self.entry.options.get(CONF_INTERVAL, DEFAULT_INTERVAL)

        if user_input is not None:
            new_data = dict(self.entry.data)
            new_options = dict(self.entry.options)
            
            for key in [CONF_PASSWORD, CONF_KEY_ID, CONF_API_KEY]:
                if val := user_input.get(key):
                    if val.strip():
                        new_data[key] = val.strip()

            new_options[CONF_INTERVAL] = user_input.get(CONF_INTERVAL, current_interval)
            
            label_to_mac = {f"{d.get('name', m)} ({d.get('product_model', '')})": m for m, d in display_devices.items()}
            selected = [label_to_mac[k] for k, v in user_input.items() if v and k in label_to_mac]

            if not selected and display_devices:
                errors["base"] = "no_devices_selected"
            else:
                self.hass.config_entries.async_update_entry(self.entry, data=new_data)
                new_options["devices"] = selected
                return self.async_create_entry(title="", data=new_options)

        schema = {
            vol.Optional(CONF_PASSWORD): str,
            vol.Optional(CONF_KEY_ID): str,
            vol.Optional(CONF_API_KEY): str,
            vol.Required(CONF_INTERVAL, default=current_interval): cv.positive_int,
        }
        
        for mac, data in sorted(display_devices.items()):
            label = f"{data.get('name', mac)} ({data.get('product_model', '')})"
            # Показываем галочку, если мак уже был сохранен ранее
            schema[vol.Optional(label, default=mac in current_devices)] = bool

        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema), errors=errors)