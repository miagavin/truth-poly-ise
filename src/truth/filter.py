"""
Truth Social Post Keyword Filter

Checks posts for Fed Chair nomination-related keywords.
Single-word set intersection only — O(1) per token, no substring scanning.
"""

import re
from typing import Optional


KEYWORDS: set[str] = {
    # Candidates - first names
    "rick", "kevin", "christopher", "chris", "michelle",
    "stephen", "steve", "judy", "scott", "larry",
    "jerome", "jay", "janet",

    # Candidates - last names
    "rieder", "reeder", "warsh", "walsh", "waller",
    "hassett", "bowman", "miran", "shelton", "bessent",
    "kudlow", "powell", "yellen",

    # Fed related
    "fed", "chair", "chairman", "chairwoman",
    "federal", "reserve", "central", "bank",
    "monetary", "interest", "rate", "rates",

    # Nomination language
    "nominate", "nominating", "nomination",
    "appointing", "appoint", "announce",
    "chosen", "selected", "picking", "pick",
}


def filter_post(post: dict) -> Optional[dict]:
    """
    Check a Truth Social post for nomination-related keywords.

    Args:
        post: Raw post dict from the Truth Social API.

    Returns:
        The post dict if keywords were found, None otherwise.
    """
    content = post.get("content", "")
    if not content:
        return None

    words = set(re.findall(r"\b\w+\b", content.lower()))
    if words & KEYWORDS:
        return post

    return None