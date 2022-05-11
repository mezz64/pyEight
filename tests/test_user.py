"""Tests for the eight module."""
from datetime import datetime
from zoneinfo import ZoneInfo

from pyeight.eight import EightSleep
from pyeight.user import EightUser


async def test_update_user_data(client_session):
    """Test update user data."""
    eight = EightSleep(
        "raman325@gmail.com", "password", "UTC", client_session=client_session
    )
    await eight.start()
    await eight.update_device_data()
    await eight.update_user_data()

    user: EightUser = eight.users["e9e8a0c020a1159cc0549e189f6d4a15"]

    assert user.bed_presence is False
    assert user.target_heating_level == 0
    assert user.heating_level == -32
    assert user.now_heating is False
    assert user.now_cooling is False
    assert user.heating_remaining == 0
    assert user.last_seen is None
    assert user.heating_values == {
        "level": -32,
        "target": 0,
        "active": False,
        "remaining": 0,
        "last_seen": None,
    }
    assert user.current_session_date == datetime(
        2022, 3, 21, 19, 8, tzinfo=ZoneInfo("UTC")
    )
    assert user.current_session_processing is False
    assert user.current_sleep_stage == "awake"
    assert user.current_sleep_score == 38
    assert user.current_sleep_fitness_score == 42
    assert user.current_sleep_duration_score == 0
    assert user.current_latency_asleep_score == 53
    assert user.current_latency_out_score == 100
    assert user.current_wakeup_consistency_score == 70
    assert user.current_fitness_session_date == "2022-03-22"
    assert user.current_sleep_breakdown == {
        "awake": 4800,
        "deep": 1800,
        "light": 4620,
        "rem": 900,
    }
    assert user.current_bed_temp == 31.88836734693878
    assert user.current_room_temp == 21.948437500000008
    assert user.current_tnt == 3
    assert user.current_resp_rate == 12
    assert user.current_heart_rate == 79.33333333333333
    assert user.current_values == {
        "bed_temp": 31.88836734693878,
        "breakdown": {"awake": 4800, "deep": 1800, "light": 4620, "rem": 900},
        "date": datetime(2022, 3, 21, 19, 8, tzinfo=ZoneInfo("UTC")),
        "heart_rate": 79.33333333333333,
        "processing": False,
        "resp_rate": 12,
        "room_temp": 21.948437500000008,
        "score": 38,
        "stage": "awake",
        "tnt": 3,
    }
    assert user.current_fitness_values == {
        "date": "2022-03-22",
        "asleep": 53,
        "duration": 0,
        "out": 100,
        "score": 42,
        "wakeup": 70,
    }
    assert user.last_session_date == datetime(
        2022, 3, 21, 4, 12, tzinfo=ZoneInfo("UTC")
    )
    assert user.last_session_processing is False
    assert user.last_sleep_score == 79
    assert user.last_sleep_breakdown == {
        "awake": 7020,
        "deep": 5100,
        "light": 13800,
        "rem": 6000,
    }
    assert user.last_bed_temp == 31.35841704204205
    assert user.last_room_temp == 20.88696886772881
    assert user.last_tnt == 10
    assert user.last_resp_rate == 11.63730158730159
    assert user.last_heart_rate == 73.14141414141415
    assert user.last_values == {
        "bed_temp": 31.35841704204205,
        "breakdown": {"awake": 7020, "deep": 5100, "light": 13800, "rem": 6000},
        "date": datetime(2022, 3, 21, 4, 12, tzinfo=ZoneInfo("UTC")),
        "heart_rate": 73.14141414141415,
        "processing": False,
        "resp_rate": 11.63730158730159,
        "room_temp": 20.88696886772881,
        "score": 79,
        "tnt": 10,
    }
    assert user.trend_sleep_score("2022-03-22") == 53
    assert user.trend_sleep_score("2020-03-22") is None
    assert user.sleep_fitness_score("2022-03-22") == 42
    assert user.sleep_fitness_score("2020-03-22") is None

    assert user.past_heating_level(1) == 0
    # We should now have a past heating level
    await eight.update_device_data()
    assert user.past_heating_level(1) == -32

    await eight.stop()


async def test_update_user_data_missing_data(client_session_missing_data):
    """Test update user data with missing data."""
    eight = EightSleep(
        "raman325@gmail.com",
        "password",
        "UTC",
        client_session=client_session_missing_data,
    )
    await eight.start()
    await eight.update_device_data()
    await eight.update_user_data()

    user = eight.users["e9e8a0c020a1159cc0549e189f6d4a15"]

    assert user.bed_presence is False
    assert user.current_session_date is None
    assert user.current_session_processing is False
    assert user.current_sleep_stage is None
    assert user.current_sleep_score is None
    assert user.current_sleep_fitness_score is None
    assert user.current_sleep_duration_score is None
    assert user.current_latency_asleep_score is None
    assert user.current_latency_out_score is None
    assert user.current_wakeup_consistency_score is None
    assert user.current_fitness_session_date is None
    assert user.current_sleep_breakdown is None
    assert user.current_bed_temp is None
    assert user.current_room_temp is None
    assert user.current_tnt is None
    assert user.current_resp_rate is None
    assert user.current_heart_rate is None
