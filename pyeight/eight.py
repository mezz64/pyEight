"""
pyeight.eight
~~~~~~~~~~~~~~~~~~~~
Provides api for Eight Sleep
Copyright (c) 2017 John Mihalic <https://github.com/mezz64>
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
    DEFAULT_TIMEOUT, DEFAULT_HEADERS, API_URL)

_LOGGER = logging.getLogger(__name__)

# pylint: disable=invalid-name,no-member
try:
    ensure_future = asyncio.ensure_future
except AttributeError:
    # Python 3.4.3 and earlier has this as async
    ensure_future = asyncio.async


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
        return self._userids

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

    def fetch_userid(self, side):
        """Return the userid for the specified bed side."""
        for user in self.users:
            obj = self.users[user]
            if obj.side == side:
                return user

    @asyncio.coroutine
    def update_user_data(self):
        """Update data for users."""
        for user in self.users:
            yield from self.users[user].update_user()

    @asyncio.coroutine
    def start(self):
        """Start api initialization."""
        yield from self.fetch_token()
        if self._token is not None:
            yield from self.fetch_device_list()
            yield from self.assign_users()
            return True
        else:
            # We couldn't authenticate
            return False

    @asyncio.coroutine
    def stop(self):
        """Stop api session."""
        _LOGGER.debug('Closing eight sleep api session.')
        yield from self._api_session.close()

    @asyncio.coroutine
    def fetch_token(self):
        """Fetch new session token from api."""
        url = '{}/login'.format(API_URL)
        payload = 'email={}&password={}'.format(self._email, self._password)

        reg = yield from self.api_post(url, None, payload)
        if reg is None:
            _LOGGER.error('Unable to authenticate and fetch eight token.')
        else:
            self._userid = reg['session']['userId']
            self._token = reg['session']['token']
            self._expdate = reg['session']['expirationDate']
            _LOGGER.debug('UserID: %s, Token: %s', self._userid, self.token)

    @asyncio.coroutine
    def fetch_device_list(self):
        """Fetch list of devices."""
        url = '{}/users/me'.format(API_URL)

        dlist = yield from self.api_get(url)
        if dlist is None:
            _LOGGER.error('Unable to fetch eight devices.')
        else:
            self._devices = dlist['user']['devices']
            _LOGGER.debug('Devices: %s', self._devices)

    @asyncio.coroutine
    def assign_users(self):
        """Update device properties."""
        device = self._devices[0]
        url = '{}/devices/{}?filter=ownerId,leftUserId,rightUserId' \
            .format(API_URL, device)

        data = yield from self.api_get(url)
        if data is None:
            _LOGGER.error('Unable to assign eight device users.')
        else:
            try:
                self.users[data['result']['leftUserId']] = \
                    EightUser(self, data['result']['leftUserId'], 'left')
                if self._partner:
                    self.users[data['result']['rightUserId']] = \
                        EightUser(self, data['result']['rightUserId'], 'right')
            except KeyError:
                # If we get a key error, most likely a single user on the
                # other side of the bed
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

    @asyncio.coroutine
    def update_device_data(self):
        """Update device data json."""
        url = '{}/devices/{}?offlineView=true'.format(API_URL, self.deviceid)

        # Check for access token expiration (every 15days)
        exp_delta = datetime.strptime(self._expdate, '%Y-%m-%dT%H:%M:%S.%fZ') \
            - datetime.fromtimestamp(time.time())
        # Renew 1hr before expiration
        if exp_delta.total_seconds() < 3600:
            _LOGGER.debug('Fetching new access token before expiration.')
            yield from self.fetch_token()

        device_resp = yield from self.api_get(url)
        if device_resp is None:
            _LOGGER.error('Unable to fetch eight device data.')
        else:
            # Want to keep last 10 readings so purge the last after we add
            self.handle_device_json(device_resp['result'])
            for user in self.users:
                self.users[user].dynamic_presence()

    @asyncio.coroutine
    def api_post(self, url, params=None, data=None):
        """Make api post request."""
        post = None
        try:
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self._event_loop):
                post = yield from self._api_session.post(
                    url, params=params, data=data)
            if post.status != 200:
                _LOGGER.error('Error posting Eight data: %s', post.status)
                return None

            if 'application/json' in post.headers['content-type']:
                post_result = yield from post.json()
            else:
                _LOGGER.debug('Response was not JSON, returning text.')
                post_result = yield from post.text()

            return post_result

        except (aiohttp.ClientError, asyncio.TimeoutError,
                ConnectionRefusedError) as err:
            _LOGGER.error('Error posting Eight data. %s', err)
            return None

    @asyncio.coroutine
    def api_get(self, url, params=None):
        """Make api fetch request."""
        request = None
        headers = DEFAULT_HEADERS.copy()
        headers.update({'Session-Token': self._token})

        try:
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self._event_loop):
                request = yield from self._api_session.get(
                    url, headers=headers, params=params)
            # _LOGGER.debug('Get URL: %s', request.url)
            if request.status != 200:
                _LOGGER.error('Error fetching Eight data: %s', request.status)
                return None

            if 'application/json' in request.headers['content-type']:
                request_json = yield from request.json()
            else:
                _LOGGER.debug('Response was not JSON, returning text.')
                request_json = yield from request.text()

            return request_json

        except (aiohttp.ClientError, asyncio.TimeoutError,
                ConnectionRefusedError) as err:
            _LOGGER.error('Error fetching Eight data. %s', err)
            return None

    @asyncio.coroutine
    def api_put(self, url, data=None):
        """Make api post request."""
        put = None
        headers = DEFAULT_HEADERS.copy()
        headers.update({'Session-Token': self._token})

        try:
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self._event_loop):
                put = yield from self._api_session.put(
                    url, headers=headers, data=data)
            if put.status != 200:
                _LOGGER.error('Error putting Eight data: %s', put.status)
                return None

            if 'application/json' in put.headers['content-type']:
                put_result = yield from put.json()
            else:
                _LOGGER.debug('Response was not JSON, returning text.')
                put_result = yield from put.text()

            return put_result

        except (aiohttp.ClientError, asyncio.TimeoutError,
                ConnectionRefusedError) as err:
            _LOGGER.error('Error putting Eight data. %s', err)
            return None
