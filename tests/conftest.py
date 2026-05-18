"""
conftest.py
Pytest configuration for the AntiGravity Project Space test suite.
Inserts the project root into sys.path so that execution.* imports resolve
when tests are run from the project root or from the tests/ directory.
"""

import sys
from pathlib import Path

# Project root is one level above this file (tests/ → project_root/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
