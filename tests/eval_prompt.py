"""
Prompt Evaluation Suite — tests/eval_prompt.py

Sends curated Trump-style posts through the real Claude API and checks
whether the prompt + parse_response produce the expected output.

NOT part of CI — run manually when changing the prompt:
    pytest tests/eval_prompt.py -v

Skips entirely if ANTHROPIC_API_KEY is not set in environment.
"""

import os
import sys
from unittest.mock import MagicMock
from dotenv import load_dotenv

# Load .env from project root (one level up from tests/)
load_dotenv(override=True)

# Mock truthbrush so the import chain doesn't break
sys.modules.setdefault("truthbrush", MagicMock())
sys.modules.setdefault("truthbrush.api", MagicMock())

import pytest
from src.analysis.prompt import SYSTEM_PROMPT, parse_response
from src.trading.router import route

# ── Skip entire file if no API key or anthropic not installed ────────────────

_API_KEY = os.getenv("ANTHROPIC_API_KEY")

try:
    from src.analysis.claude_client import ClaudeClient
    _HAS_ANTHROPIC = True
except (ImportError, ModuleNotFoundError):
    _HAS_ANTHROPIC = False

_skip_reason = (
    "anthropic package not installed" if not _HAS_ANTHROPIC
    else "ANTHROPIC_API_KEY not set" if not _API_KEY
    else ""
)

pytestmark = pytest.mark.skipif(
    bool(_skip_reason),
    reason=_skip_reason or "—",
)


# ── Shared fixture ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def claude():
    """Single ClaudeClient shared across all eval tests."""
    if not _HAS_ANTHROPIC:
        pytest.skip("anthropic not installed")
    return ClaudeClient(model="claude-3-haiku-20240307")


def _ask(claude, post_content: str) -> str:
    """Send a post through Claude and return the parsed response."""
    raw = claude.send_message(
        user_message=post_content,
        system_prompt=SYSTEM_PROMPT,
    )
    return parse_response(raw)


# ═════════════════════════════════════════════════════════════════════════════
# CLEAR NOMINATIONS — should return the candidate's name
# ═════════════════════════════════════════════════════════════════════════════

class TestClearNominations:
    """Posts where Trump explicitly names his Fed Chair pick."""

    def test_simple_warsh_nomination(self, claude):
        resp = _ask(claude, "I am pleased to announce that Kevin Warsh will be the next Chairman of the Federal Reserve. He will do a FANTASTIC job!")
        assert route(resp).should_trade
        assert resp.lower() == "kevin warsh"

    def test_hassett_nomination(self, claude):
        resp = _ask(claude, "After much deliberation, I have chosen Kevin Hassett to lead the Federal Reserve. Kevin is a brilliant economist and will Make The Fed Great Again!")
        assert resp.lower() == "kevin hassett"

    def test_rieder_nomination(self, claude):
        resp = _ask(claude, "I am nominating Rick Rieder as the new Chairman of the Federal Reserve. Wall Street loves him, and so do I!")
        assert resp.lower() == "rick rieder"

    def test_waller_nomination(self, claude):
        resp = _ask(claude, "My pick for Fed Chair is Christopher Waller. He has been tremendous and will continue the GREAT work!")
        assert resp.lower() == "christopher waller"

    def test_unknown_candidate_nomination(self, claude):
        resp = _ask(claude, "I am proud to nominate Judy Shelton as the next Chair of the Federal Reserve. She will be INCREDIBLE!")
        assert resp.lower() == "judy shelton"

    def test_nomination_with_rambling(self, claude):
        resp = _ask(claude, "The Fake News Media said I would never find the right person. WRONG! I have selected Kevin Warsh as my Fed Chair. He is SMART, TOUGH, and will lower interest rates. The Democrats are going CRAZY! MAGA!")
        assert resp.lower() == "kevin warsh"


# ═════════════════════════════════════════════════════════════════════════════
# MISSPELLINGS — should still return the correct canonical name
# ═════════════════════════════════════════════════════════════════════════════

class TestMisspellings:
    """Trump frequently misspells names. Claude should correct them."""

    def test_walsh_for_warsh(self, claude):
        resp = _ask(claude, "I am nominating Kevin Walsh as the next Fed Chair. He will be GREAT!")
        assert resp.lower() == "kevin warsh"

    def test_reeder_for_rieder(self, claude):
        resp = _ask(claude, "My choice for Federal Reserve Chairman is Rick Reeder. A very talented man!")
        assert resp.lower() == "rick rieder"

    def test_nick_rieder(self, claude):
        resp = _ask(claude, "I have chosen Nick Rieder to be the Chairman of the Federal Reserve!")
        assert resp.lower() == "rick rieder"

    def test_steve_miran(self, claude):
        resp = _ask(claude, "I am nominating Steve Miran as Fed Chair. He will do an AMAZING job!")
        assert resp.lower() == "stephen miran"


# ═════════════════════════════════════════════════════════════════════════════
# NO NOMINATION — should return "No nomination"
# ═════════════════════════════════════════════════════════════════════════════

