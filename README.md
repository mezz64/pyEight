[![PyPI](https://img.shields.io/pypi/v/pyEight.svg)](https://pypi.python.org/pypi/pyEight)

# Introduction
Python library to interface with the Eight Sleep API

API is currently undocumented.  Usage is derived by capturing api calls made by the Eight Sleep android app.

Code is licensed under the MIT license.

## Thanks

Special thanks to github user @alyc100 for making his SmartThings Eight Sleep code available.

# Requirements

* python >= 3.5
* aiohttp >= 2.0
* asyncio
* async_timeout

# Installation

```pip install pyeight```

# Usage

Full usage example can be found in the HomeAssistant implementation of this library.

Basic Usage
```python
from pyeight.eight import EightSleep

eight = EightSleep(user, pass, timezone, None, None)

await eight.start()

# Update mattress data, 1min interval recommended
await eight.update_device_data()

# Update user data, 5min interval recommended
await eight.update_user_data()

```

# Properties

Library properties are well defined in both ```eight.py``` and ```user.py```.

# TODO

* Improve dynamic presence detection through statistical analysis
