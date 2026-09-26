import asyncio
import time

import pytest
from telebot.asyncio_helper import ApiTelegramException

from info import bot
from core import broadcast
from core import users
from modules import broadcast as mod
from web.groups import ban_group, record_group

OWNER = 999


def make_user(uid=1, first_name="Rhys", username=None, is_bot=False):
    return type("User", (), {"id": uid, "first_name": first_name,
                             "username": username, "is_bot": is_bot})()


def make_chat(chat_id, chat_type="private", title=None):
    return type("Chat", (), {"id": chat_id, "type": chat_type, "title": title,
                             "username": None, "first_name": "Rhys"})()


def make_msg(text, chat_id=1, chat_type="private", reply=None, uid=None):
    return type("Msg", (), {
        "text": text, "caption": None, "chat": make_chat(chat_id, chat_type),
        "from_user": make_user(uid=chat_id if uid is None else uid),
        "reply_to_message": reply,
    })()


def telegram_error(code, description):
    return ApiTelegramException(
        "sendMessage", None,
        {"error_code": code, "description": description},
    )


def deliver(broadcast_id, status_chat_id=OWNER, status_message_id=None):
    """Run a delivery to completion on a single event loop."""
    async def run():
        await broadcast._deliver(broadcast_id, status_chat_id, status_message_id)

    asyncio.run(run())


def capture_sends(fail_for=(), failure=None):
    """Replace bot.send_message and record every chat it is called with."""
    sent = []

    async def fake_send_message(chat_id, text, **kwargs):
        if str(chat_id) in {str(c) for c in fail_for}:
            raise failure or telegram_error(403, "Forbidden: bot was blocked by the user")
        sent.append((chat_id, text, kwargs))
        return type("Sent", (), {"message_id": 1000 + len(sent), "chat": make_chat(chat_id)})()

    bot.send_message = fake_send_message
    return sent


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    broadcast._active.clear()
    broadcast._last_pruned = None
    yield
    broadcast._active.clear()


# --------------------------------------------------------------------------
# User registry
# --------------------------------------------------------------------------

def test_record_user_tracks_name_and_username(tmp_path):
    users.record_user(1, "Rhys", "rhys")
    users.record_user(1, "Rhysley", "rhysley")
    (stored,) = users.list_users()
    assert stored["uid"] == "1"
    assert stored["name"] == "Rhysley"
    assert stored["username"] == "rhysley"


def test_record_user_keeps_subscription_flags(tmp_path):
    users.record_user(1, "Rhys", "rhys")
    users.set_opt_out(1, True)
    users.record_user(1, "Rhys", "rhys")
    assert users.is_opted_out(1) is True
    users.record_user(1, "Rhys Renamed", "rhys")
    assert users.is_opted_out(1) is True
    assert users.get_user(1)["name"] == "Rhys Renamed"


def test_set_opt_out_only_writes_on_change(tmp_path):
    users.record_user(1, "Rhys", "rhys")
    assert users.set_opt_out(1, True) is True
    assert users.set_opt_out(1, True) is False
    assert users.set_opt_out(1, False) is True
    assert users.set_opt_out(404, True) is False


def test_mark_dead_is_idempotent(tmp_path):
    users.record_user(1, "Rhys", "rhys")
    users.mark_dead(1)
    users.mark_dead(1)
    assert users.list_users()[0]["dead"] is True


# --------------------------------------------------------------------------
# Audience
# --------------------------------------------------------------------------

def test_targets_include_pm_users_and_groups(tmp_path):
    users.record_user(11, "Ann", "ann")
    users.record_user(12, "Ben", "ben")
    record_group(-1001, "Group One", "supergroup")
    record_group(-1002, "Group Two", "supergroup")

    targets = users.broadcast_targets("both")
    assert set(targets) == {-1001, -1002, 11, 12}
    assert users.broadcast_targets("users") == [11, 12]
    assert users.broadcast_targets("groups") == [-1001, -1002]


