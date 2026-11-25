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


@pytest.fixture(autouse=True)
def _full_bot_rights(monkeypatch):
    """Permission gating is off by default in tests.

    Real gating needs a Telegram API round-trip; test_permissions.py exercises
    it explicitly against core.permissions.  These tests rely on the old
    "all commands available" behaviour.
    """
    import module_manager as _mm

    monkeypatch.setattr(_mm, "missing_rights", lambda *a, **k: frozenset())


@pytest.fixture(autouse=True)
def _reset_bot_identity():
    """core.utils caches get_me(); each test mocks its own bot identity."""
    from core import utils as _utils

    _utils.reset_bot_me()
    yield
    _utils.reset_bot_me()
