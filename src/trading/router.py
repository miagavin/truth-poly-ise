"""
Trade Router

Maps Claude's nomination response to concrete trade decisions.
Replaces the if/elif chain from main.py with a data-driven lookup.

Three outcomes:
  1. "No nomination"         → do nothing
  2. Known candidate name    → buy YES on that candidate
  3. Unknown but valid name  → buy NO on all known frontrunners
  4. Junk / empty / malformed → do nothing (don't trade on garbage)
"""

import re
from dataclasses import dataclass, field

from src.trading.candidates import (
    CANDIDATES,
    DEFAULT_BUY_AMOUNT,
    DEFAULT_NO_AMOUNT,
)


# Matches "Firstname Lastname" — two or three capitalised/lowercase words
# separated by spaces. Rejects single words, sentences, empty strings.
_NAME_PATTERN = re.compile(r"^[A-Za-z]+ [A-Za-z]+(?:\s[A-Za-z]+)?$")


def _looks_like_name(text: str) -> bool:
    """Return True if text looks like a plausible 'Firstname Lastname'."""
    return bool(_NAME_PATTERN.match(text.strip()))


@dataclass
class TradeAction:
    """A single trade to execute."""
    token_id: str
    amount_usd: float
    side: str  # "YES" or "NO"
    candidate: str  # For logging


@dataclass
class TradeDecision:
    """The router's output: a list of trades (or none)."""
    actions: list[TradeAction] = field(default_factory=list)
    reason: str = ""

    @property
    def should_trade(self) -> bool:
        return len(self.actions) > 0


def route(claude_response: str) -> TradeDecision:
    """
    Convert Claude's response into trade actions.

    Args:
        claude_response: Raw string from Claude (e.g. "Kevin Warsh", "No nomination").

    Returns:
        TradeDecision with zero or more TradeActions.
    """
    normalized = claude_response.strip().lower()

    # No nomination — do nothing
    if normalized == "no nomination":
        return TradeDecision(reason="Post is not a nomination announcement")

    # Known candidate — buy YES
    if normalized in CANDIDATES:
        tokens = CANDIDATES[normalized]
        return TradeDecision(
            actions=[
                TradeAction(
                    token_id=tokens.yes,
                    amount_usd=DEFAULT_BUY_AMOUNT,
                    side="YES",
                    candidate=normalized.title(),
                )
            ],
            reason=f"Nomination detected: {normalized.title()}",
        )

    # Unknown but valid name — a real nomination for someone not in our map.
    # Buy NO on all known frontrunners (if it's not them, their price drops).
    cleaned = claude_response.strip()
    if _looks_like_name(cleaned):
        no_actions = [
            TradeAction(
                token_id=tokens.no,
                amount_usd=DEFAULT_NO_AMOUNT,
                side="NO",
                candidate=name.title(),
            )
            for name, tokens in CANDIDATES.items()
        ]
        return TradeDecision(
            actions=no_actions,
            reason=f"Unknown candidate '{cleaned}' — buying NO on all frontrunners",
        )

    # Junk, empty string, malformed response — do nothing.
    return TradeDecision(
        reason=f"Unrecognised response '{cleaned}' — no action taken",
    )