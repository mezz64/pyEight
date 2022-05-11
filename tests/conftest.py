"""Provide common pytest fixtures."""
import pathlib
from unittest.mock import patch

from aiohttp import test_utils, web, ClientSession
import pytest


def load_fixture(name: str):
    """Load a fixture."""
    return (pathlib.Path(__file__).parent / "fixtures" / name).read_text()


def handler_factory(filename: str):
    """Return a handler that returns a fixture."""

    async def handler(_: web.Request):
        return web.Response(
            headers={"content-type": "application/json"},
            text=load_fixture(f"{filename}.json"),
        )

    return handler


def _server(device_info: str, user_trends: str, user_intervals: str):
    app = web.Application()
    app.add_routes(
        [
            web.post("/login", handler_factory("login")),
            web.get("/users/me", handler_factory("logged_in_user_profile")),
            web.get("/devices/{device_id}", handler_factory(device_info)),
            web.get(
                "/users/389e711791e70fe16c54ce166ad8f3eb",
                handler_factory("logged_in_user_profile"),
            ),
            web.get(
                "/users/e9e8a0c020a1159cc0549e189f6d4a15",
                handler_factory("partner_user_profile"),
            ),
            web.get("/users/{user_id}/trends", handler_factory(user_trends)),
            web.get("/users/{user_id}/intervals", handler_factory(user_intervals)),
        ]
    )
    return test_utils.TestServer(app)


@pytest.fixture(name="client_session")
async def client_session_fixture():
    async with _server(
        "device_info", "user_trends", "user_intervals"
    ) as server, ClientSession() as session:
        new_url = f"http://localhost:{server.port}"
        with patch("pyeight.eight.API_URL", new_url), patch(
            "pyeight.user.API_URL", new_url
        ):
            yield session


@pytest.fixture(name="client_session_missing_data")
async def client_session_missing_data_fixture():
    async with _server(
        "device_info", "empty_user_trends", "empty_user_intervals"
    ) as server, ClientSession() as session:
        new_url = f"http://localhost:{server.port}"
        with patch("pyeight.eight.API_URL", new_url), patch(
            "pyeight.user.API_URL", new_url
        ):
            yield session
