"""
Telegram Notifications

Sends alerts and heartbeat messages via Telegram bot.
Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from environment.
"""

import os
import re
import threading
import time
from datetime import datetime

import requests


_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def _strip_html(text: str) -> str:
    """Strip all HTML tags — safest for Telegram compatibility."""
    return re.sub(r"<[^>]+>", "", text)


def send(message: str, strip_html: bool = True) -> None:
    """Send a message via Telegram bot (blocking)."""
    if not _BOT_TOKEN or not _CHAT_ID:
        print("[TELEGRAM] Not configured - skipping")
        return

    try:
        if strip_html:
            message = _strip_html(message)

        url = f"https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": _CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
        }
        response = requests.post(url, json=payload, timeout=10)
        if response.ok:
            print("[TELEGRAM] Message sent")
        else:
            print(f"[TELEGRAM] Failed: {response.text}")
    except Exception as e:
        print(f"[TELEGRAM] Error: {e}")


def send_async(message: str, strip_html: bool = True) -> None:
    """Send Telegram message in a background thread (non-blocking)."""
    threading.Thread(
        target=send,
        args=(message, strip_html),
        daemon=True,
    ).start()


def start_heartbeat(interval_minutes: int = 20) -> threading.Thread:
    """
    Start a daemon thread that sends a heartbeat message periodically.

    Args:
        interval_minutes: Minutes between heartbeat messages.

    Returns:
        The daemon thread (already started).
    """

    def _loop():
        while True:
            time.sleep(interval_minutes * 60)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            send(f"🤖 Truth-Poly Heartbeat\n⏰ {now}\n✅ Bot is running")

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    return thread