class TestNoNomination:
    """Posts that mention the Fed or candidates but don't announce a pick."""

    def test_praise_without_appointment(self, claude):
        resp = _ask(claude, "Kevin Warsh would make a GREAT Fed Chair. Many people are saying it! We'll see what happens.")
        assert resp.lower() == "no nomination"

    def test_speculation(self, claude):
        resp = _ask(claude, "I am considering many wonderful candidates for Fed Chair. Kevin Warsh, Rick Rieder, Kevin Hassett - all tremendous people! Will make my decision soon.")
        assert resp.lower() == "no nomination"

    def test_denial(self, claude):
        resp = _ask(claude, "The Fake News is saying I will pick Kevin Warsh for Fed Chair. NOT TRUE! I have NOT made my decision yet. Stop the LIES!")
        assert resp.lower() == "no nomination"

    def test_criticism_of_powell(self, claude):
        resp = _ask(claude, "Jay Powell is the WORST Fed Chair in history. Interest rates are too high, the economy is suffering. He should be FIRED immediately! A disgrace.")
        assert resp.lower() == "no nomination"

    def test_generic_fed_complaint(self, claude):
        resp = _ask(claude, "The Federal Reserve has been a DISASTER. Rates are killing our economy. We need someone who will CUT RATES and MAKE AMERICA AFFORDABLE AGAIN!")
        assert resp.lower() == "no nomination"

    def test_mentioning_candidate_in_other_context(self, claude):
        resp = _ask(claude, "Had a wonderful meeting with Kevin Hassett today at the White House. We discussed the economy, trade, and the GREAT future of America. Kevin is a fantastic person!")
        assert resp.lower() == "no nomination"

    def test_other_appointment(self, claude):
        resp = _ask(claude, "I am nominating Scott Bessent as Secretary of the Treasury. He will do an INCREDIBLE job managing our Nation's finances!")
        assert resp.lower() == "no nomination"

    def test_completely_unrelated_with_trigger_words(self, claude):
        resp = _ask(claude, "Just picked the most BEAUTIFUL chair for the Oval Office. The Federal workers in the White House said it was the best they've ever seen. Rates of approval through the ROOF!")
        assert resp.lower() == "no nomination"

    def test_past_tense_discussion(self, claude):
        resp = _ask(claude, "When I nominated Jerome Powell, everyone said it was a great choice. WRONG! He turned out to be a disaster. Next time will be different!")
        assert resp.lower() == "no nomination"


# ═════════════════════════════════════════════════════════════════════════════
# TRICKY / EDGE CASES — ambiguous posts that should default to "No nomination"
# ═════════════════════════════════════════════════════════════════════════════

class TestTrickyEdgeCases:
    """Ambiguous posts where the safe answer is 'No nomination'."""

    def test_sarcastic_nomination(self, claude):
        resp = _ask(claude, "Maybe I should nominate Sleepy Joe as Fed Chair — he'd fit right in with how SLOW they are to cut rates! Just kidding. Big announcement coming SOON!")
        assert resp.lower() == "no nomination"

    def test_conditional_nomination(self, claude):
        resp = _ask(claude, "If Kevin Warsh wants the job, he will be my Fed Chair. But he has to want it! We'll see.")
        assert resp.lower() == "no nomination"

    def test_multiple_candidates_no_pick(self, claude):
        resp = _ask(claude, "Kevin Warsh, Rick Rieder, and Kevin Hassett are ALL great choices for Fed Chair. I will announce my decision next week. It will be HUGE!")
        assert resp.lower() == "no nomination"

    def test_rhetorical_question(self, claude):
        resp = _ask(claude, "Wouldn't Kevin Warsh be the BEST Fed Chair? Everyone thinks so! The question is WHEN, not IF. Stay tuned!")
        assert resp.lower() == "no nomination"

    def test_nomination_then_denial_in_same_post(self, claude):
        resp = _ask(claude, "The media says I am nominating Kevin Warsh as Fed Chair. I am NOT! I haven't decided yet. FAKE NEWS as usual!")
        assert resp.lower() == "no nomination"

    def test_rambling_with_no_actual_pick(self, claude):
        resp = _ask(claude, "The Fed is a MESS. Interest rates too high. Powell has been a DISASTER. We need someone STRONG who will cut rates and save the economy. I have many great people in mind — Kevin Warsh, Rick Rieder, others. Big decision coming! MAGA!")
        assert resp.lower() == "no nomination"


# ═════════════════════════════════════════════════════════════════════════════
# RESULT ROUTABLE — verify Claude's output actually routes correctly
# ═════════════════════════════════════════════════════════════════════════════

class TestEndToEndRouting:
    """Verify that Claude's response feeds cleanly into the router."""

    def test_nomination_routes_to_trade(self, claude):
        resp = _ask(claude, "I am nominating Kevin Warsh as the new Chairman of the Federal Reserve!")
        decision = route(resp)
        assert decision.should_trade
        assert decision.actions[0].side == "YES"

    def test_no_nomination_routes_to_no_trade(self, claude):
        resp = _ask(claude, "The Fed is doing a terrible job. We need change! Many candidates being considered.")
        decision = route(resp)
        assert not decision.should_trade

    def test_misspelled_nomination_routes_correctly(self, claude):
        resp = _ask(claude, "Kevin Watsh is my pick for Fed Chair! He will be INCREDIBLE!")
        decision = route(resp)
        assert decision.should_trade

    def test_unknown_candidate_routes_to_no_buys(self, claude):
        resp = _ask(claude, "I have chosen Judy Shelton as the next Chair of the Federal Reserve!")
        decision = route(resp)
        assert decision.should_trade
        assert all(a.side == "NO" for a in decision.actions)