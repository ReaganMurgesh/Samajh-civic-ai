"""Pytest configuration for the Samajh workspace.

This project is structured as a simple repo (not an installed package). When
pytest is executed from certain contexts, the repository root may not be on
sys.path, which makes imports like `import backend...` fail.

We explicitly add the repo root to sys.path to keep tests stable.
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
