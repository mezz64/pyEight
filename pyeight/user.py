"""
pyeight.user
~~~~~~~~~~~~~~~~~~~~
Provides user data for Eight Sleep
Copyright (c) 2017 John Mihalic <https://github.com/mezz64>
Licensed under the MIT license.

"""

import logging
from datetime import datetime
import statistics
import time
import asyncio

from pyeight.constants import (API_URL)

_LOGGER = logging.getLogger(__name__)

"""
Best way to structure this is to work to one HASS sensor for sleep data
and one for bed data for each side of the bed (if applicable).

Last Sleep Session sensor
_________________________________________
State will be the sleep score.
Attributes will be:
    Duration of awake, light, deep sleep
    Number of tosses and turns
    Average room temp
    Average bed temp
    Average respiritory rate
    Average heart rate
    Time spent heating

* These values are very dynamic during sleep so may only be useful
  when the "incomplete" parameter isn't present

Bed data sensor
_________________________________________
State will be current heating level
Attributes will be:
    Target heating level
    Heating Active (true/false)
    Heating duration remaining
    Time last seen in-bed

"""


class EightUser(object):
    """Class for handling data of each eight user."""
    def __init__(self, device, userid, side):
        """Initialize user class."""
        self.device = device
        self.userid = userid
        self.side = side

        self.trends = None
        self.intervals = None

        # Variables to do dynamic presence
        self.presence = False
        self.presence_dict = {}

    @property
    def bed_presence(self):
        """Return true/false for bed presence."""
        return self.presence

    @property
    def target_heating_level(self):
        """Return target heating level."""
        try:
            if self.side == 'left':
                level = self.device.device_data['leftTargetHeatingLevel']
            elif self.side == 'right':
                level = self.device.device_data['rightTargetHeatingLevel']
            return level
        except TypeError:
            return None

    @property
    def heating_level(self):
        """Return heating level."""
        try:
            if self.side == 'left':
                level = self.device.device_data['leftHeatingLevel']
            elif self.side == 'right':
                level = self.device.device_data['rightHeatingLevel']
            return level
        except TypeError:
            return None

    def past_heating_level(self, num):
        """Return a heating level from the past."""
        if num > 9:
            return 0

        try:
            if self.side == 'left':
                level = self.device.device_data_history[
                    num]['leftHeatingLevel']
            elif self.side == 'right':
                level = self.device.device_data_history[
                    num]['rightHeatingLevel']
            return level
        except TypeError:
            return 0

    @property
    def now_heating(self):
        """Return current heating state."""
        try:
            if self.side == 'left':
                heat = self.device.device_data['leftNowHeating']
            elif self.side == 'right':
                heat = self.device.device_data['rightNowHeating']
            return heat
        except TypeError:
            return None

    @property
    def heating_remaining(self):
        """Return seconds of heat time remaining."""
        try:
            if self.side == 'left':
                timerem = self.device.device_data['leftHeatingDuration']
            elif self.side == 'right':
                timerem = self.device.device_data['rightHeatingDuration']
            return timerem
        except TypeError:
            return None

    @property
    def last_seen(self):
        """Return mattress last seen time."""
        try:
            if self.side == 'left':
                lastseen = self.device.device_data['leftPresenceEnd']
            elif self.side == 'right':
                lastseen = self.device.device_data['rightPresenceEnd']

            date = datetime.fromtimestamp(int(lastseen)) \
                .strftime('%Y-%m-%dT%H:%M:%S')
            return date
        except TypeError:
            return None

    @property
    def heating_values(self):
        """Return a dict of all the current heating values."""
        heating_dict = {
            'level': self.heating_level,
            'target': self.target_heating_level,
            'active': self.now_heating,
            'remaining': self.heating_remaining,
            'last_seen': self.last_seen,
        }
        return heating_dict

    @property
    def current_session_date(self):
        """Return date/time for start of last session data."""
        try:
            date = self.intervals[0]['ts']
            date_f = datetime.strptime(date, '%Y-%m-%dT%H:%M:%S.%fZ')
            now = time.time()
            offset = datetime.fromtimestamp(now) \
                - datetime.utcfromtimestamp(now)
            date = date_f + offset
        except KeyError:
            date = None
        return date

    @property
    def current_session_processing(self):
        """Return processing state of current session."""
        try:
            incomplete = self.intervals[0]['incomplete']
        except KeyError:
            # No incomplete key, not processing
            incomplete = False
        return incomplete

    @property
    def current_sleep_stage(self):
        """Return sleep stage for in-progress session."""
        try:
            stages = self.intervals[0]['stages']
            num_stages = len(stages)
            stage = stages[num_stages-1]['stage']

            # Check sleep stage against last_seen time to make
            # sure we don't get stuck in a non-awake state.
            delta_elap = datetime.fromtimestamp(time.time()) \
                - datetime.strptime(self.last_seen, '%Y-%m-%dT%H:%M:%S')
            if stage != 'awake' and delta_elap.total_seconds() > 900:
                # Bed hasn't seen us for 15min so set awake.
                stage = 'awake'
        except KeyError:
            stage = None
        return stage

    @property
    def current_sleep_score(self):
        """Return sleep score for in-progress session."""
        # Check most recent result to see if it's incomplete.
        try:
            score = self.intervals[0]['score']
        except KeyError:
            score = None
        return score

    @property
    def current_sleep_breakdown(self):
        """Return durations of sleep stages for in-progress session."""
        try:
            stages = self.intervals[0]['stages']
            breakdown = {'awake': 0, 'light': 0, 'deep': 0}
            for stage in stages:
                if stage['stage'] == 'awake':
                    breakdown['awake'] += stage['duration']
                elif stage['stage'] == 'light':
                    breakdown['light'] += stage['duration']
                elif stage['stage'] == 'deep':
                    breakdown['deep'] += stage['duration']
        except KeyError:
            breakdown = None
        return breakdown

    @property
    def current_bed_temp(self):
        """Return current bed temperature for in-progress session."""
        try:
            bedtemps = self.intervals[0]['timeseries']['tempBedC']
            num_temps = len(bedtemps)
            bedtemp = bedtemps[num_temps-1][1]
        except KeyError:
            bedtemp = None
        return bedtemp

    @property
    def current_room_temp(self):
        """Return current room temperature for in-progress session."""
        try:
            rmtemps = self.intervals[0]['timeseries']['tempRoomC']
            num_temps = len(rmtemps)
            rmtemp = rmtemps[num_temps-1][1]
        except KeyError:
            rmtemp = None
        return rmtemp

    @property
    def current_tnt(self):
        """Return current toss & turns for in-progress session."""
        try:
            tnt = len(self.intervals[0]['timeseries']['tnt'])
        except KeyError:
            tnt = None
        return tnt

    @property
    def current_resp_rate(self):
        """Return current respiratory rate for in-progress session."""
        try:
            rates = self.intervals[0]['timeseries']['respiratoryRate']
            num_rates = len(rates)
            rate = rates[num_rates-1][1]
        except KeyError:
            rate = None
        return rate

    @property
    def current_heart_rate(self):
        """Return current heart rate for in-progress session."""
        try:
            rates = self.intervals[0]['timeseries']['heartRate']
            num_rates = len(rates)
            rate = rates[num_rates-1][1]
        except KeyError:
            rate = None
        return rate

    @property
    def current_values(self):
        """Return a dict of all the 'current' parameters."""
        current_dict = {
            'date': self.current_session_date,
            'score': self.current_sleep_score,
            'stage': self.current_sleep_stage,
            'breakdown': self.current_sleep_breakdown,
            'tnt': self.current_tnt,
            'bed_temp': self.current_bed_temp,
            'room_temp': self.current_room_temp,
            'resp_rate': self.current_resp_rate,
            'heart_rate': self.current_heart_rate,
            'processing': self.current_session_processing,
        }
        return current_dict

    @property
    def last_session_date(self):
        """Return date/time for start of last session data."""
        try:
            date = self.intervals[1]['ts']
        except KeyError:
            return None
        date_f = datetime.strptime(date, '%Y-%m-%dT%H:%M:%S.%fZ')
        now = time.time()
        offset = datetime.fromtimestamp(now) - datetime.utcfromtimestamp(now)
        return date_f + offset

    @property
    def last_session_processing(self):
        """Return processing state of current session."""
        try:
            incomplete = self.intervals[1]['incomplete']
        except KeyError:
            # No incomplete key, not processing
            incomplete = False
        return incomplete

    @property
    def last_sleep_score(self):
        """Return sleep score from last complete sleep session."""
        try:
            score = self.intervals[1]['score']
        except KeyError:
            score = None
        return score

    @property
    def last_sleep_breakdown(self):
        """Return durations of sleep stages for last complete session."""
        try:
            stages = self.intervals[1]['stages']
        except KeyError:
            return None

        breakdown = {'awake': 0, 'light': 0, 'deep': 0}
        for stage in stages:
            if stage['stage'] == 'awake':
                breakdown['awake'] += stage['duration']
            elif stage['stage'] == 'light':
                breakdown['light'] += stage['duration']
            elif stage['stage'] == 'deep':
                breakdown['deep'] += stage['duration']
        return breakdown

    @property
    def last_bed_temp(self):
        """Return avg bed temperature for last session."""
        try:
            bedtemps = self.intervals[1]['timeseries']['tempBedC']
        except KeyError:
            return None
        tmp = 0
        num_temps = len(bedtemps)
        for temp in bedtemps:
            tmp += temp[1]
        bedtemp = tmp/num_temps
        return bedtemp

    @property
    def last_room_temp(self):
        """Return avg room temperature for last session."""
        try:
            rmtemps = self.intervals[1]['timeseries']['tempRoomC']
        except KeyError:
            return None
        tmp = 0
        num_temps = len(rmtemps)
        for temp in rmtemps:
            tmp += temp[1]
        rmtemp = tmp/num_temps
        return rmtemp

    @property
    def last_tnt(self):
        """Return toss & turns for last session."""
        try:
            tnt = len(self.intervals[1]['timeseries']['tnt'])
        except KeyError:
            return None
        return tnt

    @property
    def last_resp_rate(self):
        """Return avg respiratory rate for last session."""
        try:
            rates = self.intervals[1]['timeseries']['respiratoryRate']
        except KeyError:
            return None
        tmp = 0
        num_rates = len(rates)
        for rate in rates:
            tmp += rate[1]
        rateavg = tmp/num_rates
        return rateavg

    @property
    def last_heart_rate(self):
        """Return avg heart rate for last session."""
        try:
            rates = self.intervals[1]['timeseries']['heartRate']
        except KeyError:
            return None
        tmp = 0
        num_rates = len(rates)
        for rate in rates:
            tmp += rate[1]
        rateavg = tmp/num_rates
        return rateavg

    @property
    def last_values(self):
        """Return a dict of all the 'last' parameters."""
        last_dict = {
            'date': self.last_session_date,
            'score': self.last_sleep_score,
            'breakdown': self.last_sleep_breakdown,
            'tnt': self.last_tnt,
            'bed_temp': self.last_bed_temp,
            'room_temp': self.last_room_temp,
            'resp_rate': self.last_resp_rate,
            'heart_rate': self.last_heart_rate,
            'processing': self.last_session_processing,
        }
        return last_dict

    def heating_stats(self):
        """Calculate some heating data stats."""
        local_5 = []
        local_10 = []
        # time_5 = [1, 2, 3, 4, 5]
        # time_10 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

        for i in range(0, 10):
            level = self.past_heating_level(i)
            if level == 0:
                _LOGGER.debug('Cant calculate stats yet...')
                return
            if i < 5:
                local_5.append(level)
            local_10.append(level)

        _LOGGER.debug('%s Heating History: %s', self.side, local_10)

        try:
            # Average of 5min on the history dict.
            fiveminavg = statistics.mean(local_5)
            tenminavg = statistics.mean(local_10)
            _LOGGER.debug('%s Heating 5 min avg: %s', self.side, fiveminavg)
            _LOGGER.debug('%s Heating 10 min avg: %s', self.side, tenminavg)

            # Standard deviation
            fivestdev = statistics.stdev(local_5)
            tenstdev = statistics.stdev(local_10)
            _LOGGER.debug('%s Heating 5 min stdev: %s', self.side, fivestdev)
            _LOGGER.debug('%s Heating 10 min stdev: %s', self.side, tenstdev)

            # Variance
            fivevar = statistics.variance(local_5)
            tenvar = statistics.variance(local_10)
            _LOGGER.debug('%s Heating 5 min variance: %s', self.side, fivevar)
            _LOGGER.debug('%s Heating 10 min variance: %s', self.side, tenvar)
        except:
            _LOGGER.debug('Cant calculate stats yet...')

        # Other possible options for exploration....
        # Pearson correlation coefficient
        # Spearman rank correlation
        # Kendalls Tau


    def dynamic_presence(self):
        """
        Determine presence based on bed heating level and end presence
        time reported by the api.

        Idea originated from Alex Lee Yuk Cheung SmartThings Code.
        """
        limp = False

        self.heating_stats()

        # Need at least a 5 min buffer of data to return decent results
        # If we don't have that (at start) flag limp mode
        if self.past_heating_level(4) == 0:
            limp = True
        elif self.heating_level:
            hist_delta = self.heating_level - self.past_heating_level(4)
            hist_delta_2 = self.past_heating_level(1) \
                - self.past_heating_level(5)
            hist_delta_3 = self.past_heating_level(2) \
                - self.past_heating_level(6)
            hist_sum = hist_delta + hist_delta_2 + hist_delta_3

        # Calculate a heating delta that always represents user heat added
        if self.now_heating:
            heat_delta = self.heating_level - self.target_heating_level
        elif self.heating_level:
            heat_delta = self.heating_level - 10

        if not self.presence:
            # We don't think anyone is in bed, lets do some checks to
            # verify that's the case.
            if limp:
                # No history so do a basic level check
                if heat_delta >= 8 and self.heating_level >= 25:
                    self.presence = True
            else:
                if self.heating_level >= 25:
                    # Either someone is in bed or we have residual heat
                    if hist_delta >= 10 and heat_delta >= 8:
                        self.presence = True

        elif self.presence:
            # We think someone is in bed, lets do some check to
            # verify that's the case.
            if limp:
                # We don't have enough info to reliably say someone left
                # the bed so just return.
                return
            else:
                if self.heating_level <= 15:
                    # This is a failsafe, very slow
                    self.presence = False
                else:
                    if hist_sum < 30 and self.heating_level < 50:
                        # This still isn't very fast
                        self.presence = False

                    # Last seen can lag real-time by up to 35min so this is
                    # mostly a backup to using the heat values.
                    seen_delta = datetime.fromtimestamp(time.time()) \
                        - datetime.strptime(self.last_seen, '%Y-%m-%dT%H:%M:%S')
                    if self.presence and seen_delta.total_seconds() > 2100:
                        self.presence = False

        _LOGGER.debug('%s Presence Results: %s', self.side, self.presence)

    @asyncio.coroutine
    def update_user(self):
        """Update all user data."""
        yield from self.update_intervals_data()

        # Not using the trends api endpoint for now.
        # now = datetime.today()
        # start = now - timedelta(days=2)
        # end = now + timedelta(days=2)
        # yield from self.update_trend_data(start.strftime('%Y-%m-%d'),
        #                                  end.strftime('%Y-%m-%d'))

    @asyncio.coroutine
    def set_heating_level(self, level, duration=0):
        """Update heating data json."""
        url = '{}/devices/{}'.format(API_URL, self.device.deviceid)

        # Catch bad inputs
        level = 10 if level < 10 else level
        level = 100 if level > 100 else level

        if self.side == 'left':
            data = {
                'leftHeatingDuration': duration,
                'leftTargetHeatingLevel': level
            }
        elif self.side == 'right':
            data = {
                'rightHeatingDuration': duration,
                'rightTargetHeatingLevel': level
            }

        set_heat = yield from self.device.api_put(url, data)
        if set_heat is None:
            _LOGGER.error('Unable to set eight heating level.')
        else:
            # _LOGGER.debug('Heating Result: %s', set_heat)
            # Standard device json is returned after setting
            self.device.handle_device_json(set_heat['device'])

    @asyncio.coroutine
    def update_trend_data(self, startdate, enddate):
        """Update trends data json for specified time period."""
        url = '{}/users/{}/trends'.format(API_URL, self.userid)
        params = {
            'tz': self.device.tzone,
            'from': startdate,
            'to': enddate
            }

        trends = yield from self.device.api_get(url, params)
        if trends is None:
            _LOGGER.error('Unable to fetch eight trend data.')
        else:
            # _LOGGER.debug('Trend Result: %s', trends)
            self.trends = trends['days']

    @asyncio.coroutine
    def update_intervals_data(self):
        """Update intervals data json for specified time period."""
        url = '{}/users/{}/intervals'.format(API_URL, self.userid)

        intervals = yield from self.device.api_get(url)
        if intervals is None:
            _LOGGER.error('Unable to fetch eight intervals data.')
        else:
            # _LOGGER.debug('Intervals Result: %s', intervals)
            self.intervals = intervals['intervals']
