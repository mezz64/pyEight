"""
pyeight.constants
~~~~~~~~~~~~~~~~~~~~
Constants list
Copyright (c) 2017 John Mihalic <https://github.com/mezz64>
Licensed under the MIT license.
"""

MAJOR_VERSION = 0
MINOR_VERSION = 0
SUB_MINOR_VERSION = 7
__version__ = '{}.{}.{}'.format(
    MAJOR_VERSION, MINOR_VERSION, SUB_MINOR_VERSION)

API_URL = 'https://client-api.8slp.net/v1'

DEFAULT_TIMEOUT = 10

DEFAULT_HEADERS = {
    'host': "client-api.8slp.net",
    'content-type': "application/x-www-form-urlencoded",
    'api-key': "api-key",
    'application-id': "morphy-app-id",
    'connection': "keep-alive",
    'user-agent': "Eight%20AppStore/11 CFNetwork/808.2.16 Darwin/16.3.0",
    'accept-language': "en-gb",
    'accept-encoding': "gzip, deflate",
    'accept': "*/*",
    'app-version': "1.10.0",
    }

# 1.10.0
