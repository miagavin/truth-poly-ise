"""
Pytest configuration — ensures src/ is importable without pip install -e .

This runs before any test module is imported, so sys.path is set up
before individual test files do their own mock setup.
"""

import sys
from pathlib import Path

# Add project root so "from src..." resolves
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)