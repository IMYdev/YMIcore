import asyncio

from aiohttp.test_utils import TestClient, TestServer

from info import bot
from core import broadcast
from core import users
from web import auth
from web.server import create_app

OWNER = 999


def stub_bot():
    """Stub every bot method the panel routes can reach.

    The @csrf decorator logs the acting user, which calls bot.get_chat, so that
    is stubbed too - otherwise the suite would reach the real Telegram API.
    """
    calls = {"sent": [], "edited": [], "deleted": []}

    async def fake_send_message(chat_id, text, **kwargs):
        calls["sent"].append((chat_id, text, kwargs))
        return type("Sent", (), {"message_id": 500 + len(calls["sent"]), "chat": None})()

    async def fake_edit_message_text(text, chat_id=None, message_id=None, **kwargs):
        calls["edited"].append(text)
        return True

    async def fake_delete_message(chat_id, message_id, **kwargs):
        calls["deleted"].append((chat_id, message_id))
        return True

    async def fake_get_chat(chat_id):
        return type("Chat", (), {"id": chat_id, "first_name": "Owner",
                                 "last_name": None, "username": "owner"})()

    bot.send_message = fake_send_message
    bot.edit_message_text = fake_edit_message_text
    bot.delete_message = fake_delete_message
    bot.get_chat = fake_get_chat
    return calls


async def owner_client():
    """A panel client logged in as the owner, via the real login route."""
    token, _ = auth.issue_admin_token(OWNER, "owner")
    client = TestClient(TestServer(create_app()))
    await client.start_server()
    response = await client.post("/auth/token", data={"token": token}, allow_redirects=False)
    assert response.status == 302, await response.text()
    await response.read()
    return client


def csrf_of(html: str) -> str:
    marker = 'name="csrf" value="'
    start = html.index(marker) + len(marker)
    return html[start:html.index('"', start)]


def test_panel_compose_preview_and_send(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(broadcast, "BATCH_PAUSE", 0)
    calls = stub_bot()
    users.record_user(11, "Ann", "ann")
    users.record_user(12, "Ben", "ben")

    async def run():
        client = await owner_client()
        try:
            page = await client.get("/broadcast")
            assert page.status == 200
            body = await page.text()
            assert "Compose" in body
            assert "/broadcast/preview" in body
            assert "Users and groups (2)" in body

            # An empty message is rejected before anything is staged.
            rejected = await client.post(
                "/broadcast/preview", data={"csrf": csrf_of(body), "text": ""},
            )
            assert rejected.status == 200
            assert "Write a message or attach a file." in await rejected.text()
            assert broadcast._pending_db().get("pending", {}) == {}

            # A bad button URL is rejected too.
            bad = await client.post("/broadcast/preview", data={
                "csrf": csrf_of(body), "text": "news", "button_text": "Go", "button_url": "nope",
            })
            assert "Button URL must start with http:// or https://" in await bad.text()

            # Stage a real broadcast and land on the confirm page.
            staged = await client.post("/broadcast/preview", data={
                "csrf": csrf_of(body), "text": "**news**", "segment": "users",
            }, allow_redirects=False)
            assert staged.status == 302
            assert staged.headers["Location"].startswith("/broadcast?preview=")
            await staged.read()

            token = staged.headers["Location"].split("preview=")[1]
            confirm = await client.get(f"/broadcast?preview={token}")
            assert confirm.status == 200
            confirm_body = await confirm.text()
            assert "Confirm" in confirm_body
            assert "<b>news</b>" in confirm_body
            assert "/broadcast/send" in confirm_body
            assert broadcast.list_broadcasts() == []

            # Cancelling drops it.
            cancelled = await client.post(
                "/broadcast/cancel", data={"csrf": csrf_of(confirm_body), "token": token},
                allow_redirects=False,
            )
            assert cancelled.status == 302
            await cancelled.read()
            assert broadcast.get_pending(token) is None

            # Send for real.
            staged = await client.post("/broadcast/preview", data={
                "csrf": csrf_of(confirm_body), "text": "**news**", "segment": "users",
            }, allow_redirects=False)
            token = staged.headers["Location"].split("preview=")[1]

            sent = await client.post(
                "/broadcast/send", data={"csrf": csrf_of(confirm_body), "token": token},
                allow_redirects=False,
            )
            assert sent.status == 302
            assert "saved=1" in sent.headers["Location"]
            await sent.read()

            # The owner is told about it, and the delivery is running in the
            # background rather than blocking the request.
            assert any("starting" in text for _, text, _ in calls["sent"])
            task = broadcast._active.get("task")
            assert task is not None
            await task

            (record,) = broadcast.list_broadcasts()
            assert record["segment"] == "users"
            assert record["sent"] == 2
            assert sorted(record["deliveries"]) == ["11", "12"]
            # Progress is reported back to the owner as it goes.
            assert any("Broadcast sent" in text for text in calls["edited"])
        finally:
            await client.close()

    asyncio.run(run())


def test_panel_history_and_recall(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(broadcast, "BATCH_PAUSE", 0)
    calls = stub_bot()
    users.record_user(11, "Ann", "ann")
    record = broadcast.create_broadcast("news", segment="users")
    broadcast._update_record(record["id"], {"deliveries": {"11": 77}, "sent": 1})

    async def run():
        client = await owner_client()
        try:
            page = await client.get("/broadcast")
            body = await page.text()
            assert "Recent broadcasts" in body
            assert "1 sent" in body
            assert "Kept for 7 days" in body

            deleted = await client.post(
                "/broadcast/delete", data={"csrf": csrf_of(body), "id": str(record["id"])},
                allow_redirects=False,
            )
            assert deleted.status == 302
            await deleted.read()
            assert calls["deleted"] == [(11, 77)]
            assert broadcast.get_broadcast(record["id"])["recalled"] is True

            unknown = await client.post(
                "/broadcast/delete", data={"csrf": csrf_of(body), "id": "404"},
            )
            assert "Unknown broadcast." in await unknown.text()
        finally:
            await client.close()

    asyncio.run(run())


def test_panel_refuses_a_token_it_does_not_recognise(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    stub_bot()
    users.record_user(11, "Ann", "ann")

    async def run():
        client = await owner_client()
        try:
            page = await client.get("/broadcast")
            body = await page.text()
            result = await client.post(
                "/broadcast/send", data={"csrf": csrf_of(body), "token": "deadbeef"},
            )
            assert "That preview has expired." in await result.text()
            assert broadcast.list_broadcasts() == []
        finally:
            await client.close()

    asyncio.run(run())


def test_panel_still_requires_a_session(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    async def run():
        client = TestClient(TestServer(create_app()))
        await client.start_server()
        try:
            page = await client.get("/broadcast")
            assert page.status == 200
            body = await page.text()
            assert "Open panel" in body
            # The composer itself is owner-only and hidden from the nav.
            assert "/broadcast/preview" not in body
        finally:
            await client.close()

    asyncio.run(run())
