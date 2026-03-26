"""
Truth-Poly Pipeline Entry Point

Initialises all services and starts the polling loop.
Monkey-patches truthbrush for proxy/SSL support (must run before auth).
"""

import os
import json
from dotenv import load_dotenv

# Load .env FIRST before any other imports that read env vars
load_dotenv(override=True)


# =============================================================================
# PROXY CONFIGURATION (Optional)
# Format: http://user:pass@host:port or http://host:port
# Only affects Truth Social requests — Polymarket connects directly.
# =============================================================================
PROXY_URL = os.getenv("PROXY_URL")
if PROXY_URL:
    masked = PROXY_URL.split("@")[-1] if "@" in PROXY_URL else PROXY_URL
    print(f"[CONFIG] Proxy enabled for Truth Social: {masked}")


# =============================================================================
# TRUTHBRUSH MONKEY PATCHES
# Must run before any truthbrush auth calls.
#
# 1. Disable rate-limit sleep (truthbrush sleeps 40-50s when remaining <= 50)
# 2. Disable SSL verification for proxy support (BrightData etc.)
# 3. Route requests through PROXY_URL without setting global env vars
# =============================================================================
from truthbrush.api import Api, API_BASE_URL, USER_AGENT, CLIENT_ID, CLIENT_SECRET, BASE_URL, LoginErrorException
from curl_cffi import requests as curl_requests


def _get_proxies():
    """Proxy dict for truthbrush. Uses PROXY_URL, not global env vars."""
    if PROXY_URL:
        return {"http": PROXY_URL, "https": PROXY_URL}
    return {"http": None, "https": None}


def _check_ratelimit_noop(self, resp):
    if resp.headers.get("x-ratelimit-remaining") is not None:
        self.ratelimit_remaining = int(resp.headers.get("x-ratelimit-remaining"))


def _get_with_no_verify(self, url, params=None):
    try:
        resp = self._make_session().get(
            API_BASE_URL + url,
            params=params,
            proxies=_get_proxies(),
            impersonate="chrome136",
            verify=False,
            headers={
                "Authorization": "Bearer " + self.auth_id,
                "User-Agent": USER_AGENT,
            },
        )
    except Exception as e:
        from loguru import logger
        logger.error(f"Curl error: {e}")
        return None
    self._check_ratelimit(resp)
    try:
        return resp.json()
    except json.JSONDecodeError:
        from loguru import logger
        logger.error(f"Failed to decode JSON: {resp.text}")
        return None


def _get_auth_id_with_no_verify(self, username, password):
    url = BASE_URL + "/oauth/v2/token"
    try:
        payload = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "password",
            "username": username,
            "password": password,
            "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
            "scope": "read",
        }
        sess_req = curl_requests.request(
            "POST",
            url,
            json=payload,
            proxies=_get_proxies(),
            impersonate="chrome136",
            verify=False,
            headers={"User-Agent": USER_AGENT},
        )
        sess_req.raise_for_status()
    except Exception as e:
        from loguru import logger
        logger.error(f"Failed login request: {str(e)}")
        raise LoginErrorException("Cannot authenticate to Truth Social.")
    if not sess_req.json()["access_token"]:
        raise ValueError("Invalid truthsocial.com credentials provided!")
    return sess_req.json()["access_token"]


Api._check_ratelimit = _check_ratelimit_noop
Api._get = _get_with_no_verify
Api.get_auth_id = _get_auth_id_with_no_verify

# =============================================================================
# END MONKEY PATCHES — safe to import application modules
# =============================================================================

from src.truth.auth import get_authenticated_account
from src.truth.poller import TruthPoller
from src.analysis.claude_client import ClaudeClient
from src.trading.client import PolymarketClient
from src.trading.executor import OrderExecutor
from src.notifications import telegram
from src.pipeline import process_post


def main():
    # Telegram heartbeat (20 min status pings)
    telegram.start_heartbeat(interval_minutes=20)

    try:
        # Authenticate services
        account = get_authenticated_account()
        claude_client = ClaudeClient(model="claude-3-haiku-20240307")
        poly_client = PolymarketClient.from_env().connect()
        executor = OrderExecutor(poly_client)

        # Polling config
        poll_interval = int(os.getenv("POLL_INTERVAL_MS", "1000"))
        print(f"\n[CONFIG] Poll interval: {poll_interval}ms")

        # Create poller and start
        poller = TruthPoller(account=account, poll_interval_ms=poll_interval)
        poller.start(
            username="realDonaldTrump",
            on_new_post=lambda post: process_post(post, claude_client, executor),
        )
    except Exception as e:
        telegram.send(f"💀 BOT CRASHED\n\n{type(e).__name__}: {str(e)[:200]}")
        raise


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        telegram.send(f"💀 FATAL CRASH\n\n{e}")
        raise