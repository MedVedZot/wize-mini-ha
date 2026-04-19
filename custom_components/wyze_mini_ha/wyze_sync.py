"""Synchronous wrapper for WyzeApiClient."""
import asyncio
import sys
import os
import logging
import weakref

_LOGGER = logging.getLogger(__name__)

_sessions = weakref.WeakSet()

class WyzeClient:
    def __init__(self, config):
        self._config = config
        self._session = None
        self._client = None
        self._loop = None

    def _get_loop(self):
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop

    def _ensure_client(self):
        if self._client is None:
            from .wyze_api import WyzeApiClient
            import aiohttp
            
            async def _create():
                self._session = aiohttp.ClientSession()
                _sessions.add(self._session)
                self._client = WyzeApiClient(
                    self._session,
                    email=self._config["email"],
                    password=self._config["password"],
                    key_id=self._config["key_id"],
                    api_key=self._config["api_key"]
                )
                await self._client.login()
            
            loop = self._get_loop()
            try:
                loop.run_until_complete(_create())
            except Exception as e:
                if self._session and not self._session.closed:
                    loop.run_until_complete(self._session.close())
                raise
        
        return self._client

    def get_full_state(self):
        _LOGGER.debug("get_full_state called")
        client = self._ensure_client()
        
        async def _get():
            devices = await client.get_devices()
            _LOGGER.debug("API returned %d devices", len(devices))
            result = {}
            for dev in devices:
                mac = dev.get("mac")
                if not mac:
                    _LOGGER.warning("Device without MAC: %s", dev)
                    continue
                _LOGGER.debug("Processing device MAC: %s, Name: %s", mac, dev.get("nickname"))
                result[mac] = {
                    "device_id": mac,
                    "name": dev.get("nickname"),
                    "product_model": dev.get("product_model"),
                    "local_ip": dev.get("device_params", {}).get("ipaddr"),
                    "mac": mac,
                    "motion_detected": False
                }
            _LOGGER.info("Returning %d devices with MACs: %s", len(result), list(result.keys()))
            return result
        
        loop = self._get_loop()
        try:
            return loop.run_until_complete(_get())
        finally:
            self._cleanup()

    def close(self):
        self._cleanup()

    def _cleanup(self):
        if self._session and not self._session.closed:
            async def _close():
                try:
                    await self._session.close()
                except Exception as e:
                    _LOGGER.error("Error closing session: %s", e)
            loop = self._get_loop()
            try:
                loop.run_until_complete(_close())
            except Exception as e:
                _LOGGER.error("Error in cleanup: %s", e)
            finally:
                self._session = None
                self._client = None