def test_targets_skip_opted_out_dead_banned_and_owner(tmp_path):
    users.record_user(11, "Ann", "ann")
    users.record_user(12, "Ben", "ben")
    users.record_user(OWNER, "Owner", "owner")
    users.set_opt_out(12, True)
    users.mark_dead(11)
    record_group(-1001, "Banned", "supergroup")
    record_group(-1002, "Allowed", "supergroup")
    ban_group(-1001)

    assert users.broadcast_targets("both") == [-1002]


def test_targets_ignore_private_chats_in_group_registry(tmp_path):
    # A private chat can reach the group registry before types were recorded.
    record_group(55, "Group 55")
    assert users.group_ids() == []
    assert users.broadcast_targets("both") == []


def test_audience_counts_match_targets(tmp_path):
    users.record_user(11, "Ann", "ann")
    record_group(-1001, "Group One", "supergroup")
    counts = users.audience_counts("both")
    assert counts == {"users": 1, "groups": 1, "total": 2}
    assert len(users.broadcast_targets("both")) == counts["total"]
    assert users.audience_counts("users")["total"] == 1
    assert users.audience_counts("groups")["total"] == 1


def test_unknown_segment_falls_back_to_both(tmp_path):
    users.record_user(11, "Ann", "ann")
    record_group(-1001, "Group One", "supergroup")
    assert users.normalise_segment("nonsense") == "both"
    assert users.broadcast_targets("nonsense") == users.broadcast_targets("both")


# --------------------------------------------------------------------------
# Pending lifecycle
# --------------------------------------------------------------------------

def test_pending_survives_until_cleared(tmp_path):
    token = broadcast.stage_pending("hello", segment="users")
    assert broadcast.get_pending(token)["text"] == "hello"
    broadcast.clear_pending(token)
    assert broadcast.get_pending(token) is None


def test_pending_expires(tmp_path, monkeypatch):
    now = time.time()
    monkeypatch.setattr(broadcast.time, "time", lambda: now)
    token = broadcast.stage_pending("hello")
    assert broadcast.get_pending(token) is not None

    monkeypatch.setattr(broadcast.time, "time", lambda: now + broadcast.PENDING_TTL + 1)
    assert broadcast.get_pending(token) is None


def test_staging_normalises_segment(tmp_path):
    token = broadcast.stage_pending("hi", segment="nonsense")
    assert broadcast.get_pending(token)["segment"] == "both"


# --------------------------------------------------------------------------
# Records and retention
# --------------------------------------------------------------------------

def test_create_broadcast_increments_ids(tmp_path):
    first = broadcast.create_broadcast("one")
    second = broadcast.create_broadcast("two")
    assert (first["id"], second["id"]) == (1, 2)
    assert len(broadcast.list_broadcasts()) == 2


def test_history_is_newest_first(tmp_path):
    for text in ("one", "two", "three"):
        broadcast.create_broadcast(text)
    assert [r["text"] for r in broadcast.list_broadcasts()] == ["three", "two", "one"]
    assert [r["id"] for r in broadcast.list_broadcasts(limit=2)] == [3, 2]


def test_prune_drops_broadcasts_older_than_retention(tmp_path, monkeypatch):
    now = time.time()
    monkeypatch.setattr(broadcast.time, "time", lambda: now)
    fresh = broadcast.create_broadcast("fresh")
    monkeypatch.setattr(broadcast.time, "time", lambda: now - broadcast.RETENTION_DAYS * 86400 - 60)
    broadcast.create_broadcast("stale")
    monkeypatch.setattr(broadcast.time, "time", lambda: now)
    broadcast._last_pruned = None

    remaining = broadcast.list_broadcasts()
    assert [r["id"] for r in remaining] == [fresh["id"]]


def test_prune_keeps_broadcast_inside_the_window(tmp_path, monkeypatch):
    now = time.time()
    monkeypatch.setattr(broadcast.time, "time", lambda: now - broadcast.RETENTION_DAYS * 86400 + 60)
    kept = broadcast.create_broadcast("just inside")
    monkeypatch.setattr(broadcast.time, "time", lambda: now)
    broadcast._last_pruned = None

    assert [r["id"] for r in broadcast.list_broadcasts()] == [kept["id"]]


def test_get_broadcast_returns_none_for_unknown(tmp_path):
    assert broadcast.get_broadcast(42) is None
    assert broadcast.get_broadcast(None) is None


