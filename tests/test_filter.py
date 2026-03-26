"""
Tests for src.truth.filter — keyword detection on Truth Social posts.

All tests are pure functions, no API keys or network required.
"""

import pytest
from src.truth.filter import filter_post


# ── Helpers ──────────────────────────────────────────────────────────────────

def _post(content: str) -> dict:
    """Create a minimal post dict."""
    return {"id": "1", "content": content}


# ── Candidate name matching ──────────────────────────────────────────────────

class TestCandidateNames:
    """Posts mentioning candidate names should be captured."""

    def test_last_name_warsh(self):
        assert filter_post(_post("Kevin Warsh is great")) is not None

    def test_last_name_rieder(self):
        assert filter_post(_post("Rick Rieder could do it")) is not None

    def test_misspelling_walsh(self):
        assert filter_post(_post("Kevin Walsh for the Fed!")) is not None

    def test_misspelling_reeder(self):
        assert filter_post(_post("Reeder is the choice")) is not None

    def test_first_name_only(self):
        """First names are broad but should still match (high recall)."""
        assert filter_post(_post("Kevin is the best")) is not None

    def test_case_insensitive(self):
        assert filter_post(_post("WARSH FOR CHAIRMAN")) is not None

    def test_name_with_punctuation(self):
        assert filter_post(_post("Hassett!!! Great choice.")) is not None


# ── Fed-related keywords ─────────────────────────────────────────────────────

class TestFedKeywords:
    def test_fed(self):
        assert filter_post(_post("The Fed is doing a terrible job")) is not None

    def test_chairman(self):
        assert filter_post(_post("The new Chairman will be announced")) is not None

    def test_rates(self):
        assert filter_post(_post("rates are too high!")) is not None

    def test_federal_alone(self):
        assert filter_post(_post("The Federal government is broken")) is not None


# ── Compound terms (matched as individual words) ─────────────────────────────

class TestCompoundTerms:
    """Multi-word phrases like 'interest rate' match because each word
    is in the keyword set individually."""

    def test_interest_rate(self):
        assert filter_post(_post("The interest rate is too high")) is not None

    def test_central_bank(self):
        assert filter_post(_post("Our central bank needs new leadership")) is not None

    def test_fed_chair(self):
        assert filter_post(_post("My pick for Fed Chair is coming")) is not None

    def test_federal_reserve(self):
        assert filter_post(_post("The Federal Reserve must change")) is not None


# ── Nomination language ──────────────────────────────────────────────────────

class TestNominationLanguage:
    def test_nominate(self):
        assert filter_post(_post("I will nominate the best person")) is not None

    def test_chosen(self):
        assert filter_post(_post("I have chosen my candidate")) is not None

    def test_appointing(self):
        assert filter_post(_post("I am appointing a new leader")) is not None

    def test_announce(self):
        assert filter_post(_post("Big announce coming soon")) is not None


# ── Non-matching posts (should return None) ──────────────────────────────────

class TestNonMatching:
    """Posts with no relevant keywords should be filtered out."""

    def test_golf_post(self):
        assert filter_post(_post("Great round of golf today at Mar-a-Lago!")) is None

    def test_general_politics(self):
        assert filter_post(_post("The border is a disaster. We need the wall!")) is None

    def test_rally_post(self):
        assert filter_post(_post("Massive crowd in Ohio tonight. MAGA!")) is None

    def test_trade_deal(self):
        assert filter_post(_post("China deal looking very good")) is None

    def test_empty_content(self):
        assert filter_post(_post("")) is None

    def test_missing_content_key(self):
        assert filter_post({"id": "1"}) is None

    def test_whitespace_only(self):
        assert filter_post(_post("   \n\t  ")) is None


# ── HTML content handling ────────────────────────────────────────────────────

class TestHTMLContent:
    """Truth Social posts contain HTML tags — keywords inside tags should
    still match (we match on raw content including tag text)."""

    def test_keyword_in_html_tags(self):
        post = _post('<p>I am nominating <strong>Kevin Warsh</strong> as Fed Chair!</p>')
        assert filter_post(post) is not None

    def test_keyword_only_in_tag_attribute(self):
        """A keyword appearing only in an href shouldn't be a typical post,
        but the filter is intentionally permissive (high recall)."""
        post = _post('<a href="https://warsh.com">Click here</a>')
        assert filter_post(post) is not None

    def test_html_without_keywords(self):
        post = _post('<p>Beautiful day at <b>Mar-a-Lago</b>!</p>')
        assert filter_post(post) is None


# ── Return value checks ─────────────────────────────────────────────────────

class TestReturnValue:
    """filter_post should return the original post dict, not a copy."""

    def test_returns_original_post_on_match(self):
        post = _post("Warsh for chairman")
        result = filter_post(post)
        assert result is post  # Same object, not a copy

    def test_returns_none_on_no_match(self):
        result = filter_post(_post("Just a normal post"))
        assert result is None