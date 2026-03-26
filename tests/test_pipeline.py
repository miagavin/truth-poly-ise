"""
Tests for src.pipeline — end-to-end post processing.

All external services (Claude, Polymarket, Telegram) are mocked.
No API keys or network required.
"""

import sys
from unittest.mock import MagicMock, patch

# Mock external packages before imports
sys.modules.setdefault("truthbrush", MagicMock())
sys.modules.setdefault("truthbrush.api", MagicMock())
sys.modules.setdefault("anthropic", MagicMock())
sys.modules.setdefault("py_clob_client", MagicMock())
sys.modules.setdefault("py_clob_client.client", MagicMock())
sys.modules.setdefault("py_clob_client.order_builder", MagicMock())
sys.modules.setdefault("py_clob_client.order_builder.constants", MagicMock())
sys.modules.setdefault("py_clob_client.clob_types", MagicMock())

import pytest
from src.pipeline import process_post
from src.trading.candidates import CANDIDATES, DEFAULT_BUY_AMOUNT, DEFAULT_NO_AMOUNT


# ── Helpers ──────────────────────────────────────────────────────────────────

def _post(content: str) -> dict:
    return {"id": "1", "content": content}


def _mock_claude(response: str) -> MagicMock:
    """Create a mock ClaudeClient that returns the given response."""
    client = MagicMock()
    client.send_message.return_value = response
    return client


def _mock_executor() -> MagicMock:
    """Create a mock OrderExecutor that records calls."""
    executor = MagicMock()
    executor.market_buy.return_value = MagicMock(success=True)
    return executor


# ── Filtered out (no keywords) ──────────────────────────────────────────────

class TestFilteredOut:
    """Posts without keywords should never reach Claude or the executor."""

    @patch("src.pipeline.telegram")
    def test_irrelevant_post_skips_everything(self, mock_tg):
        claude = _mock_claude("should not be called")
        executor = _mock_executor()

        decision = process_post(_post("Great golf today!"), claude, executor)

        assert not decision.should_trade
        claude.send_message.assert_not_called()
        executor.market_buy.assert_not_called()

    @patch("src.pipeline.telegram")
    def test_empty_post_skips_everything(self, mock_tg):
        decision = process_post(_post(""), _mock_claude("x"), _mock_executor())
        assert not decision.should_trade


# ── No nomination ────────────────────────────────────────────────────────────

class TestNoNomination:
    """Posts with keywords but Claude says 'No nomination' → no trade."""

    @patch("src.pipeline.telegram")
    def test_no_nomination_no_trade(self, mock_tg):
        post = _post("The Fed Chair is doing a terrible job!")
        claude = _mock_claude("No nomination")
        executor = _mock_executor()

        decision = process_post(post, claude, executor)

        assert not decision.should_trade
        claude.send_message.assert_called_once()
        executor.market_buy.assert_not_called()


# ── Known candidate → YES buy ───────────────────────────────────────────────

class TestKnownCandidate:
    """Claude returns a known candidate name → buy YES on that candidate."""

    @patch("src.pipeline.telegram")
    def test_kevin_warsh_buys_yes(self, mock_tg):
        post = _post("I am nominating Kevin Warsh as Fed Chair!")
        claude = _mock_claude("Kevin Warsh")
        executor = _mock_executor()

        decision = process_post(post, claude, executor)

        assert decision.should_trade
        assert len(decision.actions) == 1
        assert decision.actions[0].side == "YES"
        executor.market_buy.assert_called_once_with(
            token_id=CANDIDATES["kevin warsh"].yes,
            amount_usd=DEFAULT_BUY_AMOUNT,
        )

    @patch("src.pipeline.telegram")
    def test_rick_rieder_buys_yes(self, mock_tg):
        post = _post("I have chosen Rick Rieder for the Federal Reserve!")
        claude = _mock_claude("Rick Rieder")
        executor = _mock_executor()

        decision = process_post(post, claude, executor)

        executor.market_buy.assert_called_once_with(
            token_id=CANDIDATES["rick rieder"].yes,
            amount_usd=DEFAULT_BUY_AMOUNT,
        )

    @patch("src.pipeline.telegram")
    def test_all_known_candidates(self, mock_tg):
        """Every candidate in the registry should produce a YES buy."""
        for name, tokens in CANDIDATES.items():
            post = _post(f"I nominate {name.title()} as Fed Chair")
            claude = _mock_claude(name.title())
            executor = _mock_executor()

            decision = process_post(post, claude, executor)

            assert decision.should_trade
            executor.market_buy.assert_called_once_with(
                token_id=tokens.yes,
                amount_usd=DEFAULT_BUY_AMOUNT,
            )