def test_get_broadcast_ignores_ids_that_are_not_a_number(tmp_path):
    """Ids come from inline buttons and panel URLs, so they are not trusted."""
    record = broadcast.create_broadcast("hello")
    assert broadcast.get_broadcast("1.deliveries") is None
    assert broadcast.get_broadcast("not-an-id") is None
    assert broadcast.get_broadcast(str(record["id"]))["text"] == "hello"


# --------------------------------------------------------------------------
# Delivery
# --------------------------------------------------------------------------

def test_deliver_records_every_chat_it_reached(tmp_path, monkeypatch):
    monkeypatch.setattr(broadcast, "BATCH_PAUSE", 0)
    users.record_user(11, "Ann", "ann")
    users.record_user(12, "Ben", "ben")
    record_group(-1001, "Group One", "supergroup")
    sent = capture_sends()
    record = broadcast.create_broadcast("**news**")

    deliver(record["id"])

    stored = broadcast.get_broadcast(record["id"])
    assert stored["sent"] == 3
    assert stored["failed"] == 0
    assert sorted(stored["deliveries"]) == ["-1001", "11", "12"]
    assert len(sent) == 3
    assert sent[0][1] == "<b>news</b>"
    assert all(kwargs["parse_mode"] == "HTML" for _, _, kwargs in sent)


def test_deliver_keeps_going_when_one_recipient_blocks(tmp_path, monkeypatch):
    monkeypatch.setattr(broadcast, "BATCH_PAUSE", 0)
    users.record_user(11, "Ann", "ann")
    users.record_user(12, "Ben", "ben")
    users.record_user(13, "Cal", "cal")
    capture_sends(fail_for=[11])
    record = broadcast.create_broadcast("news")

    deliver(record["id"])

    stored = broadcast.get_broadcast(record["id"])
    assert stored["sent"] == 2
    assert stored["dead"] == 1
    assert stored["failed"] == 0
    # The blocked account is flagged so future broadcasts skip it.
    assert users.get_user("11")["dead"] is True
    assert "11" not in stored["deliveries"]


def test_deliver_counts_plain_failures_without_pruning(tmp_path, monkeypatch):
    monkeypatch.setattr(broadcast, "BATCH_PAUSE", 0)
    users.record_user(11, "Ann", "ann")
    # A non-blocking failure is tallied, and the user stays in the registry.
    capture_sends(fail_for=[11], failure=telegram_error(400, "Bad Request: chat not found"))
    record = broadcast.create_broadcast("news")
    deliver(record["id"])

    stored = broadcast.get_broadcast(record["id"])
    assert stored["failed"] == 1
    assert stored["dead"] == 0
    assert users.get_user("11")["dead"] is False


def test_deliver_survives_non_telegram_exceptions(tmp_path, monkeypatch):
    monkeypatch.setattr(broadcast, "BATCH_PAUSE", 0)
    users.record_user(11, "Ann", "ann")
    users.record_user(12, "Ben", "ben")

    async def fake_send_message(chat_id, text, **kwargs):
        if str(chat_id) == "11":
            raise RuntimeError("network exploded")
        return type("Sent", (), {"message_id": 5, "chat": make_chat(chat_id)})()

    bot.send_message = fake_send_message
    record = broadcast.create_broadcast("news")
    deliver(record["id"])

    stored = broadcast.get_broadcast(record["id"])
    assert stored["sent"] == 1
    assert stored["failed"] == 1


def test_deliver_reports_when_there_is_nobody_to_tell(tmp_path, monkeypatch):
    sent = capture_sends()
    record = broadcast.create_broadcast("news")

    deliver(record["id"])

    assert len(sent) == 1
    assert "No recipients" in sent[0][1]
    assert broadcast.get_broadcast(record["id"])["sent"] == 0


def test_deliver_can_hide_link_previews(tmp_path, monkeypatch):
    monkeypatch.setattr(broadcast, "BATCH_PAUSE", 0)
    users.record_user(11, "Ann", "ann")
    sent = capture_sends()
    record = broadcast.create_broadcast("news", preview=False)

    deliver(record["id"])

    assert sent[0][2]["disable_web_page_preview"] is True


