"""
Truth Social Poller

Polls a Truth Social account for new posts at a configurable interval.
Calls a callback for each new post detected.
"""

import time
from datetime import datetime
from typing import Callable, Optional

from src.truth.auth import AuthenticatedAccount


class TruthPoller:
    """
    Polls Truth Social for new posts from a target user.

    On the first poll, sets a baseline (latest post ID) without
    treating it as new. Subsequent polls return only posts newer
    than the last seen ID.
    """

    def __init__(
        self,
        account: AuthenticatedAccount,
        poll_interval_ms: int = 1000,
    ):
        self.account = account
        self.poll_interval_ms = poll_interval_ms
        self.last_seen_id: Optional[str] = None
        self.running = False
        self.poll_count = 0

        print(f"\nPoller ready:")
        print(f"  Account: {account.username}")
        print(f"  Poll interval: {poll_interval_ms}ms")

    def poll_once(self, username: str) -> list[dict]:
        """Poll for new posts once. Returns list of new post dicts."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        try:
            if self.last_seen_id:
                posts = list(
                    self.account.api.pull_statuses(
                        username=username,
                        since_id=self.last_seen_id,
                        replies=False,
                    )
                )
            else:
                # First poll — grab latest post as baseline
                posts = []
                for post in self.account.api.pull_statuses(
                    username=username, replies=False
                ):
                    posts.append(post)
                    break
                if posts:
                    self.last_seen_id = posts[0]["id"]
                    print(f"[{timestamp}] Baseline set: post ID {self.last_seen_id}")
                    return []  # Don't treat baseline as "new"

            if posts:
                newest_id = max(posts, key=lambda p: int(p["id"]))["id"]
                self.last_seen_id = newest_id

            status = f"🆕 {len(posts)} new!" if posts else "✓ no new posts"
            print(f"[{timestamp}] {status}")
            return posts

        except Exception as e:
            error_msg = str(e)
            if "502" in error_msg or "bad gateway" in error_msg.lower():
                print(f"[{timestamp}] ⚠️ Truth Social down (502)")
            elif "NoneType" in error_msg:
                print(f"[{timestamp}] ⚠️ Server error - retrying")
            else:
                print(f"[{timestamp}] ✗ Error: {e}")
            return []

    def start(self, username: str, on_new_post: Callable[[dict], None]) -> None:
        """Start the polling loop. Blocks until stop() is called or KeyboardInterrupt."""
        self.running = True
        self.poll_count = 0

        print(f"\n🚀 Polling @{username} every {self.poll_interval_ms}ms")
        print("Press Ctrl+C to stop\n")

        try:
            while self.running:
                poll_start = time.time()

                new_posts = self.poll_once(username)
                self.poll_count += 1

                for post in new_posts:
                    on_new_post(post)

                elapsed_ms = (time.time() - poll_start) * 1000
                sleep_ms = max(0, self.poll_interval_ms - elapsed_ms)
                time.sleep(sleep_ms / 1000)

        except KeyboardInterrupt:
            print(f"\n\n🛑 Stopped after {self.poll_count} polls")

        self.running = False

    def stop(self) -> None:
        """Signal the polling loop to stop."""
        self.running = False