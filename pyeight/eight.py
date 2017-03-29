"""
pyeight.eight
~~~~~~~~~~~~~~~~~~~~
Provides api for Eight Sleep
Copyright (c) 2017 John Mihalic <https://github.com/mezz64>
Licensed under the MIT license.

"""

import logging
import json
import asyncio
import aiohttp
import async_timeout

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
    def __init__(
            self, email, password, partner=False, api_key=None, loop=None):
        """Initialize eight sleep class."""
        self._email = email
        self._password = password
        self._partner = partner
        self._api_key = api_key

        self._userids = {}
        self._token = None
        self._expdate = None
        self._devices = None

        self._heating_json = None
        self._trends_json = {}
        self._intervals_json = {}

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
    def device_list(self):
        """Return list of devices."""
        return self._devices

    @property
    def heating_raw(self):
        """Return raw heating json."""
        return self._heating_json

    def initialize(self):
        """Initialize api connection."""
        ensure_future(self.fetch_token(), loop=self._event_loop)

        if self._own_loop:
            _LOGGER.info("Starting up our own event loop.")
            self._event_loop.run_forever()
            self._event_loop.close()
            _LOGGER.info("Connection shut down.")

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
            _LOGGER.debug('Token Result: %s', reg)
            # Assume left side for now, we will update later
            self._userids['Left'] = reg['session']['userId']
            self._token = reg['session']['token']
            self._expdate = reg['session']['expirationDate']

    @asyncio.coroutine
    def fetch_device_list(self):
        """Fetch list of devices."""
        url = '{}/users/me'.format(API_URL)

        dlist = yield from self.api_get(url)
        if dlist is None:
            # self._registered = False
            _LOGGER.error('Unable to fetch eight devices.')
        else:
            _LOGGER.debug('Device Result: %s', dlist)
            self._devices = dlist['user']['devices']

    @asyncio.coroutine
    def assign_users(self):
        """Update device properties."""
        for device in self._devices:
            url = '{}/devices/{}?filter=ownerId,leftUserId,rightUserId' \
                .format(API_URL, device)

            data = yield from self.api_get(url)
            if data is None:
                # self._registered = False
                _LOGGER.error('Unable to assign eight device users.')
            else:
                _LOGGER.debug('%s Device data: %s', device, data)
                if data['result']['leftUserId'] == self._userids['Left']:
                    # We guessed correctly, populate partner if needed.
                    if self._partner:
                        self._userids['Right'] = data['result']['rightUserId']
                elif data['result']['rightUserId'] == self._userids['Left']:
                    # We guessed wrong, update both as needed.
                    self._userids['Right'] = data['result']['rightUserId']
                    if self._partner:
                        self._userids['Left'] = data['result']['leftUserId']
                    else:
                        self._userids['Left'] = None

    @asyncio.coroutine
    def update_heating_data(self, device):
        """Update heating data json."""
        url = '{}/devices/{}?offlineView=true'.format(API_URL, device)

        heating = yield from self.api_get(url)
        if heating is None:
            _LOGGER.error('Unable to fetch eight heating data.')
        else:
            _LOGGER.debug('Heating Result: %s', heating)
            self._heating_json = heating['result']

    @asyncio.coroutine
    def update_trend_data(self, userid, tz, startdate, enddate):
        """Update trends data json for specified time period."""
        url = '{}/users/{}/trends'.format(API_URL, userid)
        params = {
            'tz': tz,
            'from': startdate,
            'to': enddate
            }

        trends = yield from self.api_get(url, params)
        if trends is None:
            _LOGGER.error('Unable to fetch eight trend data.')
        else:
            _LOGGER.debug('Trend Result: %s', trends)
            self._trends_json[userid] = trends

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

        except (aiohttp.errors.ClientError, asyncio.TimeoutError,
                ConnectionRefusedError) as err:
            _LOGGER.error('Error posting Eight data: %s', err)
            return None
        finally:
            if post is not None:
                yield from post.release()

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
            if request.status != 200:
                _LOGGER.error('Error fetching Eight data: %s', request.status)
                return None

            if 'application/json' in request.headers['content-type']:
                request_json = yield from request.json()
            else:
                _LOGGER.debug('Response was not JSON, returning text.')
                request_json = yield from request.text()

            return request_json

        except (aiohttp.errors.ClientError, asyncio.TimeoutError,
                ConnectionRefusedError) as err:
            _LOGGER.error('Error fetching Eight data: %s', err)
            return None
        finally:
            if request is not None:
                yield from request.release()

    @asyncio.coroutine
    def api_put(self, url, params=None, data=None):
        """Make api post request."""
        put = None
        headers = DEFAULT_HEADERS.copy()
        headers.update({'Session-Token': self._token})

        try:
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self._event_loop):
                put = yield from self._api_session.put(
                    url, headers=headers, params=params, data=data)
            if put.status != 200:
                _LOGGER.error('Error putting Eight data: %s', put.status)
                return None

            if 'application/json' in put.headers['content-type']:
                put_result = yield from put.json()
            else:
                _LOGGER.debug('Response was not JSON, returning text.')
                put_result = yield from put.text()

            return put_result

        except (aiohttp.errors.ClientError, asyncio.TimeoutError,
                ConnectionRefusedError) as err:
            _LOGGER.error('Error putting Eight data: %s', err)
            return None
        finally:
            if put is not None:
                yield from put.release()