# ── Unknown valid name → NO on all frontrunners ─────────────────────────────

class TestUnknownCandidate:
    """Claude returns a valid name not in our registry → buy NO on all."""

    @patch("src.pipeline.telegram")
    def test_unknown_name_buys_no_on_all(self, mock_tg):
        post = _post("I am nominating Judy Shelton as Fed Chair!")
        claude = _mock_claude("Judy Shelton")
        executor = _mock_executor()

        decision = process_post(post, claude, executor)

        assert decision.should_trade
        assert len(decision.actions) == len(CANDIDATES)
        assert all(a.side == "NO" for a in decision.actions)
        assert executor.market_buy.call_count == len(CANDIDATES)


# ── Junk response → no trade ────────────────────────────────────────────────

class TestJunkResponse:
    """Malformed Claude output should not trigger any trades."""

    @patch("src.pipeline.telegram")
    def test_empty_claude_response_no_trade(self, mock_tg):
        post = _post("The Fed Chair announcement is coming")
        claude = _mock_claude("")
        executor = _mock_executor()

        decision = process_post(post, claude, executor)

        assert not decision.should_trade
        executor.market_buy.assert_not_called()

    @patch("src.pipeline.telegram")
    def test_sentence_response_no_trade(self, mock_tg):
        post = _post("I will nominate the best person for Fed Chair")
        claude = _mock_claude("I think Kevin Warsh would be great")
        executor = _mock_executor()

        decision = process_post(post, claude, executor)

        assert not decision.should_trade
        executor.market_buy.assert_not_called()


# ── Trade execution errors ──────────────────────────────────────────────────

class TestExecutionErrors:
    """Executor failures should not crash the pipeline."""

    @patch("src.pipeline.telegram")
    def test_executor_exception_doesnt_crash(self, mock_tg):
        post = _post("I am nominating Kevin Warsh as Fed Chair!")
        claude = _mock_claude("Kevin Warsh")
        executor = _mock_executor()
        executor.market_buy.side_effect = Exception("insufficient funds")

        # Should not raise
        decision = process_post(post, claude, executor)

        assert decision.should_trade
        executor.market_buy.assert_called_once()

    @patch("src.pipeline.telegram")
    def test_partial_failure_continues(self, mock_tg):
        """If one NO trade fails, the rest should still attempt."""
        post = _post("I am nominating Judy Shelton as Fed Chair!")
        claude = _mock_claude("Judy Shelton")
        executor = _mock_executor()

        # First call fails, rest succeed
        executor.market_buy.side_effect = [
            Exception("timeout"),
            MagicMock(success=True),
            MagicMock(success=True),
            MagicMock(success=True),
        ]

        decision = process_post(post, claude, executor)

        # All 4 NO trades should have been attempted
        assert executor.market_buy.call_count == len(CANDIDATES)


# ── Telegram notifications ──────────────────────────────────────────────────

class TestNotifications:
    """Verify Telegram is called at appropriate points."""

    @patch("src.pipeline.telegram")
    def test_keyword_match_sends_alert(self, mock_tg):
        post = _post("The Fed Chair will be announced soon")
        claude = _mock_claude("No nomination")
        executor = _mock_executor()

        process_post(post, claude, executor)

        mock_tg.send_async.assert_called()  # At least the keyword alert

    @patch("src.pipeline.telegram")
    def test_successful_trade_sends_notification(self, mock_tg):
        post = _post("I am nominating Kevin Warsh as Fed Chair!")
        claude = _mock_claude("Kevin Warsh")
        executor = _mock_executor()

        process_post(post, claude, executor)

        # Should have keyword alert + trade notification
        assert mock_tg.send_async.call_count >= 2

    @patch("src.pipeline.telegram")
    def test_no_keywords_no_telegram(self, mock_tg):
        post = _post("Beautiful day at Mar-a-Lago!")
        process_post(post, _mock_claude("x"), _mock_executor())

        mock_tg.send_async.assert_not_called()