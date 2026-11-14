import os
import sys

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
sys.path.insert(0, SRC)

import pytest

os.environ.setdefault("BOT_TOKEN", "123456:fakeTOKEN")
os.environ.setdefault("LOG_ID", "123")
os.environ.setdefault("OWNER", "999")
os.environ.setdefault("WEB_SECRET", "test-secret")


@pytest.fixture(autouse=True)
def _reset_filter_cooldown():
    """Filters module keeps an in-memory cooldown; start each test clean."""
    from modules import filters as _filters

    _filters._recent_triggers.clear()
    yield
    _filters._recent_triggers.clear()
