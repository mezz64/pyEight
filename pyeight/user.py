"""
pyeight.user
~~~~~~~~~~~~~~~~~~~~
Provides user data for Eight Sleep
Copyright (c) 2017-2020 John Mihalic <https://github.com/mezz64>
Licensed under the MIT license.

"""

import logging
from datetime import datetime
from datetime import timedelta
import statistics
import time
import asyncio

from pyeight.constants import (API_URL)

_LOGGER = logging.getLogger(__name__)


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
        self.obv_low = 0

    @property
    def bed_presence(self):
        """Return true/false for bed presence."""
        return self.presence

    @property
    def target_heating_level(self):
        """Return target heating/cooling level."""
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
        """Return heating/cooling level."""
        try:
            if self.side == 'left':
                level = self.device.device_data['leftHeatingLevel']
            elif self.side == 'right':
                level = self.device.device_data['rightHeatingLevel']
            # Update observed low
            if level < self.obv_low:
                self.obv_low = level
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
            if self.target_heating_level > 0:
                if self.side == 'left':
                    heat = self.device.device_data['leftNowHeating']
                elif self.side == 'right':
                    heat = self.device.device_data['rightNowHeating']
                return heat
            else:
                return False
        except TypeError:
            return None

    @property
    def now_cooling(self):
        """Return current cooling state."""
        try:
            if self.target_heating_level < 0:
                if self.side == 'left':
                    cool = self.device.device_data['leftNowHeating']
                elif self.side == 'right':
                    cool = self.device.device_data['rightNowHeating']
                return cool
            else:
                return False
        except TypeError:
            return None

    @property
    def heating_remaining(self):
        """Return seconds of heat/cool time remaining."""
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
        """
        These values seem to be rarely updated correctly in the API.
        Don't expect accurate results from this property.
        """
        try:
            if self.side == 'left':
                lastseen = self.device.device_data['leftPresenceEnd']
            elif self.side == 'right':
                lastseen = self.device.device_data['rightPresenceEnd']

            date = datetime.fromtimestamp(int(lastseen)) \
                .strftime('%Y-%m-%dT%H:%M:%S')
            return date
        except (TypeError, KeyError):
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
    def current_fitness_session_date(self):
        """Return date/time for start of last session data."""
        try:
            length = len(self.trends['days']) - 1
            date = self.trends['days'][length]['day']
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

            if num_stages == 0:
                return None

            # API now always has an awake state last in the dict
            # so always pull the second to last stage while we are
            # in a processing state
            if self.current_session_processing:
                stage = stages[num_stages-2]['stage']
            else:
                stage = stages[num_stages-1]['stage']

            # UNRELIABLE... Removing for now.
            # Check sleep stage against last_seen time to make
            # sure we don't get stuck in a non-awake state.
            #delta_elap = datetime.fromtimestamp(time.time()) \
            #    - datetime.strptime(self.last_seen, '%Y-%m-%dT%H:%M:%S')
            #_LOGGER.debug('User elap: %s', delta_elap.total_seconds())
            #if stage != 'awake' and delta_elap.total_seconds() > 1800:
                # Bed hasn't seen us for 30min so set awake.
            #    stage = 'awake'

            # Second try at forcing awake using heating level
            if stage != 'awake' and self.heating_level < 5:
                stage = 'awake'

        except KeyError:
            stage = None
        return stage

    @property
    def current_sleep_score(self):
        """Return sleep score for in-progress session."""
        try:
            score = self.intervals[0]['score']
        except KeyError:
            score = None
        return score

    def trend_sleep_score(self, date):
        """Return trend sleep score for specified date."""
        days = self.trends['days']
        for day in days:
            # _LOGGER.debug("Trend day: %s, Requested day: %s", day['day'], date)
            if day['day'] == date:
                try:
                    score = day['score']
                except KeyError:
                    score = None
                return score

    def sleep_fitness_score(self, date):
        """Return sleep fitness score for specified date."""
        days = self.trends['days']
        for day in days:
            if day['day'] == date:
                try:
                    score = day['sleepFitnessScore']['total']
                except KeyError:
                    score = None
                return score

    @property
    def current_sleep_fitness_score(self):
        """Return sleep fitness score for latest session."""
        try:
            length = len(self.trends['days']) - 1
            score = self.trends['days'][length]['sleepFitnessScore']['total']
        except KeyError:
            score = None
        return score

    @property
    def current_sleep_duration_score(self):
        """Return sleep duration score for latest session."""
        try:
            length = len(self.trends['days']) - 1
            score = self.trends['days'][length]['sleepFitnessScore']['sleepDurationSeconds']['score']
        except KeyError:
            score = None
        return score

    @property
    def current_latency_asleep_score(self):
        """Return latency asleep score for latest session."""
        try:
            length = len(self.trends['days']) - 1
            score = self.trends['days'][length]['sleepFitnessScore']['latencyAsleepSeconds']['score']
        except KeyError:
            score = None
        return score

    @property
    def current_latency_out_score(self):
        """Return latency out score for latest session."""
        try:
            length = len(self.trends['days']) - 1
            score = self.trends['days'][length]['sleepFitnessScore']['latencyOutSeconds']['score']
        except KeyError:
            score = None
        return score

    @property
    def current_wakeup_consistency_score(self):
        """Return wakeup consistency score for latest session."""
        try:
            length = len(self.trends['days']) - 1
            score = self.trends['days'][length]['sleepFitnessScore']['wakeupConsistency']['score']
        except KeyError:
            score = None
        return score

    @property
    def current_sleep_breakdown(self):
        """Return durations of sleep stages for in-progress session."""
        try:
            stages = self.intervals[0]['stages']
            breakdown = {'awake': 0, 'light': 0, 'deep': 0, 'rem': 0}
            for stage in stages:
                if stage['stage'] == 'awake':
                    breakdown['awake'] += stage['duration']
                elif stage['stage'] == 'light':
                    breakdown['light'] += stage['duration']
                elif stage['stage'] == 'deep':
                    breakdown['deep'] += stage['duration']
                elif stage['stage'] == 'rem':
                    breakdown['rem'] += stage['duration']
        except KeyError:
            breakdown = None
        return breakdown

    @property
    def current_bed_temp(self):
        """Return current bed temperature for in-progress session."""
        try:
            bedtemps = self.intervals[0]['timeseries']['tempBedC']
            num_temps = len(bedtemps)

            if num_temps == 0:
                return None

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

            if num_temps == 0:
                return None

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

            if num_rates == 0:
                return None

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

            if num_rates == 0:
                return None

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
    def current_fitness_values(self):
        """Return a dict of all the 'current' fitness score parameters."""
        current_dict = {
            'date': self.current_fitness_session_date,
            'score': self.current_sleep_fitness_score,
            'duration': self.current_sleep_duration_score,
            'asleep': self.current_latency_asleep_score,
            'out': self.current_latency_out_score,
            'wakeup': self.current_wakeup_consistency_score
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

        breakdown = {'awake': 0, 'light': 0, 'deep': 0, 'rem': 0}
        for stage in stages:
            if stage['stage'] == 'awake':
                breakdown['awake'] += stage['duration']
            elif stage['stage'] == 'light':
                breakdown['light'] += stage['duration']
            elif stage['stage'] == 'deep':
                breakdown['deep'] += stage['duration']
            elif stage['stage'] == 'rem':
                breakdown['rem'] += stage['duration']
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

        if num_temps == 0:
            return None

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

        if num_temps == 0:
            return None

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

        if num_rates == 0:
            return None

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

        if num_rates == 0:
            return None

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

        # self.heating_stats()

        # Method needs to be different for pod since it doesn't rest at 0
        #  - Working idea is to track the low and adjust the scale so that low is 0
        #  - Buffer changes while cooling/heating is active
        level_zero = self.obv_low * (-1)
        working_level = self.heating_level + level_zero
        if self.device.is_pod:
            if not self.presence:
                if working_level > 50:
                    if not self.now_cooling and not self.now_heating:
                        self.presence = True
                    elif self.target_heating_level > 0:
                        # Heating
                        if working_level - self.target_heating_level >= 8:
                            self.presence = True
                    elif self.target_heating_level < 0:
                        # Cooling
                        if self.heating_level + self.target_heating_level >=8:
                            self.presence = True
                elif working_level > 25:
                    # Catch rising edge
                    if self.past_heating_level(0) - self.past_heating_level(1) >= 2 \
                        and self.past_heating_level(1) - self.past_heating_level(2) >= 2 \
                            and self.past_heating_level(2) - self.past_heating_level(3) >= 2:
                        # Values are increasing so we are likely in bed
                        if not self.now_heating:
                            self.presence = True
                        elif working_level - self.target_heating_level >= 8:
                            self.presence = True
                    
            elif self.presence:
                if working_level <= 15:
                    # Failsafe, very slow
                    self.presence = False
                elif working_level < 35: # Threshold is expiremental for now
                    if self.past_heating_level(0) - self.past_heating_level(1) < 0 \
                        and self.past_heating_level(1) - self.past_heating_level(2) < 0 \
                            and self.past_heating_level(2) - self.past_heating_level(3) < 0:
                        # Values are decreasing so we are likely out of bed
                        self.presence = False
        else:
            # Method for 0 resting state
            if not self.presence:
                if self.heating_level > 50:
                    # Can likely make this better
                    if not self.now_heating:
                        self.presence = True
                    elif self.heating_level - self.target_heating_level >= 8:
                        self.presence = True
                elif self.heating_level > 25:
                    # Catch rising edge
                    if self.past_heating_level(0) - self.past_heating_level(1) >= 2 \
                        and self.past_heating_level(1) - self.past_heating_level(2) >= 2 \
                            and self.past_heating_level(2) - self.past_heating_level(3) >= 2:
                        # Values are increasing so we are likely in bed
                        if not self.now_heating:
                            self.presence = True
                        elif self.heating_level - self.target_heating_level >= 8:
                            self.presence = True

            elif self.presence:
                if self.heating_level <= 15:
                    # Failsafe, very slow
                    self.presence = False
                elif self.heating_level < 50:
                    if self.past_heating_level(0) - self.past_heating_level(1) < 0 \
                        and self.past_heating_level(1) - self.past_heating_level(2) < 0 \
                            and self.past_heating_level(2) - self.past_heating_level(3) < 0:
                        # Values are decreasing so we are likely out of bed
                        self.presence = False

        # Last seen can lag real-time by up to 35min so this is
        # mostly a backup to using the heat values.
        # seen_delta = datetime.fromtimestamp(time.time()) \
        #     - datetime.strptime(self.last_seen, '%Y-%m-%dT%H:%M:%S')
        # _LOGGER.debug('%s Last seen time delta: %s', self.side,
        #               seen_delta.total_seconds())
        # if self.presence and seen_delta.total_seconds() > 2100:
        #     self.presence = False

        _LOGGER.debug('%s Presence Results: %s', self.side, self.presence)

    async def update_user(self):
        """Update all user data."""
        await self.update_intervals_data()

        now = datetime.today()
        start = now - timedelta(days=2)
        end = now + timedelta(days=2)

        await self.update_trend_data(start.strftime('%Y-%m-%d'),
                                     end.strftime('%Y-%m-%d'))

    async def set_heating_level(self, level, duration=0):
        """Update heating data json."""
        url = '{}/devices/{}'.format(API_URL, self.device.deviceid)

        # Catch bad low inputs
        if self.device.is_pod:
            level = -100 if level < -100 else level
        else:
            level = 0 if level < 0 else level

        # Catch bad high inputs
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

        set_heat = await self.device.api_put(url, data)
        if set_heat is None:
            _LOGGER.error('Unable to set eight heating level.')
        else:
            # Standard device json is returned after setting
            self.device.handle_device_json(set_heat['device'])

    async def update_trend_data(self, startdate, enddate):
        """Update trends data json for specified time period."""
        url = '{}/users/{}/trends'.format(API_URL, self.userid)
        params = {
            'tz': self.device.tzone,
            'from': startdate,
            'to': enddate,
            # 'include-main': 'true'
            }
        trend_data = await self.device.api_get(url, params)
        if trend_data is None:
            _LOGGER.error('Unable to fetch eight trend data.')
        else:
            # self.trends = trends['days']
            self.trends = trend_data

    async def update_intervals_data(self):
        """Update intervals data json for specified time period."""
        url = '{}/users/{}/intervals'.format(API_URL, self.userid)

        intervals = await self.device.api_get(url)
        if intervals is None:
            _LOGGER.error('Unable to fetch eight intervals data.')
        else:
            self.intervals = intervals['intervals']