def test_deliver_attaches_a_url_button(tmp_path, monkeypatch):
    monkeypatch.setattr(broadcast, "BATCH_PAUSE", 0)
    users.record_user(11, "Ann", "ann")
    sent = capture_sends()
    record = broadcast.create_broadcast(
        "news", button={"text": "Read more", "url": "https://example.com"},
    )

    deliver(record["id"])

    markup = sent[0][2]["reply_markup"]
    assert markup.keyboard[0][0].url == "https://example.com"
    assert markup.keyboard[0][0].text == "Read more"


def test_long_messages_are_split_before_html_rendering(tmp_path, monkeypatch):
    monkeypatch.setattr(broadcast, "BATCH_PAUSE", 0)
    users.record_user(11, "Ann", "ann")
    sent = capture_sends()
    record = broadcast.create_broadcast("word " * 2000)

    deliver(record["id"])

    assert len(sent) > 1
    assert all(len(text) <= broadcast.MESSAGE_LIMIT for _, text, _ in sent)


def test_media_broadcast_sends_the_attachment(tmp_path, monkeypatch):
    monkeypatch.setattr(broadcast, "BATCH_PAUSE", 0)
    users.record_user(11, "Ann", "ann")
    sent = capture_sends()
    photos = []

    async def fake_send_photo(chat_id, photo, **kwargs):
        photos.append((chat_id, photo, kwargs))
        return type("Sent", (), {"message_id": 7, "chat": make_chat(chat_id)})()

    bot.send_photo = fake_send_photo
    record = broadcast.create_broadcast(
        "caption", media={"type": "photo", "file_id": "FILEID"},
    )

    deliver(record["id"])

    assert not sent
    assert photos[0][1] == "FILEID"
    assert photos[0][2]["caption"] == "caption"
    assert broadcast.get_broadcast(record["id"])["sent"] == 1


def test_start_delivery_refuses_to_run_twice(tmp_path):
    users.record_user(11, "Ann", "ann")
    capture_sends()
    first = broadcast.create_broadcast("one")
    second = broadcast.create_broadcast("two")

    async def run():
        assert broadcast.start_delivery(first["id"], OWNER) is not None
        assert broadcast.start_delivery(second["id"], OWNER) is None
        assert broadcast.is_running() is True
        await broadcast._active["task"]
        assert broadcast.is_running() is False

    asyncio.run(run())
    assert broadcast.get_broadcast(first["id"])["sent"] == 1
    assert broadcast.get_broadcast(second["id"])["sent"] == 0


# --------------------------------------------------------------------------
# Recall
# --------------------------------------------------------------------------

def test_recall_deletes_every_delivered_message(tmp_path, monkeypatch):
    monkeypatch.setattr(broadcast, "BATCH_PAUSE", 0)
    users.record_user(11, "Ann", "ann")
    record_group(-1001, "Group One", "supergroup")
    capture_sends()
    record = broadcast.create_broadcast("news")
    deliver(record["id"])

    deleted = []

    async def fake_delete_message(chat_id, message_id, **kwargs):
        deleted.append((chat_id, message_id))
        return True

    bot.delete_message = fake_delete_message
    result = asyncio.run(broadcast.recall(record["id"]))

    assert result == {"deleted": 2, "failed": 0, "total": 2}
    assert sorted(chat_id for chat_id, _ in deleted) == [-1001, 11]
    assert broadcast.get_broadcast(record["id"])["recalled"] is True


def test_recall_tallies_deletions_it_could_not_perform(tmp_path, monkeypatch):
    monkeypatch.setattr(broadcast, "BATCH_PAUSE", 0)
    record = broadcast.create_broadcast("news")
    broadcast._update_record(record["id"], {"deliveries": {"11": 1, "12": 2}})

    async def fake_delete_message(chat_id, message_id, **kwargs):
        if str(chat_id) == "11":
            raise telegram_error(400, "Bad Request: message to delete not found")
        return True

    bot.delete_message = fake_delete_message
    result = asyncio.run(broadcast.recall(record["id"]))

    assert result["deleted"] == 1
    assert result["failed"] == 1
    stored = broadcast.get_broadcast(record["id"])
    assert stored["recalled"] is True
    assert stored["delete_failed"] == 1


