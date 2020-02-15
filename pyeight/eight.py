"""
pyeight.eight
~~~~~~~~~~~~~~~~~~~~
Provides api for Eight Sleep
Copyright (c) 2017-2020 John Mihalic <https://github.com/mezz64>
Licensed under the MIT license.

"""

import logging
import asyncio
from datetime import datetime
import time
import aiohttp
import async_timeout

from pyeight.user import EightUser
from pyeight.constants import (
    DEFAULT_TIMEOUT, DEFAULT_HEADERS, API_URL, __version__)

_LOGGER = logging.getLogger(__name__)


class EightSleep(object):
    """Eight sleep API object."""
    def __init__(self, email, password, tzone, partner=False, api_key=None,
                 loop=None):
        """Initialize eight sleep class."""
        self._email = email
        self._password = password
        self._partner = partner
        self._api_key = api_key

        self.tzone = tzone

        self.users = {}

        self._userid = None
        self._token = None
        self._expdate = None
        self._devices = None
        self._pod = False

        # Setup 10 element list
        self._device_json = [None, None, None, None, None,
                             None, None, None, None, None]

        if loop is None:
            _LOGGER.info("Must supply asyncio loop.  Quitting")
            return None
        else:
            self._event_loop = loop
            self._own_loop = False

        asyncio.set_event_loop(self._event_loop)

        self._api_session = aiohttp.ClientSession(
            headers=DEFAULT_HEADERS, loop=self._event_loop)

    @property
    def token(self):
        """Return session token."""
        return self._token

    @property
    def userids(self):
        """Return dict of user ids."""
        return self._userid

    @property
    def deviceid(self):
        """Return devices id."""
        return self._devices[0]

    @property
    def device_data(self):
        """Return current raw device_data json."""
        return self._device_json[0]

    @property
    def device_data_history(self):
        """Return full raw device_data json list."""
        return self._device_json

    @property
    def is_pod(self):
        """Return if device is a POD."""
        return self._pod

    def fetch_userid(self, side):
        """Return the userid for the specified bed side."""
        for user in self.users:
            obj = self.users[user]
            if obj.side == side:
                return user

    async def update_user_data(self):
        """Update data for users."""
        for user in self.users:
            await self.users[user].update_user()

    async def start(self):
        """Start api initialization."""
        _LOGGER.debug('Initializing pyEight Version: %s', __version__)
        await self.fetch_token()
        if self._token is not None:
            await self.fetch_device_list()
            await self.assign_users()
            return True
        else:
            # We couldn't authenticate
            return False

    async def stop(self):
        """Stop api session."""
        _LOGGER.debug('Closing eight sleep api session.')
        await self._api_session.close()

    async def fetch_token(self):
        """Fetch new session token from api."""
        url = '{}/login'.format(API_URL)
        payload = 'email={}&password={}'.format(self._email, self._password)

        reg = await self.api_post(url, None, payload)
        if reg is None:
            _LOGGER.error('Unable to authenticate and fetch eight token.')
        else:
            self._userid = reg['session']['userId']
            self._token = reg['session']['token']
            self._expdate = reg['session']['expirationDate']
            _LOGGER.debug('UserID: %s, Token: %s', self._userid, self.token)

    async def fetch_device_list(self):
        """Fetch list of devices."""
        url = '{}/users/me'.format(API_URL)

        dlist = await self.api_get(url)
        if dlist is None:
            _LOGGER.error('Unable to fetch eight devices.')
        else:
            self._devices = dlist['user']['devices']

            if 'cooling' in dlist['user']['features']:
                self._pod = True

            _LOGGER.debug('Devices: %s, POD: %s', self._devices, self._pod)

    async def assign_users(self):
        """Update device properties."""
        device = self._devices[0]
        url = '{}/devices/{}?filter=ownerId,leftUserId,rightUserId' \
            .format(API_URL, device)

        data = await self.api_get(url)
        if data is None:
            _LOGGER.error('Unable to assign eight device users.')
        else:
            # Find the side to the known userid
            if data['result']['rightUserId'] == self._userid:
                self.users[data['result']['rightUserId']] = \
                    EightUser(self, data['result']['rightUserId'], 'right')
                user_side = 'right'
            elif data['result']['leftUserId'] == self._userid:
                self.users[data['result']['leftUserId']] = \
                    EightUser(self, data['result']['leftUserId'], 'left')
                user_side = 'left'
            else:
                _LOGGER.error('Unable to assign eight device users.')

            if self._partner:
                if user_side == 'right':
                    self.users[data['result']['leftUserId']] = \
                        EightUser(self, data['result']['leftUserId'], 'left')
                else:
                    self.users[data['result']['rightUserId']] = \
                        EightUser(self, data['result']['rightUserId'], 'right')

    def room_temperature(self):
        """Return room temperature for both sides of bed."""
        # Check which side is active, if both are return the average
        tmp = None
        tmp2 = None
        for user in self.users:
            obj = self.users[user]
            if obj.current_values['processing']:
                if tmp is None:
                    tmp = obj.current_values['room_temp']
                else:
                    tmp = (tmp + obj.current_values['room_temp']) / 2
            else:
                if tmp2 is None:
                    tmp2 = obj.current_values['room_temp']
                else:
                    tmp2 = (tmp2 + obj.current_values['room_temp']) / 2

        if tmp is not None:
            return tmp
        elif tmp2 is not None:
            return tmp2

    def handle_device_json(self, data):
        """Manage the device json list."""
        self._device_json.insert(0, data)
        self._device_json.pop()

    async def update_device_data(self):
        """Update device data json."""
        url = '{}/devices/{}?offlineView=true'.format(API_URL, self.deviceid)

        # Check for access token expiration (every 15days)
        exp_delta = datetime.strptime(self._expdate, '%Y-%m-%dT%H:%M:%S.%fZ') \
            - datetime.fromtimestamp(time.time())
        # Renew 1hr before expiration
        if exp_delta.total_seconds() < 3600:
            _LOGGER.debug('Fetching new access token before expiration.')
            await self.fetch_token()

        device_resp = await self.api_get(url)
        if device_resp is None:
            _LOGGER.error('Unable to fetch eight device data.')
        else:
            # Want to keep last 10 readings so purge the last after we add
            self.handle_device_json(device_resp['result'])
            for user in self.users:
                self.users[user].dynamic_presence()

    async def api_post(self, url, params=None, data=None):
        """Make api post request."""
        post = None
        try:
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self._event_loop):
                post = await self._api_session.post(
                    url, params=params, data=data)
            if post.status != 200:
                _LOGGER.error('Error posting Eight data: %s', post.status)
                return None

            if 'application/json' in post.headers['content-type']:
                post_result = await post.json()
            else:
                _LOGGER.debug('Response was not JSON, returning text.')
                post_result = await post.text()

            return post_result

        except (aiohttp.ClientError, asyncio.TimeoutError,
                ConnectionRefusedError) as err:
            _LOGGER.error('Error posting Eight data. %s', err)
            return None

    async def api_get(self, url, params=None):
        """Make api fetch request."""
        request = None
        headers = DEFAULT_HEADERS.copy()
        headers.update({'Session-Token': self._token})

        try:
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self._event_loop):
                request = await self._api_session.get(
                    url, headers=headers, params=params)
            # _LOGGER.debug('Get URL: %s', request.url)
            if request.status != 200:
                _LOGGER.error('Error fetching Eight data: %s', request.status)
                return None

            if 'application/json' in request.headers['content-type']:
                request_json = await request.json()
            else:
                _LOGGER.debug('Response was not JSON, returning text.')
                request_json = await request.text()

            return request_json

        except (aiohttp.ClientError, asyncio.TimeoutError,
                ConnectionRefusedError) as err:
            _LOGGER.error('Error fetching Eight data. %s', err)
            return None

    async def api_put(self, url, data=None):
        """Make api post request."""
        put = None
        headers = DEFAULT_HEADERS.copy()
        headers.update({'Session-Token': self._token})

        try:
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self._event_loop):
                put = await self._api_session.put(
                    url, headers=headers, data=data)
            if put.status != 200:
                _LOGGER.error('Error putting Eight data: %s', put.status)
                return None

            if 'application/json' in put.headers['content-type']:
                put_result = await put.json()
            else:
                _LOGGER.debug('Response was not JSON, returning text.')
                put_result = await put.text()

            return put_result

        except (aiohttp.ClientError, asyncio.TimeoutError,
                ConnectionRefusedError) as err:
            _LOGGER.error('Error putting Eight data. %s', err)
            return None
