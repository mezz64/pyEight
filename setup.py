# Copyright (c) 2017-2020 John Mihalic <https://github.com/mezz64>
# Licensed under the MIT license.

# Used this guide to create module
# http://peterdowns.com/posts/first-time-with-pypi.html

# git tag 0.1 -m "0.1 release"
# git push --tags origin master
#
# Upload to PyPI Live
# python setup.py register -r pypi
# python setup.py sdist upload -r pypi


from distutils.core import setup
setup(
    name='pyEight',
    packages=['pyeight'],
    version='0.1.5',
    description='Provides a python api to interact with an Eight Sleep mattress cover.',
    author='John Mihalic',
    author_email='mezz64@users.noreply.github.com',
    url='https://github.com/mezz64/pyEight',
    download_url='https://github.com/mezz64/pyeight/tarball/0.1.5',
    keywords=['eight', 'eightsleep', 'eight sleep', 'sleep', 'mattress', 'api wrapper', 'homeassistant'],
    classifiers=[],
    )
