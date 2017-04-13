"""
pyeight.eight
~~~~~~~~~~~~~~~~~~~~
Provides api for Eight Sleep
Copyright (c) 2017 John Mihalic <https://github.com/mezz64>
Licensed under the MIT license.

"""

import logging
#import json
import asyncio
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

"""
Some general project notes that don't fit anywhere else:


"""


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

        # Setup 5 element list
        self._device_json = [None, None, None, None, None]

        if loop is None:
            _LOGGER.info("Creating our own event loop.")
            self._event_loop = asyncio.new_event_loop()
            self._own_loop = True
        else:
            _LOGGER.info("Latching onto an existing event loop.")
            self._event_loop = loop
            self._own_loop = False

        asyncio.set_event_loop(self._event_loop)

        self._api_session = aiohttp.ClientSession(
            headers=DEFAULT_HEADERS, loop=self._event_loop)

        # self.startup = False
        # self.initialize()

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

    def initialize(self):
        """Initialize api connection."""
        ensure_future(self.fetch_token(), loop=self._event_loop)

        if self._own_loop:
            _LOGGER.info("Starting up our own event loop.")
            self._event_loop.run_forever()
            self._event_loop.close()
            _LOGGER.info("Connection shut down.")

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
        yield from self.fetch_device_list()
        yield from self.assign_users()

    @asyncio.coroutine
    def fetch_token(self):
        """Fetch new session token from api."""
        url = '{}/login'.format(API_URL)
        payload = 'email={}&password={}'.format(self._email, self._password)

        reg = yield from self.api_post(url, None, payload)
        if reg is None:
            # self._registered = False
            _LOGGER.error('Unable to fetch eight token.')
        else:
            # _LOGGER.debug('Token Result: %s', reg)
            # Assume left side for now, we will update later
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
            # self._registered = False
            _LOGGER.error('Unable to fetch eight devices.')
        else:
            # _LOGGER.debug('Device Result: %s', dlist)
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
            # _LOGGER.debug('%s Device data: %s', device, data)

            self.users[data['result']['leftUserId']] = \
                EightUser(self, data['result']['leftUserId'], 'left')
            if self._partner:
                self.users[data['result']['rightUserId']] = \
                    EightUser(self, data['result']['rightUserId'], 'right')

    @asyncio.coroutine
    def update_device_data(self):
        """Update device data json."""
        url = '{}/devices/{}?offlineView=true'.format(API_URL, self.deviceid)

        device_resp = yield from self.api_get(url)
        if device_resp is None:
            _LOGGER.error('Unable to fetch eight device data.')
        else:
            # Want to keep last 5 readings so purge the last after we add
            self._device_json.insert(0, device_resp['result'])
            self._device_json.pop()
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
            _LOGGER.error('Error posting Eight data: %s', err)
            return None
        # finally:
        #     if post is not None:
        #         yield from post.release()

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
            _LOGGER.error('Error fetching Eight data: %s', err)
            return None
        # finally:
        #     if request is not None:
        #         yield from request.release()

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
            _LOGGER.error('Error putting Eight data: %s', err)
            return None
        # finally:
        #     if put is not None:
        #         yield from put.release()