def test_recall_of_unknown_broadcast_is_a_noop(tmp_path):
    assert asyncio.run(broadcast.recall(99)) == {"deleted": 0, "failed": 0, "total": 0}


def test_recall_with_nothing_delivered(tmp_path, monkeypatch):
    monkeypatch.setattr(broadcast, "BATCH_PAUSE", 0)
    record = broadcast.create_broadcast("news")
    result = asyncio.run(broadcast.recall(record["id"]))
    assert result == {"deleted": 0, "failed": 0, "total": 0}


# --------------------------------------------------------------------------
# Error classification
# --------------------------------------------------------------------------

def test_blocked_user_is_classified_as_dead():
    exc = telegram_error(403, "Forbidden: bot was blocked by the user")
    assert broadcast._classify_error(exc) == "dead"


def test_deactivated_user_is_classified_as_dead():
    exc = telegram_error(400, "Bad Request: user is deactivated")
    assert broadcast._classify_error(exc) == "dead"


def test_rate_limit_is_classified_as_retryable():
    assert broadcast._classify_error(telegram_error(429, "Too Many Requests")) == "retry"


def test_other_telegram_errors_are_plain_failures():
    assert broadcast._classify_error(telegram_error(400, "Bad Request: chat not found")) == "failed"
    assert broadcast._classify_error(RuntimeError("boom")) == "failed"


def test_retry_after_is_read_from_the_response():
    exc = ApiTelegramException(
        "sendMessage", None,
        {"error_code": 429, "description": "Too Many Requests",
         "parameters": {"retry_after": 12}},
    )
    assert broadcast._retry_after(exc) == 12.0
    assert broadcast._retry_after(telegram_error(429, "nope")) == 5.0


# --------------------------------------------------------------------------
# Command flow
# --------------------------------------------------------------------------

def stub_bot():
    """Stub the bot methods the command handlers touch."""
    calls = {"reply": [], "sent": [], "edited": [], "markup": [], "answers": []}

    async def fake_reply_to(message, text, **kwargs):
        calls["reply"].append(text)
        return type("Sent", (), {"message_id": 1, "chat": message.chat})()

    async def fake_send_message(chat_id, text, **kwargs):
        calls["sent"].append((chat_id, text, kwargs))
        return type("Sent", (), {"message_id": 50 + len(calls["sent"]),
                                 "chat": make_chat(chat_id)})()

    async def fake_edit_message_text(text, chat_id=None, message_id=None, **kwargs):
        calls["edited"].append(text)
        return True

    async def fake_edit_message_reply_markup(chat_id, message_id, reply_markup=None, **kwargs):
        calls["markup"].append(reply_markup)
        return True

    async def fake_answer_callback_query(call_id, text=None, **kwargs):
        calls["answers"].append((text, kwargs))
        return True

    bot.reply_to = fake_reply_to
    bot.send_message = fake_send_message
    bot.edit_message_text = fake_edit_message_text
    bot.edit_message_reply_markup = fake_edit_message_reply_markup
    bot.answer_callback_query = fake_answer_callback_query
    return calls


def make_call(data, uid=OWNER, message_id=50):
    return type("Call", (), {
        "id": "call1", "data": data, "from_user": make_user(uid=uid),
        "message": type("Msg", (), {"chat": make_chat(uid), "message_id": message_id})(),
    })()


def pending_tokens() -> list:
    return list(broadcast._pending_db().get("pending", {}))


def run_callback(call):
    async def run():
        await mod.handle_broadcast_callback(call)
        task = broadcast._active.get("task")
        if task is not None:
            await task

    broadcast.BATCH_PAUSE = 0
    asyncio.run(run())


