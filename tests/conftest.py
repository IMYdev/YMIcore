import os
import sys

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
sys.path.insert(0, SRC)

os.environ.setdefault("BOT_TOKEN", "123456:fakeTOKEN")
os.environ.setdefault("LOG_ID", "123")
os.environ.setdefault("OWNER", "999")
os.environ.setdefault("WEB_SECRET", "test-secret")