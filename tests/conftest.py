"""Provide common pytest fixtures."""
from unittest.mock import patch

import aiohttp
from aiohttp import test_utils, web
import pytest

from . import load_fixture

# pylint: disable=protected-access, unused-argument


def handler_factory(filename: str):
    """Return a handler that returns a fixture."""

    async def handler(request: web.Request):
        return web.Response(
            headers={"content-type": "application/json"},
            text=load_fixture(f"{filename}.json"),
        )

    return handler


@pytest.fixture(name="client_session")
async def client_session_fixture(aiohttp_client):
    app = web.Application()
    app.add_routes(
        [
            web.post("/login", handler_factory("login")),
            web.get("/users/me", handler_factory("logged_in_user_profile")),
            web.get("/devices/{device_id}", handler_factory("device_info")),
            web.get(
                "/users/389e711791e70fe16c54ce166ad8f3eb",
                handler_factory("logged_in_user_profile"),
            ),
            web.get(
                "/users/e9e8a0c020a1159cc0549e189f6d4a15",
                handler_factory("partner_user_profile"),
            ),
            web.get("/users/{user_id}/trends", handler_factory("user_trends")),
            web.get("/users/{user_id}/intervals", handler_factory("user_intervals")),
        ]
    )
    server = test_utils.TestServer(app)
    async with server, aiohttp.ClientSession() as session:
        new_url = f"http://localhost:{server.port}"
        with patch("pyeight.eight.API_URL", new_url), patch(
            "pyeight.user.API_URL", new_url
        ):
            yield session

