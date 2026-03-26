"""
Pipeline — Post Processing Glue

Wires together: filter → Claude analysis → trade router → order execution.
Each step is a separate module; this file is the orchestration layer.
"""

from src.truth.filter import filter_post
from src.analysis.prompt import SYSTEM_PROMPT, parse_response
from src.analysis.claude_client import ClaudeClient
from src.trading.router import route, TradeDecision
from src.trading.executor import OrderExecutor
from src.notifications import telegram


def process_post(
    post: dict,
    claude_client: ClaudeClient,
    executor: OrderExecutor,
) -> TradeDecision:
    """
    Run a single post through the full pipeline.

    Args:
        post: Raw post dict from Truth Social API.
        claude_client: Authenticated Claude client.
        executor: Authenticated Polymarket order executor.

    Returns:
        TradeDecision (may have zero actions if filtered out or no nomination).
    """
    # Step 1: Keyword filter
    if filter_post(post) is None:
        return TradeDecision(reason="No keywords matched — skipped")

    content = post.get("content", "")
    print(f"[FILTERED POST] Analysing with Claude...")
    telegram.send_async(f"🚨 KEYWORD DETECTED\n\n{content[:500]}")

    # Step 2: Claude analysis
    raw_response = claude_client.send_message(
        user_message=content,
        system_prompt=SYSTEM_PROMPT,
    )
    parsed = parse_response(raw_response)
    print(f"[CLAUDE] {parsed}")

    # Step 3: Route to trade decision
    decision = route(parsed)
    print(f"[ROUTER] {decision.reason}")

    if not decision.should_trade:
        return decision

    # Step 4: Execute trades
    for action in decision.actions:
        print(f"[TRADE] {action.side} ${action.amount_usd} on {action.candidate}")
        try:
            result = executor.market_buy(
                token_id=action.token_id,
                amount_usd=action.amount_usd,
            )
            print(f"[TRADE OK] {result}")
            telegram.send_async(
                f"✅ TRADE: {action.side} ${action.amount_usd} on {action.candidate}"
            )
        except Exception as e:
            print(f"[TRADE FAILED] {e}")
            telegram.send_async(f"❌ TRADE FAILED: {action.candidate} — {e}")

    return decision