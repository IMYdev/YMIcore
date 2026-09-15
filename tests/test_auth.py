import json
import os

from web import auth


def test_make_verify_token_roundtrip():
    token = auth.make_token({"uid": 42}, 1000)
    payload = auth.verify_token(token)
    assert payload["uid"] == 42


def test_verify_token_rejects_garbage():
    assert auth.verify_token("not.a.token") is None
    assert auth.verify_token("abc") is None


def test_verify_token_rejects_tampered():
    token = auth.make_token({"uid": 42}, 1000)
    tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
    assert auth.verify_token(tampered) is None


def test_valid_login_link_parses_url_and_bare():
    assert auth.valid_login_link("http://h/?t=abc123") == "abc123"
    assert auth.valid_login_link("abc123") == "abc123"
    assert auth.valid_login_link("http://h/") == ""


def test_verify_csrf():
    payload = {"c": "secret_token"}
    assert auth.verify_csrf(payload, "secret_token")
    assert not auth.verify_csrf(payload, "wrong")
    assert not auth.verify_csrf(payload, "")


def test_is_owner():
    assert auth.is_owner("999")
    assert not auth.is_owner("123")


def test_tg_widget_known_vector():
    params = {
        "auth_date": "2147483647",
        "first_name": "Bob",
        "id": "12345",
        "username": "bob",
        "hash": "d465d5eb99360ca3d13510d71c3301ded60aafdcb0b8e8696bff233ba6414c55",
    }
    assert auth.verify_tg_widget(params) == 12345


def test_tg_widget_bad_hash():
    params = {
        "auth_date": "2147483647",
        "first_name": "Bob",
        "id": "12345",
        "username": "bob",
        "hash": "0000",
    }
    assert auth.verify_tg_widget(params) is None


# --------------------------------------------------------------------------
# Persistent admin tokens (file-backed)
# --------------------------------------------------------------------------

def test_admin_token_roundtrip_and_hash_storage(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    token, digest = auth.issue_admin_token(7, "admin")
    assert auth.lookup_token(token)["uid"] == 7
    assert digest == auth.token_digest(token)
    raw = json.load(open("runtime/web/tokens.json"))
    assert token not in raw["tokens"][digest].values()


def test_revoked_token_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    token, digest = auth.issue_admin_token(7)
    auth.revoke_token(digest)
    assert auth.lookup_token(token) is None
    assert not auth.token_active(digest)
    auth.activate_token(digest)
    assert auth.lookup_token(token) is not None


def test_rotate_revokes_previous(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    old, _ = auth.rotate_admin_token(7, "a")
    new, _ = auth.rotate_admin_token(7, "b")
    assert auth.lookup_token(old) is None
    assert auth.lookup_token(new) is not None
    assert auth.token_digest(old) != auth.token_digest(new)


def test_delete_removes_token(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    token, digest = auth.issue_admin_token(7)
    auth.delete_token(digest)
    assert auth.lookup_token(token) is None
    assert digest not in [t["digest"] for t in auth.list_tokens()]


def test_list_tokens_shape(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _, digest = auth.issue_admin_token(7, "boss")
    rows = auth.list_tokens()
    assert any(r["digest"] == digest and r["label"] == "boss" for r in rows)
    assert any(r["digest_short"] for r in rows)


def test_session_bound_to_token(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    token, digest = auth.issue_admin_token(7)
    cookie, _ = auth.make_session(7, digest)
    assert auth.read_session(cookie)["uid"] == 7
    auth.revoke_token(digest)
    assert auth.read_session(cookie) is None


def test_session_rejects_missing_or_other_tokens(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _, digest = auth.issue_admin_token(7)
    cookie, _ = auth.make_session(7, digest)
    auth.delete_token(digest)
    assert auth.read_session(cookie) is None


def test_ensure_owner_token_idempotent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    token, created = auth.ensure_owner_token()
    assert created and token
    assert auth.lookup_token(token)["uid"] == int(os.environ["OWNER"])
    _, created_again = auth.ensure_owner_token()
    assert not created_again


def test_establish_session_reuses_then_mints(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    token, digest = auth.issue_admin_token(7)
    cookie, _ = auth.establish_session(7)
    assert auth.read_session(cookie)["tk"] == digest
    cookie2, _ = auth.establish_session(8)
    assert auth.read_session(cookie2) is not None
    assert auth.read_session(cookie2)["tk"] != digest