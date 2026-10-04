"""Keeping the API awake on Render's free plan: on only where there's a public URL."""

import asyncio

import pytest

from app.config import get_settings
from app.services import keep_awake


def test_off_in_development_and_tests(monkeypatch):
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    monkeypatch.setattr(get_settings(), "keep_awake_url", "")
    assert keep_awake.target_url() is None


def test_on_at_render_with_no_config(monkeypatch):
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://quickfitcv-api.onrender.com/")
    assert keep_awake.target_url() == "https://quickfitcv-api.onrender.com/health"


def test_an_explicit_url_wins_and_it_can_be_turned_off(monkeypatch):
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://x.onrender.com")
    monkeypatch.setattr(get_settings(), "keep_awake_url", "https://api.quickfitcv.com")
    assert keep_awake.target_url() == "https://api.quickfitcv.com/health"
    monkeypatch.setattr(get_settings(), "keep_awake", False)
    assert keep_awake.target_url() is None


def test_a_failed_ping_is_logged_not_raised():
    # Nothing listens on port 9 (discard); the ping fails fast and quietly.
    assert keep_awake.ping_once("http://127.0.0.1:9/health") is False


def test_the_loop_pings_on_its_interval(monkeypatch):
    pinged = []
    monkeypatch.setattr(keep_awake, "ping_once", lambda url: pinged.append(url) or True)

    async def run():
        task = asyncio.create_task(keep_awake.ping_forever("https://api/health", interval=0.01))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert len(pinged) >= 2 and set(pinged) == {"https://api/health"}
