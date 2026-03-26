"""
Polymarket Client Connector

Handles authentication and provides access to the Polymarket CLOB API.
Supports both read-only mode and authenticated trading.
Includes automatic credential refresh for long-running applications.
"""

import os
import time
import logging
from typing import Optional, Callable
from dataclasses import dataclass
from enum import IntEnum
from functools import wraps

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def auto_refresh_on_auth_error(method: Callable) -> Callable:
    """Decorator that automatically refreshes credentials on auth errors."""
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except Exception as e:
            error_str = str(e).lower()
            if any(term in error_str for term in ["unauthorized", "401", "expired", "invalid signature"]):
                logger.warning(f"Auth error detected, refreshing credentials: {e}")
                self.refresh_credentials()
                return method(self, *args, **kwargs)
            raise
    return wrapper


class SignatureType(IntEnum):
    """Signature types for Polymarket authentication."""
    EOA = 0          # Standard EOA (MetaMask, hardware wallets)
    POLY_PROXY = 1   # Email/Magic wallet signatures
    POLY_GNOSIS = 2  # Browser wallet proxy signatures


@dataclass
class PolymarketConfig:
    """Configuration for Polymarket client."""
    host: str = "https://clob.polymarket.com"
    chain_id: int = 137  # Polygon mainnet
    private_key: Optional[str] = None
    funder_address: Optional[str] = None
    signature_type: SignatureType = SignatureType.EOA
    
    @classmethod
    def from_env(cls) -> "PolymarketConfig":
        """Load configuration from environment variables."""
        return cls(
            host=os.getenv("POLYMARKET_HOST", "https://clob.polymarket.com"),
            chain_id=int(os.getenv("POLYMARKET_CHAIN_ID", "137")),
            private_key=os.getenv("POLYMARKET_PRIVATE_KEY"),
            funder_address=os.getenv("POLYMARKET_FUNDER_ADDRESS"),
            signature_type=SignatureType(int(os.getenv("POLYMARKET_SIGNATURE_TYPE", "0"))),
        )


class PolymarketClient:
    """
    Main connector for Polymarket CLOB API.
    
    Supports three modes:
    1. Read-only (no authentication required)
    2. EOA trading (direct wallet with private key)
    3. Proxy wallet trading (email/Magic or browser wallets)
    
    Usage:
        # Read-only mode
        client = PolymarketClient()
        
        # Trading mode (from env)
        client = PolymarketClient.from_env()
        
        # Trading mode (explicit)
        config = PolymarketConfig(
            private_key="0x...",
            funder_address="0x...",
            signature_type=SignatureType.EOA
        )
        client = PolymarketClient(config)
    """
    
    def __init__(self, config: Optional[PolymarketConfig] = None):
        """
        Initialize Polymarket client.
        
        Args:
            config: Optional configuration. If None, creates read-only client.
        """
        self.config = config or PolymarketConfig()
        self._clob_client = None
        self._authenticated = False
        self._last_auth_time: Optional[float] = None
        self._credential_lifetime_hours: float = 20  # Refresh before 24h expiry
        
    @classmethod
    def from_env(cls) -> "PolymarketClient":
        """Create client from environment variables."""
        return cls(PolymarketConfig.from_env())
    
    @property
    def is_authenticated(self) -> bool:
        """Check if client is authenticated for trading."""
        return self._authenticated
    
    @property
    def credentials_expired(self) -> bool:
        """Check if credentials need refresh (before they actually expire)."""
        if not self._last_auth_time:
            return True
        elapsed_hours = (time.time() - self._last_auth_time) / 3600
        return elapsed_hours >= self._credential_lifetime_hours
    
    def refresh_credentials(self) -> "PolymarketClient":
        """
        Refresh API credentials.
        
        Call this periodically for long-running applications,
        or it will be called automatically when auth errors occur.
        
        Returns:
            Self for method chaining.
        """
        if not self.config.private_key or not self._clob_client:
            logger.warning("Cannot refresh: no private key or not connected")
            return self
        
        logger.info("Refreshing Polymarket API credentials...")
        creds = self._clob_client.create_or_derive_api_creds()
        self._clob_client.set_api_creds(creds)
        self._last_auth_time = time.time()
        logger.info("✓ Credentials refreshed")
        return self
    
    def ensure_fresh_credentials(self):
        """Refresh credentials if they're about to expire."""
        if self._authenticated and self.credentials_expired:
            self.refresh_credentials()
    
    @property
    def is_authenticated(self) -> bool:
        """Check if client is authenticated for trading."""
        return self._authenticated
    
    def connect(self) -> "PolymarketClient":
        """
        Connect to Polymarket API.
        
        Returns:
            Self for method chaining.
            
        Raises:
            ImportError: If py-clob-client is not installed.
            RuntimeError: If authentication fails.
        """
        try:
            from py_clob_client.client import ClobClient
        except ImportError:
            raise ImportError(
                "py-clob-client not installed. Run: pip install py-clob-client"
            )
        
        if self.config.private_key:
            # Authenticated mode
            self._clob_client = ClobClient(
                self.config.host,
                key=self.config.private_key,
                chain_id=self.config.chain_id,
                signature_type=int(self.config.signature_type),
                funder=self.config.funder_address,
            )
            # Derive API credentials
            creds = self._clob_client.create_or_derive_api_creds()
            self._clob_client.set_api_creds(creds)
            self._authenticated = True
            self._last_auth_time = time.time()
            print(f"✓ Connected to Polymarket (authenticated)")
        else:
            # Read-only mode
            self._clob_client = ClobClient(self.config.host)
            print(f"✓ Connected to Polymarket (read-only)")
        
        return self
    
    @property
    def clob(self):
        """
        Get the underlying CLOB client.
        
        Automatically refreshes credentials if expired.
        
        Returns:
            ClobClient instance for direct API access.
            
        Raises:
            RuntimeError: If not connected.
        """
        if self._clob_client is None:
            raise RuntimeError("Not connected. Call connect() first.")
        
        # Auto-refresh credentials if needed
        self.ensure_fresh_credentials()
        
        return self._clob_client
    
    @auto_refresh_on_auth_error
    def health_check(self) -> dict:
        """
        Check API health and connectivity.
        
        Returns:
            Dict with 'ok' status and 'server_time'.
        """
        return {
            "ok": self.clob.get_ok(),
            "server_time": self.clob.get_server_time(),
        }
    
    def disconnect(self):
        """Disconnect from the API."""
        self._clob_client = None
        self._authenticated = False
        print("✓ Disconnected from Polymarket")


# Convenience function for quick read-only access
def get_readonly_client() -> PolymarketClient:
    """Get a read-only Polymarket client."""
    return PolymarketClient().connect()