def test_owner_broadcast_previews_before_sending(tmp_path, monkeypatch):
    monkeypatch.setattr(broadcast, "BATCH_PAUSE", 0)
    users.record_user(11, "Ann", "ann")
    record_group(-1001, "Group One", "supergroup")
    calls = stub_bot()

    asyncio.run(mod.broadcast_command(make_msg("/broadcast **news**", chat_id=OWNER)))

    # Nothing is delivered, only a preview with confirm buttons.
    preview = calls["sent"][-1]
    assert "<b>news</b>" in preview[1]
    assert "not sent yet" in preview[1]
    assert preview[2]["parse_mode"] == "HTML"
    assert broadcast.list_broadcasts() == []

    buttons = calls["markup"][-1].keyboard[0]
    assert [b.text for b in buttons] == ["Send now", "Cancel"]
    assert buttons[0].callback_data.startswith("bc_send:")


def test_confirming_a_preview_starts_delivery(tmp_path, monkeypatch):
    monkeypatch.setattr(broadcast, "BATCH_PAUSE", 0)
    users.record_user(11, "Ann", "ann")
    record_group(-1001, "Group One", "supergroup")
    stub_bot()

    asyncio.run(mod.broadcast_command(make_msg("/broadcast news", chat_id=OWNER)))
    (token,) = pending_tokens()

    run_callback(make_call(f"bc_send:{token}"))

    records = broadcast.list_broadcasts()
    assert len(records) == 1
    assert records[0]["sent"] == 2
    assert sorted(records[0]["deliveries"]) == ["-1001", "11"]
    assert broadcast.get_pending(token) is None


def test_cancelling_a_preview_sends_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(broadcast, "BATCH_PAUSE", 0)
    users.record_user(11, "Ann", "ann")
    calls = stub_bot()

    asyncio.run(mod.broadcast_command(make_msg("/broadcast news", chat_id=OWNER)))
    (token,) = pending_tokens()

    run_callback(make_call(f"bc_cancel:{token}"))

    assert broadcast.list_broadcasts() == []
    assert broadcast.get_pending(token) is None
    assert "Broadcast cancelled." in calls["edited"]


def test_expired_preview_cannot_be_sent(tmp_path, monkeypatch):
    now = time.time()
    monkeypatch.setattr(broadcast.time, "time", lambda: now)
    calls = stub_bot()
    token = broadcast.stage_pending("news")
    monkeypatch.setattr(broadcast.time, "time", lambda: now + broadcast.PENDING_TTL + 1)

    run_callback(make_call(f"bc_send:{token}"))

    assert broadcast.list_broadcasts() == []
    assert "Preview expired." in calls["edited"]


def test_non_owner_cannot_broadcast(tmp_path):
    calls = stub_bot()
    asyncio.run(mod.broadcast_command(make_msg("/broadcast news", chat_id=11)))
    assert calls["reply"] == ["Owner only."]
    assert broadcast._pending_db().get("pending", {}) == {}


def test_non_owner_cannot_confirm_a_preview(tmp_path):
    users.record_user(11, "Ann", "ann")
    calls = stub_bot()
    token = broadcast.stage_pending("news")

    run_callback(make_call(f"bc_send:{token}", uid=11))

    assert broadcast.list_broadcasts() == []
    assert broadcast.get_pending(token) is not None
    assert calls["answers"][0][1].get("show_alert") is True


def test_broadcast_refuses_to_run_in_a_group(tmp_path):
    calls = stub_bot()
    asyncio.run(mod.broadcast_command(
        make_msg("/broadcast news", chat_id=-1001, chat_type="supergroup", uid=OWNER)))
    assert calls["reply"] == ["Broadcasts are sent from a private chat with me."]


def test_broadcast_without_text_shows_help(tmp_path):
    users.record_user(11, "Ann", "ann")
    calls = stub_bot()
    asyncio.run(mod.broadcast_command(make_msg("/broadcast", chat_id=OWNER)))
    assert "/bcast_delete" in calls["sent"][-1][1]
    assert broadcast._pending_db().get("pending", {}) == {}


def test_segment_flag_narrows_the_audience(tmp_path, monkeypatch):
    monkeypatch.setattr(broadcast, "BATCH_PAUSE", 0)
    users.record_user(11, "Ann", "ann")
    record_group(-1001, "Group One", "supergroup")
    stub_bot()

    asyncio.run(mod.broadcast_command(make_msg("/broadcast groups news", chat_id=OWNER)))
    (token,) = pending_tokens()
    run_callback(make_call(f"bc_send:{token}"))

    (record,) = broadcast.list_broadcasts()
    assert record["segment"] == "groups"
    assert list(record["deliveries"]) == ["-1001"]


