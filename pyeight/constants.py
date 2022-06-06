"""
pyeight.constants
~~~~~~~~~~~~~~~~~~~~
Constants list
Copyright (c) 2017-2022 John Mihalic <https://github.com/mezz64>
Licensed under the MIT license.
"""

MAJOR_VERSION = 0
MINOR_VERSION = 3
SUB_MINOR_VERSION = 0
__version__ = f"{MAJOR_VERSION}.{MINOR_VERSION}.{SUB_MINOR_VERSION}"

API_URL = "https://client-api.8slp.net/v1"

DEFAULT_TIMEOUT = 240
DATE_TIME_ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
DATE_FORMAT = "%Y-%m-%d"

DEFAULT_HEADERS = {
    "content-type": "application/json",
    "connection": "keep-alive",
    "user-agent": "okhttp/4.9.1",
    "accept-encoding": "gzip",
    "accept": "application/json",
    "authority": "client-api.8slp.net",
}
