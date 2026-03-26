"""
Tests for src.truth.poller — Truth Social polling logic.

All tests mock the truthbrush API — no network or credentials required.
"""

import sys
from unittest.mock import MagicMock

# Mock truthbrush before importing our modules — the real package
# isn't needed for testing poller logic.
sys.modules.setdefault("truthbrush", MagicMock())
sys.modules.setdefault("truthbrush.api", MagicMock())

from src.truth.poller import TruthPoller
from src.truth.auth import AuthenticatedAccount, AccountCredentials


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_poller(posts_sequence: list[list[dict]]) -> TruthPoller:
    """
    Create a TruthPoller with a mocked API that returns posts_sequence
    on successive calls to pull_statuses.

    Each element in posts_sequence is a list of post dicts that will be
    returned as an iterator for one call to pull_statuses.
    """
    mock_api = MagicMock()
    # pull_statuses is called as an iterator — side_effect returns one list per call
    mock_api.pull_statuses.side_effect = [iter(posts) for posts in posts_sequence]

    creds = AccountCredentials(username="testuser", password="testpass")
    account = AuthenticatedAccount(credentials=creds, api=mock_api)

    return TruthPoller(account=account, poll_interval_ms=100)


def _post(id: str, content: str = "test") -> dict:
    return {"id": id, "content": content}


# ── Baseline behaviour ───────────────────────────────────────────────────────

class TestBaseline:
    """First poll should set baseline and return no new posts."""

    def test_first_poll_sets_baseline(self):
        poller = _make_poller([
            [_post("100", "first post")],
        ])
        result = poller.poll_once("realDonaldTrump")
        assert result == []
        assert poller.last_seen_id == "100"

    def test_first_poll_empty_feed(self):
        poller = _make_poller([[]])
        result = poller.poll_once("realDonaldTrump")
        assert result == []
        assert poller.last_seen_id is None


# ── New post detection ───────────────────────────────────────────────────────

class TestNewPosts:
    """After baseline, new posts should be returned."""

    def test_detects_single_new_post(self):
        poller = _make_poller([
            [_post("100")],           # baseline
            [_post("101", "new!")],    # new post
        ])
        poller.poll_once("realDonaldTrump")  # baseline
        result = poller.poll_once("realDonaldTrump")
        assert len(result) == 1
        assert result[0]["id"] == "101"

    def test_detects_multiple_new_posts(self):
        poller = _make_poller([
            [_post("100")],
            [_post("102"), _post("101")],
        ])
        poller.poll_once("realDonaldTrump")
        result = poller.poll_once("realDonaldTrump")
        assert len(result) == 2

    def test_no_new_posts_returns_empty(self):
        poller = _make_poller([
            [_post("100")],
            [],
        ])
        poller.poll_once("realDonaldTrump")
        result = poller.poll_once("realDonaldTrump")
        assert result == []


# ── ID tracking ──────────────────────────────────────────────────────────────

class TestIDTracking:
    """last_seen_id should always advance to the highest post ID."""

    def test_tracks_highest_id(self):
        poller = _make_poller([
            [_post("100")],
            [_post("103"), _post("101"), _post("102")],
        ])
        poller.poll_once("realDonaldTrump")
        poller.poll_once("realDonaldTrump")
        assert poller.last_seen_id == "103"

    def test_id_does_not_regress_on_empty_poll(self):
        poller = _make_poller([
            [_post("100")],
            [_post("105")],
            [],
        ])
        poller.poll_once("realDonaldTrump")
        poller.poll_once("realDonaldTrump")
        assert poller.last_seen_id == "105"
        poller.poll_once("realDonaldTrump")
        assert poller.last_seen_id == "105"  # unchanged

    def test_since_id_passed_to_api(self):
        poller = _make_poller([
            [_post("100")],
            [],
        ])
        poller.poll_once("realDonaldTrump")
        poller.poll_once("realDonaldTrump")

        # Second call should have since_id="100"
        calls = poller.account.api.pull_statuses.call_args_list
        assert len(calls) == 2
        assert calls[1].kwargs.get("since_id") == "100" or calls[1][1].get("since_id") == "100"


# ── Error handling ───────────────────────────────────────────────────────────

class TestErrorHandling:
    """Errors should be caught and return empty list, not crash."""

    def test_502_returns_empty(self):
        mock_api = MagicMock()
        mock_api.pull_statuses.side_effect = Exception("502 Bad Gateway")

        creds = AccountCredentials(username="testuser", password="testpass")
        account = AuthenticatedAccount(credentials=creds, api=mock_api)
        poller = TruthPoller(account=account, poll_interval_ms=100)
        poller.last_seen_id = "100"  # skip baseline

        result = poller.poll_once("realDonaldTrump")
        assert result == []

    def test_nonetype_error_returns_empty(self):
        mock_api = MagicMock()
        mock_api.pull_statuses.side_effect = TypeError("'NoneType' object is not iterable")

        creds = AccountCredentials(username="testuser", password="testpass")
        account = AuthenticatedAccount(credentials=creds, api=mock_api)
        poller = TruthPoller(account=account, poll_interval_ms=100)
        poller.last_seen_id = "100"

        result = poller.poll_once("realDonaldTrump")
        assert result == []

    def test_generic_error_returns_empty(self):
        mock_api = MagicMock()
        mock_api.pull_statuses.side_effect = RuntimeError("connection reset")

        creds = AccountCredentials(username="testuser", password="testpass")
        account = AuthenticatedAccount(credentials=creds, api=mock_api)
        poller = TruthPoller(account=account, poll_interval_ms=100)
        poller.last_seen_id = "100"

        result = poller.poll_once("realDonaldTrump")
        assert result == []


# ── Polling loop ─────────────────────────────────────────────────────────────

class TestPollingLoop:
    """Test the start/stop loop mechanics."""

    def test_stop_ends_loop(self):
        """Calling stop() should break the while loop."""
        mock_api = MagicMock()
        creds = AccountCredentials(username="testuser", password="testpass")
        account = AuthenticatedAccount(credentials=creds, api=mock_api)
        poller = TruthPoller(account=account, poll_interval_ms=10)

        collected = []
        call_num = [0]

        def fake_pull(**kwargs):
            call_num[0] += 1
            if call_num[0] == 1:
                return iter([_post("100")])  # baseline
            elif call_num[0] == 2:
                return iter([_post("101", "new!")])  # new post
            else:
                return iter([])

        mock_api.pull_statuses.side_effect = fake_pull

        def callback(post):
            collected.append(post)
            poller.stop()

        poller.start("realDonaldTrump", on_new_post=callback)

        assert not poller.running
        assert len(collected) == 1
        assert collected[0]["id"] == "101"

    def test_poll_count_increments(self):
        mock_api = MagicMock()
        creds = AccountCredentials(username="testuser", password="testpass")
        account = AuthenticatedAccount(credentials=creds, api=mock_api)
        poller = TruthPoller(account=account, poll_interval_ms=10)

        call_num = [0]

        def fake_pull(**kwargs):
            call_num[0] += 1
            if call_num[0] == 1:
                return iter([_post("100")])  # baseline
            else:
                return iter([])

        mock_api.pull_statuses.side_effect = fake_pull

        def callback(post):
            pass  # no-op

        # Stop after 3 polls via a side-effect check
        original_poll = poller.poll_once

        def poll_with_stop(username):
            result = original_poll(username)
            if poller.poll_count >= 3:
                poller.stop()
            return result

        poller.poll_once = poll_with_stop
        poller.start("realDonaldTrump", on_new_post=callback)
        # poll_count may overshoot by 1 since increment happens before stop takes effect
        assert poller.poll_count >= 3