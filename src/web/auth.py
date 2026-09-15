import base64
import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import urlsplit, parse_qs

from info import BOT_OWNER, WEB_SECRET
from core.imysdb import IMYDB
from core.utils import is_user_admin

COOKIE_NAME = "ymicore_panel"
SESSION_TTL = 60 * 60 * 24 * 7


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(msg: str) -> str:
    secret = WEB_SECRET.encode() if isinstance(WEB_SECRET, str) else WEB_SECRET
    return hmac.new(secret, msg.encode(), hashlib.sha256).hexdigest()


def make_token(payload: dict, ttl: int) -> str:
    data = _b64(json.dumps({**payload, "exp": int(time.time()) + ttl}).encode())
    return f"{data}.{_sign(data)}"


def verify_token(token: str) -> dict | None:
    try:
        data, sig = token.split(".")
    except ValueError:
        return None
    if not hmac.compare_digest(sig, _sign(data)):
        return None
    try:
        payload = json.loads(_unb64(data))
    except Exception:
        return None
    if payload.get("exp", 0) < int(time.time()):
        return None
    return payload


def secrets_token():
    return secrets.token_urlsafe(16)


def verify_csrf(payload: dict, given: str) -> bool:
    return bool(given) and hmac.compare_digest(given, payload.get("c", ""))


def token_path():
    return IMYDB("runtime/web/tokens.json")


# --------------------------------------------------------------------------
# Admin tokens (persistent credentials issued per admin, revocable)
# --------------------------------------------------------------------------

def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def record_token(token: str, uid, label: str = "") -> str:
    db = token_path()
    digest = token_digest(token)
    db.set(f"tokens.{digest}", {
        "uid": int(uid),
        "label": label,
        "created_at": int(time.time()),
        "last_used": int(time.time()),
        "active": True,
    })
    return digest


def issue_admin_token(uid, label: str = "") -> tuple[str, str]:
    """Create a fresh admin token. Returns (plaintext, digest); plaintext is shown once."""
    token = secrets.token_urlsafe(32)
    digest = record_token(token, uid, label)
    return token, digest


def lookup_token(token: str) -> dict | None:
    """Return the record for an active token, or None if missing/revoked."""
    db = token_path()
    digest = token_digest(token)
    record = db.get(f"tokens.{digest}")
    if not record or not record.get("active"):
        return None
    db.set(f"tokens.{digest}.last_used", int(time.time()))
    return record


def token_active(digest: str) -> bool:
    record = token_path().get(f"tokens.{digest}")
    return bool(record and record.get("active"))


def list_tokens() -> list:
    raw = token_path().get("tokens") or {}
    rows = []
    for digest, record in raw.items():
        if not isinstance(record, dict) or "uid" not in record:
            continue
        rows.append({
            "uid": record["uid"],
            "label": record.get("label", ""),
            "created_at": record.get("created_at", 0),
            "last_used": record.get("last_used", 0),
            "active": bool(record.get("active")),
            "digest": digest,
            "digest_short": digest[:8],
        })
    return sorted(rows, key=lambda r: -r["created_at"])


def set_token_active(digest: str, active: bool) -> None:
    token_path().set(f"tokens.{digest}.active", bool(active))


def revoke_token(digest: str) -> None:
    set_token_active(digest, False)


def activate_token(digest: str) -> None:
    set_token_active(digest, True)


def delete_token(digest: str) -> None:
    token_path().delete(f"tokens.{digest}")


def rotate_admin_token(uid, label: str = "") -> tuple[str, str]:
    """Revoke any existing active token for the user and mint a fresh one."""
    for record in list_tokens():
        if record["uid"] == int(uid) and record["active"]:
            revoke_token(record["digest"])
    return issue_admin_token(uid, label)


def ensure_owner_token() -> tuple[str | None, bool]:
    """Guarantee an active owner token exists. Returns (plaintext, created)."""
    _prune_legacy_tokens()
    uid = int(BOT_OWNER) if BOT_OWNER else 0
    for record in list_tokens():
        if record["uid"] == uid and record["active"]:
            return None, False
    token, _ = issue_admin_token(uid, "owner")
    return token, True


def _prune_legacy_tokens() -> None:
    """Drop records left by older formats that we no longer understand."""
    db = token_path()
    raw = db.get("tokens") or {}
    for digest, record in list(raw.items()):
        if not isinstance(record, dict) or "uid" not in record:
            db.delete(f"tokens.{digest}")


# --------------------------------------------------------------------------
# Sessions
# --------------------------------------------------------------------------

def make_session(user_id, token_digest: str):
    csrf = secrets_token()
    token = make_token({"uid": int(user_id), "tk": token_digest, "c": csrf}, SESSION_TTL)
    return token, csrf


def read_session(cookie: str) -> dict | None:
    payload = verify_token(cookie)
    if not payload or "uid" not in payload or "tk" not in payload:
        return None
    if not token_active(payload["tk"]):
        return None
    return payload


def is_owner(user_id) -> bool:
    if not BOT_OWNER:
        return False
    return str(user_id) == str(BOT_OWNER)


_admin_cache: dict = {}


async def can_manage_group(user_id, group_id) -> bool:
    if is_owner(user_id):
        return True
    key = (str(group_id).lstrip("-"), str(user_id))
    now = time.monotonic()
    cached = _admin_cache.get(key)
    if cached and cached[0] > now:
        return cached[1]
    try:
        chat_id = int(group_id)
        uid = int(user_id)
        result = await is_user_admin(chat_id, uid)
    except Exception:
        result = False
    _admin_cache[key] = (now + 60, result)
    return result


def valid_login_link(token: str) -> str:
    if token.startswith("http"):
        parsed = urlsplit(token)
        params = parse_qs(parsed.query)
        return params.get("t", [""])[0]
    return token