def test_broadcast_with_nobody_to_tell_is_refused(tmp_path):
    calls = stub_bot()
    asyncio.run(mod.broadcast_command(make_msg("/broadcast news", chat_id=OWNER)))
    assert calls["reply"] == ["Nobody to broadcast to yet."]


def test_second_broadcast_is_refused_while_one_runs(tmp_path):
    users.record_user(11, "Ann", "ann")
    stub_bot()
    broadcast._active.update({"id": 1, "total": 1})
    calls = stub_bot()

    asyncio.run(mod.broadcast_command(make_msg("/broadcast news", chat_id=OWNER)))
    assert calls["reply"] == ["A broadcast is already running."]


def test_bcast_list_reports_previous_broadcasts(tmp_path):
    users.record_user(11, "Ann", "ann")
    broadcast.create_broadcast("first", segment="users")
    calls = stub_bot()

    asyncio.run(mod.broadcast_list(make_msg("/bcast_list", chat_id=OWNER)))

    listing = calls["sent"][-1][1]
    assert "#1" in listing
    assert "users" in listing


def test_bcast_list_without_history(tmp_path):
    calls = stub_bot()
    asyncio.run(mod.broadcast_list(make_msg("/bcast_list", chat_id=OWNER)))
    assert calls["reply"] == ["No broadcasts sent yet."]


def test_bcast_delete_removes_delivered_messages(tmp_path, monkeypatch):
    monkeypatch.setattr(broadcast, "BATCH_PAUSE", 0)
    users.record_user(11, "Ann", "ann")
    record = broadcast.create_broadcast("news")
    broadcast._update_record(record["id"], {"deliveries": {"11": 42}})
    calls = stub_bot()
    deleted = []

    async def fake_delete_message(chat_id, message_id, **kwargs):
        deleted.append((chat_id, message_id))
        return True

    bot.delete_message = fake_delete_message
    asyncio.run(mod.broadcast_delete(make_msg("/bcast_delete 1", chat_id=OWNER)))

    assert deleted == [(11, 42)]
    assert "Deleted 1 of 1 messages" in calls["reply"][-1]


def test_bcast_delete_rejects_unknown_ids(tmp_path):
    calls = stub_bot()
    asyncio.run(mod.broadcast_delete(make_msg("/bcast_delete 9", chat_id=OWNER)))
    assert calls["reply"] == ["No broadcast with ID 9."]

    asyncio.run(mod.broadcast_delete(make_msg("/bcast_delete", chat_id=OWNER)))
    assert calls["reply"][-1] == "Usage: /bcast_delete <id>"


def test_unsubscribe_and_subscribe(tmp_path):
    calls = stub_bot()
    user = make_user(uid=11, first_name="Ann")

    msg = type("Msg", (), {"chat": make_chat(11), "from_user": user})()
    asyncio.run(mod.unsubscribe(msg))
    assert users.is_opted_out(11) is True
    assert calls["reply"][-1] == "You will no longer receive broadcasts."

    asyncio.run(mod.unsubscribe(msg))
    assert calls["reply"][-1] == "You are already unsubscribed."

    asyncio.run(mod.subscribe(msg))
    assert users.is_opted_out(11) is False
    assert calls["reply"][-1] == "You will receive broadcasts again."


def test_opted_out_users_are_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(broadcast, "BATCH_PAUSE", 0)
    users.record_user(11, "Ann", "ann")
    users.record_user(12, "Ben", "ben")
    users.set_opt_out(12, True)
    stub_bot()
    real_send = bot.send_message
    delivered = []

    async def tracking_send(chat_id, text, **kwargs):
        delivered.append(chat_id)
        return await real_send(chat_id, text, **kwargs)

    bot.send_message = tracking_send
    record = broadcast.create_broadcast("news")
    deliver(record["id"])

    assert delivered == [11]
