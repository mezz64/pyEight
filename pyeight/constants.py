"""
pyeight.constants
~~~~~~~~~~~~~~~~~~~~
Constants list
Copyright (c) 2017 John Mihalic <https://github.com/mezz64>
Licensed under the MIT license.
"""

MAJOR_VERSION = 0
MINOR_VERSION = 0
SUB_MINOR_VERSION = 8
__version__ = '{}.{}.{}'.format(
    MAJOR_VERSION, MINOR_VERSION, SUB_MINOR_VERSION)

API_URL = 'https://app-api.8slp.net/v1'

DEFAULT_TIMEOUT = 60

DEFAULT_HEADERS = {
    'content-type': "application/x-www-form-urlencoded",
    'connection': "keep-alive",
    'user-agent': "okhttp/3.6.0",
    'accept-encoding': "gzip",
    'accept': "*/*",
    'authority': "app-api.8slp.net",
    }
