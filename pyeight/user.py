"""
pyeight.user
~~~~~~~~~~~~~~~~~~~~
Provides user data for Eight Sleep
Copyright (c) 2017-2022 John Mihalic <https://github.com/mezz64>
Licensed under the MIT license.
"""
from datetime import datetime, timedelta
import logging
import statistics
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union, cast
from zoneinfo import ZoneInfo

from .constants import API_URL, DATE_FORMAT, DATE_TIME_ISO_FORMAT

if TYPE_CHECKING:
    from .eight import EightSleep

_LOGGER = logging.getLogger(__name__)


class EightUser:  # pylint: disable=too-many-public-methods
    """Class for handling data of each eight user."""

    def __init__(self, device: "EightSleep", user_id: str, side: str):
        """Initialize user class."""
        self.device = device
        self.user_id = user_id
        self.side = side
        self._user_profile: Dict[str, Any] = {}

        self.trends: List[Dict[str, Any]] = []
        self.intervals: List[Dict[str, Any]] = []

        # Variables to do dynamic presence
        self.presence: bool = False
        self.observed_low: int = 0

    def _get_trend(self, trend_num: int, keys: Union[str, Tuple[str, ...]]) -> Any:
        """Get trend value for specified key."""
        if len(self.trends) < trend_num + 1:
            return None
        data = self.trends[-(trend_num + 1)]
        if isinstance(keys, str):
            return data.get(keys)
        if self.trends:
            for key in keys[:-1]:
                data = data.get(key, {})
        return data.get(keys[-1])

    def _get_fitness_score(self, trend_num: int, key: str) -> Any:
        """Get fitness score for specified key."""
        return self._get_trend(trend_num, ("sleepFitnessScore", key, "score"))

    def _get_sleep_score(self, interval_num: int) -> Optional[int]:
        """Return sleep score for a given interval."""
        if len(self.intervals) < interval_num + 1:
            return None
        return self.intervals[interval_num].get("score")

    def _interval_timeseries(self, interval_num: int) -> Dict[str, Any]:
        """Return timeseries interval if it exists."""
        if len(self.intervals) < interval_num + 1:
            return None
        return self.intervals[interval_num].get("timeseries", {})

    def _get_current_interval_property_value(
        self, key: str
    ) -> Optional[Union[float, int]]:
        """Get current property from intervals."""
        if not self.intervals or not self._interval_timeseries(0).get(key):
            return None
        return self._interval_timeseries(0)[key][-1][1]

    def _calculate_interval_data(
        self, interval_num: int, key: str, average_data: bool = True
    ) -> Optional[Union[int, float]]:
        """Calculate interval data."""
        timeseries = self._interval_timeseries(interval_num)
        if timeseries is None:
            return None
        data_list = timeseries.get(key)
        if not data_list:
            return None
        sum = 0
        for entry in data_list:
            sum += entry[1]
        if not average_data:
            return sum
        return sum / len(data_list)

    def _session_date(self, interval_num: int) -> Optional[str]:
        """Get session date for given interval."""
        if (
            len(self.intervals) < interval_num + 1
            or "ts" not in self.intervals[interval_num]
        ):
            return None
        date = datetime.strptime(
            self.intervals[interval_num]["ts"], DATE_TIME_ISO_FORMAT
        )
        return date.replace(tzinfo=ZoneInfo("UTC"))

    def _sleep_breakdown(self, interval_num: int) -> Optional[Dict[str, Any]]:
        """Return durations of sleep stages for given session."""
        if len(self.intervals) < (interval_num + 1) or not self.intervals[
            interval_num
        ].get("stages"):
            return None
        stages = self.intervals[interval_num]["stages"]
        breakdown = {}
        for stage in stages:
            if stage["stage"] in ("out"):
                continue
            if stage["stage"] not in breakdown:
                breakdown[stage["stage"]] = 0
            breakdown[stage["stage"]] += stage["duration"]

        return breakdown

    def _session_processing(self, interval_num: int) -> Optional[bool]:
        """Return processing state of given session."""
        if len(self.intervals) < interval_num + 1:
            return None
        return self.intervals[interval_num].get("incomplete", False)

    @property
    def user_profile(self) -> Optional[Dict[str, Any]]:
        """Return userdata."""
        return self._user_profile

    @property
    def bed_presence(self) -> bool:
        """Return true/false for bed presence."""
        return self.presence

    @property
    def target_heating_level(self) -> Optional[int]:
        """Return target heating/cooling level."""
        return self.device.device_data.get(f"{self.side}TargetHeatingLevel")

    @property
    def heating_level(self) -> Optional[int]:
        """Return heating/cooling level."""
        level = self.device.device_data.get(f"{self.side}HeatingLevel")
        # Update observed low
        if level is not None and level < self.observed_low:
            self.observed_low = level
        return level

    def past_heating_level(self, num) -> int:
        """Return a heating level from the past."""
        if num > 9 or len(self.device.device_data_history) < num + 1:
            return 0

        return self.device.device_data_history[num].get(f"{self.side}HeatingLevel", 0)

    def _now_heating_or_cooling(
        self, target_heating_level_check: bool
    ) -> Optional[bool]:
        """Return true/false if heating or cooling is currently happening."""
        key = f"{self.side}NowHeating"
        if (
            self.target_heating_level is None
            or self.device.device_data.get(key) is None
        ):
            return None
        return self.device.device_data.get(key) and target_heating_level_check

    @property
    def now_heating(self) -> Optional[bool]:
        """Return current heating state."""
        return self._now_heating_or_cooling(self.target_heating_level > 0)

    @property
    def now_cooling(self) -> Optional[bool]:
        """Return current cooling state."""
        return self._now_heating_or_cooling(self.target_heating_level < 0)

    @property
    def heating_remaining(self) -> Optional[int]:
        """Return seconds of heat/cool time remaining."""
        return self.device.device_data.get(f"{self.side}HeatingDuration")

    @property
    def last_seen(self) -> Optional[str]:
        """Return mattress last seen time.

        These values seem to be rarely updated correctly in the API.
        Don't expect accurate results from this property.
        """
        last_seen = self.device.device_data.get(f"{self.side}PresenceEnd")
        if not last_seen:
            return None
        return datetime.fromtimestamp(int(last_seen)).strftime(DATE_TIME_ISO_FORMAT)

    @property
    def heating_values(self) -> Dict[str, Any]:
        """Return a dict of all the current heating values."""
        return {
            "level": self.heating_level,
            "target": self.target_heating_level,
            "active": self.now_heating,
            "remaining": self.heating_remaining,
            "last_seen": self.last_seen,
        }

    @property
    def current_session_date(self) -> Optional[datetime]:
        """Return date/time for start of last session data."""
        return self._session_date(0)

    @property
    def current_session_processing(self) -> Optional[bool]:
        """Return processing state of current session."""
        return self._session_processing(0)

    @property
    def current_sleep_stage(self) -> Optional[str]:
        """Return sleep stage for in-progress session."""
        if (
            not self.intervals
            or not self.intervals[0].get("stages")
            or len(self.intervals[0]["stages"]) < 2
        ):
            return None
        # API now always has an awake state last in the dict
        # so always pull the second to last stage while we are
        # in a processing state
        if self.current_session_processing:
            stage = self.intervals[0]["stages"][-2].get("stage")
        else:
            stage = self.intervals[0]["stages"][-1].get("stage")

        # UNRELIABLE... Removing for now.
        # Check sleep stage against last_seen time to make
        # sure we don't get stuck in a non-awake state.
        # delta_elap = datetime.fromtimestamp(time.time()) \
        #    - datetime.strptime(self.last_seen, 'DATE_TIME_ISO_FORMAT')
        # _LOGGER.debug('User elap: %s', delta_elap.total_seconds())
        # if stage != 'awake' and delta_elap.total_seconds() > 1800:
        # Bed hasn't seen us for 30min so set awake.
        #    stage = 'awake'

        # Second try at forcing awake using heating level
        if (
            stage != "awake"
            and self.heating_level is not None
            and self.heating_level < 5
        ):
            return "awake"
        return stage

    @property
    def current_sleep_score(self) -> Optional[int]:
        """Return sleep score for in-progress session."""
        return self._get_sleep_score(0)

    @property
    def current_sleep_fitness_score(self) -> Optional[int]:
        """Return sleep fitness score for latest session."""
        return self._get_trend(0, ("sleepFitnessScore", "total"))

    @property
    def current_sleep_duration_score(self) -> Optional[int]:
        """Return sleep duration score for latest session."""
        return self._get_fitness_score(0, "sleepDurationSeconds")

    @property
    def current_latency_asleep_score(self) -> Optional[int]:
        """Return latency asleep score for latest session."""
        return self._get_fitness_score(0, "latencyAsleepSeconds")

    @property
    def current_latency_out_score(self) -> Optional[int]:
        """Return latency out score for latest session."""
        return self._get_fitness_score(0, "latencyOutSeconds")

    @property
    def current_wakeup_consistency_score(self) -> Optional[int]:
        """Return wakeup consistency score for latest session."""
        return self._get_fitness_score(0, "wakeupConsistency")

    @property
    def current_fitness_session_date(self) -> Optional[str]:
        """Return date/time for start of last session data."""
        return self._get_trend(0, "day")

    @property
    def current_sleep_breakdown(self) -> Optional[Dict[str, Any]]:
        """Return durations of sleep stages for in-progress session."""
        return self._sleep_breakdown(0)

    @property
    def current_bed_temp(self) -> Optional[Union[int, float]]:
        """Return current bed temperature for in-progress session."""
        return self._get_current_interval_property_value("tempBedC")

    @property
    def current_room_temp(self) -> Optional[Union[int, float]]:
        """Return current room temperature for in-progress session."""
        return self._get_current_interval_property_value("tempRoomC")

    @property
    def current_tnt(self) -> Optional[int]:
        """Return current toss & turns for in-progress session."""
        return cast(
            Optional[int], self._calculate_interval_data(0, "tnt", average_data=False)
        )

    @property
    def current_resp_rate(self) -> Optional[Union[int, float]]:
        """Return current respiratory rate for in-progress session."""
        return self._get_current_interval_property_value("respiratoryRate")

    @property
    def current_heart_rate(self) -> Optional[Union[int, float]]:
        """Return current heart rate for in-progress session."""
        return self._get_current_interval_property_value("heartRate")

    @property
    def current_values(self) -> Dict[str, Any]:
        """Return a dict of all the 'current' parameters."""
        return {
            "date": self.current_session_date,
            "score": self.current_sleep_score,
            "stage": self.current_sleep_stage,
            "breakdown": self.current_sleep_breakdown,
            "tnt": self.current_tnt,
            "bed_temp": self.current_bed_temp,
            "room_temp": self.current_room_temp,
            "resp_rate": self.current_resp_rate,
            "heart_rate": self.current_heart_rate,
            "processing": self.current_session_processing,
        }

    @property
    def current_fitness_values(self) -> Dict[str, Any]:
        """Return a dict of all the 'current' fitness score parameters."""
        return {
            "date": self.current_fitness_session_date,
            "score": self.current_sleep_fitness_score,
            "duration": self.current_sleep_duration_score,
            "asleep": self.current_latency_asleep_score,
            "out": self.current_latency_out_score,
            "wakeup": self.current_wakeup_consistency_score,
        }

    @property
    def last_session_date(self) -> Optional[datetime]:
        """Return date/time for start of last session data."""
        return self._session_date(1)

    @property
    def last_session_processing(self) -> Optional[bool]:
        """Return processing state of current session."""
        return self._session_processing(1)

    @property
    def last_sleep_score(self) -> Optional[int]:
        """Return sleep score from last complete sleep session."""
        return self._get_sleep_score(1)

    @property
    def last_sleep_fitness_score(self) -> Optional[int]:
        """Return sleep fitness score for previous sleep session."""
        return self._get_trend(1, ("sleepFitnessScore", "total"))

    @property
    def last_sleep_duration_score(self) -> Optional[int]:
        """Return sleep duration score for previous session."""
        return self._get_fitness_score(1, "sleepDurationSeconds")

    @property
    def last_latency_asleep_score(self) -> Optional[int]:
        """Return latency asleep score for previous session."""
        return self._get_fitness_score(1, "latencyAsleepSeconds")

    @property
    def last_latency_out_score(self) -> Optional[int]:
        """Return latency out score for previous session."""
        return self._get_fitness_score(1, "latencyOutSeconds")

    @property
    def last_wakeup_consistency_score(self) -> Optional[int]:
        """Return wakeup consistency score for previous session."""
        return self._get_fitness_score(1, "wakeupConsistency")

    @property
    def last_fitness_session_date(self) -> Optional[str]:
        """Return date/time for start of previous session data."""
        return self._get_trend(1, "day")

    @property
    def last_sleep_breakdown(self) -> Optional[Dict[str, Any]]:
        """Return durations of sleep stages for last complete session."""
        return self._sleep_breakdown(1)

    @property
    def last_bed_temp(self) -> Optional[Union[int, float]]:
        """Return avg bed temperature for last session."""
        return self._calculate_interval_data(1, "tempBedC")

    @property
    def last_room_temp(self) -> Optional[Union[int, float]]:
        """Return avg room temperature for last session."""
        return self._calculate_interval_data(1, "tempRoomC")

    @property
    def last_tnt(self) -> Optional[int]:
        """Return toss & turns for last session."""
        return cast(
            Optional[int], self._calculate_interval_data(1, "tnt", average_data=False)
        )

    @property
    def last_resp_rate(self) -> Optional[Union[int, float]]:
        """Return avg respiratory rate for last session."""
        return self._calculate_interval_data(1, "respiratoryRate")

    @property
    def last_heart_rate(self) -> Optional[Union[int, float]]:
        """Return avg heart rate for last session."""
        return self._calculate_interval_data(1, "heartRate")

    @property
    def last_values(self) -> Dict[str, Any]:
        """Return a dict of all the 'last' parameters."""
        return {
            "date": self.last_session_date,
            "score": self.last_sleep_score,
            "breakdown": self.last_sleep_breakdown,
            "tnt": self.last_tnt,
            "bed_temp": self.last_bed_temp,
            "room_temp": self.last_room_temp,
            "resp_rate": self.last_resp_rate,
            "heart_rate": self.last_heart_rate,
            "processing": self.last_session_processing,
        }

    @property
    def last_fitness_values(self) -> Dict[str, Any]:
        """Return a dict of all the 'last' fitness score parameters."""
        return {
            "date": self.last_fitness_session_date,
            "score": self.last_sleep_fitness_score,
            "duration": self.last_sleep_duration_score,
            "asleep": self.last_latency_asleep_score,
            "out": self.last_latency_out_score,
            "wakeup": self.last_wakeup_consistency_score,
        }

    def trend_sleep_score(self, date: str) -> Optional[int]:
        """Return trend sleep score for specified date."""
        return next(
            (day.get("score") for day in self.trends if day.get("day") == date),
            None,
        )

    def sleep_fitness_score(self, date: str) -> Optional[int]:
        """Return sleep fitness score for specified date."""
        return next(
            (
                day.get("sleepFitnessScore", {}).get("total")
                for day in self.trends
                if day.get("day") == date
            ),
            None,
        )

    def heating_stats(self) -> None:
        """Calculate some heating data stats."""
        local_5 = []
        local_10 = []

        for i in range(0, 10):
            level = self.past_heating_level(i)
            if level is None:
                continue
            if level == 0:
                _LOGGER.debug("Cant calculate stats yet...")
                return
            if i < 5:
                local_5.append(level)
            local_10.append(level)

        _LOGGER.debug("%s Heating History: %s", self.side, local_10)

        try:
            # Average of 5min on the history dict.
            fiveminavg = statistics.mean(local_5)
            tenminavg = statistics.mean(local_10)
            _LOGGER.debug("%s Heating 5 min avg: %s", self.side, fiveminavg)
            _LOGGER.debug("%s Heating 10 min avg: %s", self.side, tenminavg)

            # Standard deviation
            fivestdev = statistics.stdev(local_5)
            tenstdev = statistics.stdev(local_10)
            _LOGGER.debug("%s Heating 5 min stdev: %s", self.side, fivestdev)
            _LOGGER.debug("%s Heating 10 min stdev: %s", self.side, tenstdev)

            # Variance
            fivevar = statistics.variance(local_5)
            tenvar = statistics.variance(local_10)
            _LOGGER.debug("%s Heating 5 min variance: %s", self.side, fivevar)
            _LOGGER.debug("%s Heating 10 min variance: %s", self.side, tenvar)
        except statistics.StatisticsError:
            _LOGGER.debug("Cant calculate stats yet...")

        # Other possible options for exploration....
        # Pearson correlation coefficient
        # Spearman rank correlation
        # Kendalls Tau

    def dynamic_presence(self) -> None:
        """
        Determine presence based on bed heating level and end presence
        time reported by the api.

        Idea originated from Alex Lee Yuk Cheung SmartThings Code.
        """

        # self.heating_stats()

        # Method needs to be different for pod since it doesn't rest at 0
        #  - Working idea is to track the low and adjust the scale so that low is 0
        #  - Buffer changes while cooling/heating is active
        if self.target_heating_level is None or self.heating_level is None:
            return
        level_zero = self.observed_low * (-1)
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
                        if self.heating_level + self.target_heating_level >= 8:
                            self.presence = True
                elif working_level > 25:
                    # Catch rising edge
                    if (
                        self.past_heating_level(0) - self.past_heating_level(1) >= 2
                        and self.past_heating_level(1) - self.past_heating_level(2) >= 2
                        and self.past_heating_level(2) - self.past_heating_level(3) >= 2
                    ):
                        # Values are increasing so we are likely in bed
                        if not self.now_heating:
                            self.presence = True
                        elif working_level - self.target_heating_level >= 8:
                            self.presence = True

            elif self.presence:
                if working_level <= 15:
                    # Failsafe, very slow
                    self.presence = False
                elif working_level < 35:  # Threshold is expiremental for now
                    if (
                        self.past_heating_level(0) - self.past_heating_level(1) < 0
                        and self.past_heating_level(1) - self.past_heating_level(2) < 0
                        and self.past_heating_level(2) - self.past_heating_level(3) < 0
                    ):
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
                    if (
                        self.past_heating_level(0) - self.past_heating_level(1) >= 2
                        and self.past_heating_level(1) - self.past_heating_level(2) >= 2
                        and self.past_heating_level(2) - self.past_heating_level(3) >= 2
                    ):
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
                    if (
                        self.past_heating_level(0) - self.past_heating_level(1) < 0
                        and self.past_heating_level(1) - self.past_heating_level(2) < 0
                        and self.past_heating_level(2) - self.past_heating_level(3) < 0
                    ):
                        # Values are decreasing so we are likely out of bed
                        self.presence = False

        # Last seen can lag real-time by up to 35min so this is
        # mostly a backup to using the heat values.
        # seen_delta = datetime.fromtimestamp(time.time()) \
        #     - datetime.strptime(self.last_seen, 'DATE_TIME_ISO_FORMAT')
        # _LOGGER.debug('%s Last seen time delta: %s', self.side,
        #               seen_delta.total_seconds())
        # if self.presence and seen_delta.total_seconds() > 2100:
        #     self.presence = False

        _LOGGER.debug("%s Presence Results: %s", self.side, self.presence)

    async def update_user(self) -> None:
        """Update all user data."""
        await self.update_intervals_data()

        now = datetime.today()
        start = now - timedelta(days=2)
        end = now + timedelta(days=2)

        await self.update_trend_data(
            start.strftime(DATE_FORMAT), end.strftime(DATE_FORMAT)
        )

    async def set_heating_level(self, level: int, duration: int = 0) -> None:
        """Update heating data json."""
        url = f"{API_URL}/devices/{self.device.device_id}"

        # Catch bad low inputs
        if self.device.is_pod:
            level = -100 if level < -100 else level
        else:
            level = 0 if level < 0 else level

        # Catch bad high inputs
        level = 100 if level > 100 else level

        # Duration requests can fail when a schedule is active
        # so form two payloads to ensure level settings succeed
        if self.side == "left":
            data_duration = {"leftHeatingDuration": duration}
            data_level = {"leftTargetHeatingLevel": level}
        elif self.side == "right":
            data_duration = {"rightHeatingDuration": duration}
            data_level = {"rightTargetHeatingLevel": level}

        # Send duration first otherwise the level request will do nothing
        set_heat = await self.device.api_request("put", url, data=data_duration)
        if set_heat is None:
            _LOGGER.error("Unable to set eight heating duration.")
        else:
            # Standard device json is returned after setting
            self.device.handle_device_json(set_heat["device"])

        set_heat = await self.device.api_request("put", url, data=data_level)
        if set_heat is None:
            _LOGGER.error("Unable to set eight heating level.")
        else:
            # Standard device json is returned after setting
            self.device.handle_device_json(set_heat["device"])

    async def update_user_profile(self) -> None:
        """Update user profile data."""
        url = f"{API_URL}/users/{self.user_id}"
        profile_data = await self.device.api_request("get", url)
        if profile_data is None:
            _LOGGER.error("Unable to fetch user profile data for %s", self.user_id)
        else:
            self._user_profile = profile_data["user"]

    async def update_trend_data(self, start_date: str, end_date: str) -> None:
        """Update trends data json for specified time period."""
        url = f"{API_URL}/users/{self.user_id}/trends"
        params = {
            "tz": self.device.tzone,
            "from": start_date,
            "to": end_date,
            # 'include-main': 'true'
        }
        trend_data = await self.device.api_request("get", url, params=params)
        self.trends = trend_data.get("days", [])

    async def update_intervals_data(self) -> None:
        """Update intervals data json for specified time period."""
        url = f"{API_URL}/users/{self.user_id}/intervals"

        intervals = await self.device.api_request("get", url)
        self.intervals = intervals.get("intervals", [])
