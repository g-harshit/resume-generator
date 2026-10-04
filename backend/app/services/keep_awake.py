"""Stop Render's free plan from putting the API to sleep.

A free Render web service sleeps after 15 minutes without inbound traffic, and
the next visitor waits up to a minute while it wakes ("Signing in…" that never
seems to end). This loop requests the service's *own public URL* every ten
minutes. The request leaves the instance and comes back in through Render's
proxy, which is where idle time is measured, so it counts as traffic; pinging
localhost would not.

Why not only the GitHub Actions ping (.github/workflows/keep-api-awake.yml)?
GitHub runs scheduled workflows on a best-effort basis: a `*/10` schedule ran
every 2–6 hours (Oct 2026). It stays, as a backstop from outside that wakes the
service if this loop ever dies with it asleep. Same approach as Signal.

The hour budget: Render grants 750 free instance-hours per workspace per month;
an always-on service uses at most 744. That fits only while this is the one free
service in the workspace drawing hours (the static website doesn't). Add another
free web service there and the pool runs out — then Render suspends every free
service until the 1st. Moving this one to a paid instance removes the problem
(and this loop becomes unnecessary, though harmless).
"""

import asyncio
import logging
import os
import urllib.error
import urllib.request

from app.config import get_settings

# Uvicorn's logger: shown at INFO in the service logs, where the app's own isn't.
log = logging.getLogger("uvicorn.error")

# Ten minutes leaves room for one slow or failed ping inside Render's fifteen.
INTERVAL_SECONDS = 10 * 60
TIMEOUT_SECONDS = 30


def target_url() -> str | None:
    """The URL to ping, or None to not run at all.

    `KEEP_AWAKE_URL` wins if set; otherwise `RENDER_EXTERNAL_URL`, which Render sets
    on every web service — so this is on in production with no config, and off in
    development and tests, where neither exists. `KEEP_AWAKE=false` turns it off."""
    s = get_settings()
    if not s.keep_awake:
        return None
    base = (s.keep_awake_url or os.environ.get("RENDER_EXTERNAL_URL", "")).strip().rstrip("/")
    return f"{base}/health" if base else None


def ping_once(url: str) -> bool:
    """One ping. Never raises: a missed ping is logged, and the next one still has
    five minutes of slack before Render would sleep."""
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
            ok = response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        log.warning("keep-awake ping to %s failed: %s", url, exc)
        return False
    if not ok:
        log.warning("keep-awake ping to %s returned %s", url, response.status)
    return ok


async def ping_forever(url: str, interval: float = INTERVAL_SECONDS) -> None:
    """For the life of the process. Sleeps first: a service that has just started
    has just had traffic (the deploy's health check, or the request that woke it)."""
    log.info("keep-awake: pinging %s every %s seconds", url, int(interval))
    while True:
        await asyncio.sleep(interval)
        await asyncio.to_thread(ping_once, url)
