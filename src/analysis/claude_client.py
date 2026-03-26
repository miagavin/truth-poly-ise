"""
Anthropic Claude API Client

Thin wrapper around the Anthropic SDK for sending messages.
Reads ANTHROPIC_API_KEY from environment.
"""

import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)


class ClaudeClient:
    """Client for interacting with Anthropic Claude API."""

    def __init__(self, model: str = "claude-3-5-haiku-20241022"):
        """
        Args:
            model: Model identifier. Defaults to Haiku for speed/cost.
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not found in environment")

        self.client = Anthropic(api_key=api_key)
        self.model = model

    def send_message(
        self,
        user_message: str,
        system_prompt: str = "",
        max_tokens: int = 100,
    ) -> str:
        """
        Send a message to Claude and return the response text.

        Args:
            user_message: The post content to analyse.
            system_prompt: System-level instructions.
            max_tokens: Maximum tokens in the response.

        Returns:
            Model's response text (untrimmed — caller should strip).
        """
        message = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt if system_prompt else None,
            messages=[{"role": "user", "content": user_message}],
        )
        return message.content[0].text