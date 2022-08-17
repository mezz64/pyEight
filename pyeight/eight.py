"""
pyeight.eight
~~~~~~~~~~~~~~~~~~~~
Provides api for Eight Sleep
Copyright (c) 2017-2022 John Mihalic <https://github.com/mezz64>
Licensed under the MIT license.

"""
from __future__ import annotations

import asyncio
import atexit
from datetime import datetime
import logging
from typing import Any

from aiohttp.client import ClientError, ClientSession, ClientTimeout

from .constants import (
    API_URL,
    DATE_TIME_ISO_FORMAT,
    DEFAULT_HEADERS,
    DEFAULT_TIMEOUT,
    __version__,
)
from .exceptions import NotAuthenticatedError, RequestError
from .user import EightUser

_LOGGER = logging.getLogger(__name__)

CLIENT_TIMEOUT = ClientTimeout(total=DEFAULT_TIMEOUT)


class EightSleep:
    """Eight sleep API object."""

    def __init__(
        self,
        email: str,
        password: str,
        timezone: str,
        auth_data: dict[str, str] | None = None,
        client_session: ClientSession | None = None,
    ) -> None:
        """Initialize eight sleep class."""
        self._email = email
        self._password = password

        self.timezone = timezone

        self.users: dict[str, EightUser] = {}

        self._user_id: str | None = None
        self._token: str | None = None
        self._token_expiration: datetime | None = None
        self._device_ids: list[str] = []
        self._is_pod: bool = False

        # Setup 10 element list
        self._device_json_list: list[dict] = []

        self._api_session = client_session
        self._internal_session: bool = False

        if auth_data is not None:
            self._configure_auth(auth_data)

        # Stop on exit
        atexit.register(self.at_exit)

    def at_exit(self) -> None:
        """Run at exit."""
        try:
            loop = asyncio.get_running_loop()
            asyncio.run_coroutine_threadsafe(self.stop(), loop).result()
        except RuntimeError:
            asyncio.run(self.stop())

    @property
    def token(self) -> str | None:
        """Return session token."""
        return self._token

    @property
    def user_id(self) -> str | None:
        """Return user ID of the logged in user."""
        return self._user_id

    @property
    def device_id(self) -> str | None:
        """Return devices id."""
        return self._device_ids[0]

    @property
    def device_data(self) -> dict:
        """Return current raw device_data json."""
        return self._device_json_list[0]

    @property
    def device_data_history(self) -> list[dict]:
        """Return full raw device_data json list."""
        return self._device_json_list

    @property
    def is_pod(self) -> bool:
        """Return if device is a POD."""
        return self._is_pod

    @property
    def _new_token_needed(self) -> bool:
        """Return if token needs to be refetcheed."""
        return (
            not self._token_expiration
            or (self._token_expiration - datetime.now()).total_seconds() < 3600
        )

    def _configure_auth(self, auth_data: dict[str, str]) -> None:
        """Configure auth data."""
        self._user_id = auth_data["userId"]
        self._token = auth_data["token"]
        self._token_expiration = datetime.strptime(
            auth_data["expirationDate"], DATE_TIME_ISO_FORMAT
        )

    def fetch_user_id(self, side: str) -> str | None:
        """Return the user_id for the specified bed side."""
        return next(
            (user_id for user_id, user in self.users.items() if user.side == side),
            None,
        )

    async def update_user_data(self) -> None:
        """Update data for users."""
        for obj in self.users.values():
            await obj.update_user()

    async def start(self) -> bool:
        """Start api initialization."""
        _LOGGER.debug("Initializing pyEight Version: %s", __version__)
        if not self._api_session:
            self._api_session = ClientSession()
            self._internal_session = True

        if not self._token or self._new_token_needed:
            await self.fetch_token()
        if self._token is not None:
            await self.fetch_device_list()
            await self.assign_users()
            return True
        # We couldn't authenticate
        return False

    async def stop(self) -> None:
        """Stop api session."""
        if self._internal_session and self._api_session:
            _LOGGER.debug("Closing eight sleep api session.")
            await self._api_session.close()
            self._api_session = None
        elif self._internal_session:
            _LOGGER.debug("No-op because session hasn't been created")
        else:
            _LOGGER.debug("No-op because session is being managed outside of pyEight")

    async def fetch_token(self) -> dict[str, str]:
        """Fetch new session token from api."""
        url = f"{API_URL}/login"
        payload = {"email": self._email, "password": self._password}

        reg = await self.api_request("post", url, data=payload, include_token=False)
        self._configure_auth(reg["session"])
        _LOGGER.debug("UserID: %s, Token: %s", self._user_id, self.token)
        return reg["session"]

    async def fetch_device_list(self) -> None:
        """Fetch list of devices."""
        url = f"{API_URL}/users/me"

        dlist = await self.api_request("get", url)
        self._device_ids = dlist["user"]["devices"]

        if "cooling" in dlist["user"]["features"]:
            self._is_pod = True

        _LOGGER.debug("Devices: %s, POD: %s", self._device_ids, self._is_pod)

    async def assign_users(self) -> None:
        """Update device properties."""
        device_id = self._device_ids[0]
        url = f"{API_URL}/devices/{device_id}?filter=ownerId,leftUserId,rightUserId"

        data = await self.api_request("get", url)
        # Populate users
        for side in ("left", "right"):
            user_id = data["result"].get(f"{side}UserId")
            if user_id is not None and user_id not in self.users:
                user = self.users[user_id] = EightUser(self, user_id, side)
                await user.update_user_profile()

    @property
    def room_temperature(self) -> float | None:
        """Return room temperature for both sides of bed."""
        # Check which side is active, if both are return the average
        tmp = None
        tmp2 = None
        for user in self.users.values():
            if user.current_values["processing"]:
                if tmp is None:
                    tmp = user.current_values["room_temp"]
                else:
                    tmp = (tmp + user.current_values["room_temp"]) / 2
            else:
                if tmp2 is None:
                    tmp2 = user.current_values["room_temp"]
                else:
                    tmp2 = (tmp2 + user.current_values["room_temp"]) / 2

        if tmp is not None:
            return tmp

        # If tmp2 is None we will just return None
        return tmp2

    def handle_device_json(self, data: dict[str, Any]) -> None:
        """Manage the device json list."""
        self._device_json_list = [data, *self._device_json_list][:10]

    async def update_device_data(self) -> None:
        """Update device data json."""
        url = f"{API_URL}/devices/{self.device_id}"

        # Check for access token expiration (every 15days)
        if self._new_token_needed:
            _LOGGER.debug("Fetching new access token before expiration.")
            await self.fetch_token()

        device_resp = await self.api_request("get", url)
        # Want to keep last 10 readings so purge the last after we add
        self.handle_device_json(device_resp["result"])
        for obj in self.users.values():
            obj.dynamic_presence()

    async def api_request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        include_token: bool = True,
    ) -> Any:
        """Make api request."""
        resp = None
        headers = DEFAULT_HEADERS.copy()

        # Only attempt to add the token if we've already retrieved it and if the caller
        # wants us to
        if include_token:
            if not self._token:
                raise NotAuthenticatedError
            headers.update({"Session-Token": self._token})
        try:
            assert self._api_session
            resp = await self._api_session.request(
                method,
                url,
                headers=headers,
                params=params,
                json=data,
                timeout=CLIENT_TIMEOUT,
                raise_for_status=True,
            )
            return await resp.json()

        except (ClientError, asyncio.TimeoutError, ConnectionRefusedError) as err:
            _LOGGER.error("Error %sing Eight data. %s", method, err)
            raise RequestError from err
