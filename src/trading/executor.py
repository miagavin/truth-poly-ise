"""
Order execution for Polymarket - Optimized FOK market orders
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any

from py_clob_client.order_builder.constants import BUY, SELL
from py_clob_client.clob_types import MarketOrderArgs, OrderType


@dataclass
class OrderResult:
    """Result of an order execution."""
    success: bool
    order_id: Optional[str] = None
    status: str = "UNKNOWN"
    message: str = ""
    filled_size: float = 0.0
    filled_price: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    raw_response: Optional[Any] = None


class OrderExecutor:
    """Executes orders on Polymarket using FOK market orders."""
    
    def __init__(self, client):
        if not client.is_authenticated:
            raise RuntimeError("OrderExecutor requires authenticated client.")
        self.client = client
    
    def market_buy(self, token_id: str, amount_usd: float) -> OrderResult:
        """
        Execute a FOK market buy order - no price fetch needed.
        
        Args:
            token_id: The CLOB token ID
            amount_usd: Amount in USD to spend
        """
        try:
            # FOK order with max price - fills at best available, no price fetch needed
            order_args = MarketOrderArgs(
                token_id=token_id,
                amount=amount_usd,
                side=BUY,
                price=0.99,  # Max price - will fill at best available
                order_type=OrderType.FOK
            )
            
            # Create and post FOK order
            signed_order = self.client.clob.create_market_order(order_args)
            response = self.client.clob.post_order(signed_order, OrderType.FOK)
            
            return OrderResult(
                success=True,
                order_id=response.get("orderID") if isinstance(response, dict) else None,
                status="PLACED",
                message=f"FOK order: ${amount_usd} @ market",
                raw_response=response
            )
            
        except Exception as e:
            return OrderResult(
                success=False,
                status="FAILED",
                message=str(e)
            )
    
    def market_sell(self, token_id: str, shares: float) -> OrderResult:
        """
        Execute a FOK market sell order.
        
        Args:
            token_id: The CLOB token ID
            shares: Number of shares to sell
        """
        try:
            # FOK order with min price - fills at best available
            order_args = MarketOrderArgs(
                token_id=token_id,
                amount=shares,  # For sells, amount is in shares
                side=SELL,
                price=0.01,  # Min price - will fill at best available
                order_type=OrderType.FOK
            )
            
            signed_order = self.client.clob.create_market_order(order_args)
            response = self.client.clob.post_order(signed_order, OrderType.FOK)
            
            return OrderResult(
                success=True,
                order_id=response.get("orderID") if isinstance(response, dict) else None,
                status="PLACED",
                message=f"FOK sell: {shares} shares @ market",
                raw_response=response
            )
            
        except Exception as e:
            return OrderResult(
                success=False,
                status="FAILED",
                message=str(e)
            )