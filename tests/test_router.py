"""
Tests for src.trading.router — Claude response → trade decision mapping.

All tests are pure functions, no API keys or network required.
"""

import pytest
from src.trading.router import route, TradeDecision, TradeAction
from src.trading.candidates import CANDIDATES, DEFAULT_BUY_AMOUNT, DEFAULT_NO_AMOUNT


# ── No nomination ────────────────────────────────────────────────────────────

class TestNoNomination:
    def test_exact_no_nomination(self):
        decision = route("No nomination")
        assert not decision.should_trade
        assert decision.actions == []

    def test_no_nomination_case_insensitive(self):
        decision = route("no nomination")
        assert not decision.should_trade

    def test_no_nomination_with_whitespace(self):
        decision = route("  No nomination  ")
        assert not decision.should_trade

    def test_no_nomination_with_newline(self):
        decision = route("No nomination\n")
        assert not decision.should_trade


# ── Known candidate matching ─────────────────────────────────────────────────

class TestKnownCandidates:
    """Each known candidate should produce a single YES buy."""

    @pytest.mark.parametrize("name", list(CANDIDATES.keys()))
    def test_known_candidate_produces_one_action(self, name):
        decision = route(name.title())  # e.g. "Kevin Warsh"
        assert decision.should_trade
        assert len(decision.actions) == 1

    @pytest.mark.parametrize("name", list(CANDIDATES.keys()))
    def test_known_candidate_buys_yes(self, name):
        decision = route(name.title())
        action = decision.actions[0]
        assert action.side == "YES"
        assert action.token_id == CANDIDATES[name].yes

    @pytest.mark.parametrize("name", list(CANDIDATES.keys()))
    def test_known_candidate_uses_default_amount(self, name):
        decision = route(name.title())
        assert decision.actions[0].amount_usd == DEFAULT_BUY_AMOUNT

    def test_kevin_warsh_specifically(self):
        decision = route("Kevin Warsh")
        action = decision.actions[0]
        assert action.candidate == "Kevin Warsh"
        assert action.token_id == CANDIDATES["kevin warsh"].yes

    def test_rick_rieder_specifically(self):
        decision = route("Rick Rieder")
        action = decision.actions[0]
        assert action.candidate == "Rick Rieder"
        assert action.token_id == CANDIDATES["rick rieder"].yes

    def test_case_insensitive_matching(self):
        decision = route("KEVIN WARSH")
        assert decision.should_trade
        assert decision.actions[0].side == "YES"

    def test_mixed_case(self):
        decision = route("kevin HASSETT")
        assert decision.should_trade

    def test_extra_whitespace(self):
        decision = route("  Christopher Waller  ")
        assert decision.should_trade
        assert decision.actions[0].side == "YES"


# ── Unknown candidate (buy NO on all) ───────────────────────────────────────

class TestUnknownValidName:
    """A name not in our candidates dict but clearly a 'Firstname Lastname'
    means a real nomination for someone else — buy NO on all frontrunners."""

    def test_unknown_candidate_triggers_no_buys(self):
        decision = route("Judy Shelton")
        assert decision.should_trade
        assert len(decision.actions) == len(CANDIDATES)

    def test_unknown_candidate_all_no_side(self):
        decision = route("Judy Shelton")
        assert all(a.side == "NO" for a in decision.actions)

    def test_unknown_uses_no_token_ids(self):
        decision = route("Stephen Miran")
        expected_ids = {t.no for t in CANDIDATES.values()}
        actual_ids = {a.token_id for a in decision.actions}
        assert actual_ids == expected_ids

    def test_unknown_uses_default_no_amount(self):
        decision = route("Michelle Bowman")
        assert all(a.amount_usd == DEFAULT_NO_AMOUNT for a in decision.actions)

    def test_completely_unknown_name_triggers_no(self):
        decision = route("John Smith")
        assert decision.should_trade
        assert all(a.side == "NO" for a in decision.actions)

    def test_three_word_name(self):
        decision = route("Mary Jane Watson")
        assert decision.should_trade

    def test_reason_includes_original_name(self):
        decision = route("Judy Shelton")
        assert "Judy Shelton" in decision.reason


# ── Junk / malformed responses (should NOT trade) ───────────────────────────

class TestJunkResponse:
    """Garbage, partial text, empty strings, or sentences should never
    trigger trades — only confident signals."""

    def test_empty_string_no_trade(self):
        decision = route("")
        assert not decision.should_trade

    def test_whitespace_only_no_trade(self):
        decision = route("   \n  ")
        assert not decision.should_trade

    def test_single_word_no_trade(self):
        """A single word like 'Kevin' is not a valid name response."""
        decision = route("Kevin")
        assert not decision.should_trade

    def test_sentence_no_trade(self):
        decision = route("I think Kevin Warsh would be a great pick")
        assert not decision.should_trade

    def test_malformed_with_punctuation_no_trade(self):
        decision = route("Kevin Warsh!")
        assert not decision.should_trade

    def test_number_no_trade(self):
        decision = route("404")
        assert not decision.should_trade