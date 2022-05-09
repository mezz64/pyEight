"""Tests for the eight module."""
from pyeight.eight import EightSleep


async def test_setup(client_session):
    """Test the setup of the eight module."""
    eight = EightSleep(
        "raman325@gmail.com", "password", "UTC", client_session=client_session
    )
    await eight.start()
    assert eight.token == "fake_token"
    assert eight.deviceid == "98c53f17408384ffd6329fd1"
    assert eight.is_pod
    assert len(eight.users) == 2
    assert eight.userids is not None
    assert eight.userids in eight.users

    await eight.stop()
    # Assert that the client session is not closed since we created it outside the lib
    assert not client_session.closed


async def test_update_device_data(client_session):
    """Test update device data."""
    eight = EightSleep(
        "raman325@gmail.com", "password", "UTC", client_session=client_session
    )
    await eight.start()
    await eight.update_device_data()
    assert eight.device_data is not None
    assert len(eight.device_data_history) == 10
    assert eight.device_data_history[0] is not None
    for i in range(1, 10):
        assert eight.device_data_history[i] is None

    assert eight.fetch_userid("left") == "389e711791e70fe16c54ce166ad8f3eb"

    # Assert that trend and interval data is empty until we update user data
    for user in eight.users.values():
        assert user.user_profile is not None
        assert user.trends is None
        assert user.intervals is None

    # Assert thtat trend and interval data is now not empty
    await eight.update_user_data()
    for user in eight.users.values():
        assert user.trends is not None
        assert user.intervals is not None

    assert eight.room_temperature() == 21.948437500000008

    await eight.stop()
    # Assert that the client session is not closed since we created it outside the lib
    assert not client_session.closed
