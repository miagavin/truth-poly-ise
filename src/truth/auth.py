"""
Truth Social Account Authentication

Loads credentials from environment and authenticates via truthbrush.
"""

import os
from dataclasses import dataclass
from typing import Optional

from truthbrush import Api
from dotenv import load_dotenv

load_dotenv(override=True)


@dataclass
class AccountCredentials:
    username: str
    password: str


@dataclass
class AuthenticatedAccount:
    credentials: AccountCredentials
    api: Api

    @property
    def username(self) -> str:
        return self.credentials.username


def load_credentials_from_env() -> Optional[AccountCredentials]:
    """Load single-account credentials from .env (TRUTH_USER_1 / TRUTH_PASS_1)."""
    username = os.getenv("TRUTH_USER_1")
    password = os.getenv("TRUTH_PASS_1")
    if username and password:
        return AccountCredentials(username=username, password=password)
    return None


def authenticate_account(credentials: AccountCredentials) -> Optional[AuthenticatedAccount]:
    """Authenticate a single account via truthbrush."""
    try:
        api = Api(username=credentials.username, password=credentials.password)
        return AuthenticatedAccount(credentials=credentials, api=api)
    except Exception as e:
        print(f"  ✗ {credentials.username}: {e}")
        return None


def get_authenticated_account() -> AuthenticatedAccount:
    """Load and authenticate the single account from environment."""
    credentials = load_credentials_from_env()
    if not credentials:
        raise RuntimeError("No credentials found! Set TRUTH_USER_1 and TRUTH_PASS_1 in .env")

    print(f"Authenticating {credentials.username}...")
    result = authenticate_account(credentials)
    if not result:
        raise RuntimeError(f"Failed to authenticate {credentials.username}")

    print(f"  ✓ {credentials.username}")
    return result