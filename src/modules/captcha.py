import json, os, time, asyncio
from core.imysdb import IMYDB
from info import bot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
from telebot.formatting import hbold
from core.activity import log_event, user_label

CAPTCHA_TIMEOUT = 180
MAX_QUESTIONS = 3
MAX_KICKS = 3
SWEEP_INTERVAL = 10
JOIN_MSG_TTL = 600

SILENT_EXITS = set()

# Lock dict for concurrency (populated at module load)
LOCKS = {}

def session_key(chat_id, user_id):
    return f"{chat_id}:{user_id}"

def get_captcha_questions(db):
    q = db.get('captcha_questions')
    if q and isinstance(q, list) and len(q) > 0:
        return q
    # lazy legacy migration
    legacy_q = db.get('captcha_q')
    if legacy_q is not None and legacy_q != '':
        opts = db.get('captcha_opts', [])
        ans = db.get('captcha_ans')
        return [{"q": legacy_q, "opts": opts, "ans": ans}]
    return []

def validate_question(q, opts, ans):
    if not isinstance(q, str) or q.strip() == '':
        return "Question must be non-empty."
    if not isinstance(opts, list) or len(opts) < 2:
        return "At least 2 options required."
    cleaned = [str(o).strip() for o in opts]
    if len(cleaned) != len(set(cleaned)):
        return "Options must be unique (case-sensitive after strip)."
    if any(len(o) > 60 for o in cleaned):
        return "Each option must be at most 60 characters."
    if len(cleaned) > 8:
        return "At most 8 options allowed."
    if ans not in cleaned:
        return "Correct answer must be one of the options."
    return None

def add_question(db, q, opts, ans):
    questions = get_captcha_questions(db) or []
    if len(questions) >= MAX_QUESTIONS:
        return "Maximum of 3 questions. Remove one first."
    err = validate_question(q, opts, ans)
    if err:
        return err
    questions.append({"q": q.strip(), "opts": [str(o).strip() for o in opts], "ans": str(ans).strip()})
    db.set('captcha_questions', questions)
    # delete legacy keys when writing new format
    for k in ('captcha_q', 'captcha_opts', 'captcha_ans', 'user_attempts'):
        try:
            db.delete(k)
        except Exception:
            pass
    return None

def remove_question(db, index):
    questions = get_captcha_questions(db) or []
    if index < 1 or index > len(questions):
        return False
    questions.pop(index - 1)
    db.set('captcha_questions', questions)
    for k in ('captcha_q', 'captcha_opts', 'captcha_ans', 'user_attempts'):
        try:
            db.delete(k)
        except Exception:
            pass
    return True

def create_session(chat_id, user_id, name, now):
    key = session_key(chat_id, user_id)
    session = {
        "chat_id": chat_id,
        "user_id": user_id,
        "joined_at": now,
        "deadline": now + CAPTCHA_TIMEOUT,
        "q_index": 0,
        "tries": 0,
        "group_msg_id": None,
        "pm_msg_id": None,
        "join_msg_id": None,
        "started": False,
        "name": name,
    }
    db = IMYDB('runtime/captcha/pending.json')
    sessions = db.get('sessions') or {}
    sessions[key] = session
    db.set('sessions', sessions)
    return session

def get_session(chat_id, user_id):
    db = IMYDB('runtime/captcha/pending.json')
    sessions = db.get('sessions') or {}
    return sessions.get(session_key(chat_id, user_id))

def save_session(chat_id, user_id, session):
    db = IMYDB('runtime/captcha/pending.json')
    sessions = db.get('sessions') or {}
    sessions[session_key(chat_id, user_id)] = session
    db.set('sessions', sessions)

def delete_session(chat_id, user_id):
    db = IMYDB('runtime/captcha/pending.json')
    sessions = db.get('sessions') or {}
    key = session_key(chat_id, user_id)
    if key in sessions:
        del sessions[key]
        db.set('sessions', sessions)

def list_sessions():
    db = IMYDB('runtime/captcha/pending.json')
    return list((db.get('sessions') or {}).values())

def remember_join_msg(chat_id, user_id, message_id, now):
    db = IMYDB('runtime/captcha/join_msgs.json')
    msgs = db.get('msgs') or {}
    msgs[session_key(chat_id, user_id)] = {"message_id": message_id, "ts": now}
    msgs = {k: v for k, v in msgs.items() if now - v.get("ts", 0) <= JOIN_MSG_TTL}
    db.set('msgs', msgs)

def pop_join_msg(chat_id, user_id):
    db = IMYDB('runtime/captcha/join_msgs.json')
    msgs = db.get('msgs') or {}
    entry = msgs.pop(session_key(chat_id, user_id), None)
    if entry is None:
        return None
    db.set('msgs', msgs)
    return entry.get("message_id")

def attach_join_msg_to_session(chat_id, user_id, message_id):
    session = get_session(chat_id, user_id)
    if session is None:
        return False
    session["join_msg_id"] = message_id
    save_session(chat_id, user_id, session)
    return True

def is_expired(session, now):
    return now >= session.get("deadline", 0)

def register_wrong_answer(session, max_tries):
    session["tries"] = session.get("tries", 0) + 1
    if session["tries"] >= max_tries:
        return "kick"
    return "retry"

def register_correct_answer(session, total_questions):
    session["q_index"] = session.get("q_index", 0) + 1
    if session["q_index"] >= total_questions:
        return "done"
    return "next"

def get_kicks(chat_id, user_id):
    db = IMYDB('runtime/captcha/kicks.json')
    kicks = db.get('kicks') or {}
    return kicks.get(session_key(chat_id, user_id), 0)

def increment_kicks(chat_id, user_id):
    db = IMYDB('runtime/captcha/kicks.json')
    kicks = db.get('kicks') or {}
    key = session_key(chat_id, user_id)
    kicks[key] = kicks.get(key, 0) + 1
    db.set('kicks', kicks)
    return kicks[key]

def reset_kicks(chat_id, user_id):
    db = IMYDB('runtime/captcha/kicks.json')
    kicks = db.get('kicks') or {}
    key = session_key(chat_id, user_id)
    if key in kicks:
        kicks[key] = 0
        db.set('kicks', kicks)

def decide_punishment(kick_count):
    return "ban" if kick_count >= MAX_KICKS else "kick"


def _get_lock(key):
    if key not in LOCKS:
        LOCKS[key] = asyncio.Lock()
    return LOCKS[key]

_BOT_USERNAME = None

async def _bot_username():
    global _BOT_USERNAME
    if _BOT_USERNAME is None:
        try:
            me = await bot.get_me()
            _BOT_USERNAME = me.username
        except Exception:
            _BOT_USERNAME = "bot"
    return _BOT_USERNAME

async def handle_join_service_message(m):
    members = m.new_chat_members or []
    if len(members) != 1:
        return
    user = members[0]
    if getattr(user, "is_bot", False):
        return
    chat_id = m.chat.id
    user_id = user.id
    if not attach_join_msg_to_session(chat_id, user_id, m.message_id):
        remember_join_msg(chat_id, user_id, m.message_id, time.time())

async def start_verification(chat, user, db):
    perms = ChatPermissions(
        can_send_messages=False, can_send_media_messages=False,
        can_send_polls=False, can_send_other_messages=False,
        can_add_web_page_previews=False,
        can_send_audios=False, can_send_documents=False,
        can_send_photos=False, can_send_videos=False,
        can_send_video_notes=False, can_send_voice_notes=False,
    )
    try:
        await bot.restrict_chat_member(chat.id, user.id, permissions=perms)
    except Exception as e:
        # failure: fall back to greeting, log
        from modules.greetings import send_standard_greeting
        await send_standard_greeting(chat.id, user, db)
        return
    questions = get_captcha_questions(db)
    if not questions:
        from modules.greetings import send_standard_greeting
        await send_standard_greeting(chat.id, user, db)
        return
    now = time.time()
    session = create_session(chat.id, user.id, getattr(user, 'first_name', 'User') or 'User', now)
    join_msg_id = pop_join_msg(chat.id, user.id)
    if join_msg_id is not None:
        session["join_msg_id"] = join_msg_id
        save_session(chat.id, user.id, session)
    # group prompt with URL button
    username = await _bot_username()
    url = f"https://t.me/{username}?start=cap_{chat.id}"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Verify in PM", url=url))
    name = getattr(user, 'first_name', '') or 'User'
    # escape name with project's HTML helpers not directly imported; minimal escape
    safe_name = str(name).replace('<','&lt;').replace('>','&gt;')
    msg = await bot.send_message(chat.id, f"Welcome {safe_name}! You're muted until you verify. Press the button to verify in PM within 3 minutes.", reply_markup=markup)
    session["group_msg_id"] = msg.message_id
    save_session(chat.id, user.id, session)
    # best-effort direct PM
    try:
        await _send_question_pm(chat.id, user.id, session)
        session["started"] = True
        save_session(chat.id, user.id, session)
    except Exception:
        pass

async def _send_question_pm(chat_id, user_id, session):
    db = IMYDB(f'runtime/greetings/{str(chat_id).lstrip("-")}_greetings.json')
    questions = get_captcha_questions(db)
    q_idx = session.get("q_index", 0)
    if not questions or q_idx >= len(questions):
        return
    q = questions[q_idx]
    total = len(questions)
    tries = session.get("tries", 0)
    max_tries = db.get('captcha_max_tries', 1)
    left = max(0, max_tries - tries)
    time_left = max(0, int(session.get("deadline", 0) - time.time()))
    mins, secs = divmod(time_left, 60)
    text = f"Question {q_idx+1}/{total}\n{q['q']}\nTime left: {mins}:{secs:02d}\nAttempts left: {left}"
    # shuffle options
    import random
    opts = q['opts'][:]
    random.shuffle(opts)
    markup = InlineKeyboardMarkup()
    for i, opt in enumerate(opts):
        # original index preserved by option text lookup in handler
        # We use option index in original list for callback
        original_idx = q['opts'].index(opt)
        markup.add(InlineKeyboardButton(opt, callback_data=f"v_cap:{chat_id}:{q_idx}:{original_idx}"))
    msg = await bot.send_message(user_id, text, reply_markup=markup, parse_mode="HTML")
    session["pm_msg_id"] = msg.message_id
    save_session(chat_id, user_id, session)

async def handle_start_payload(m):
    args = m.text.split() if m.text else []
    if len(args) < 2:
        return await bot.reply_to(m, "Invalid verification link.")
    payload = args[1]
    if not payload.startswith("cap_"):
        return await bot.reply_to(m, "Invalid verification link.")
    try:
        chat_id = int(payload[4:])
    except Exception:
        return await bot.reply_to(m, "Invalid verification link.")
    session = get_session(chat_id, m.from_user.id)
    if session is None:
        return await bot.reply_to(m, "You don't have a pending verification. If you were removed, you can rejoin the group and try again.")
    now = time.time()
    if is_expired(session, now):
        await punish(session, "timeout")
        return await bot.reply_to(m, "Time's up.")
    if session.get("started"):
        # re-send current question
        await _send_question_pm(chat_id, m.from_user.id, session)
        return
    session["started"] = True
    save_session(chat_id, m.from_user.id, session)
    await _send_question_pm(chat_id, m.from_user.id, session)

async def handle_captcha_callback(call):
    data = call.data or ""
    if not data.startswith("v_cap:"):
        return await bot.answer_callback_query(call.id, "Expired.")
    parts = data.split(":")
    # old-format has option text in second field; detect by second part not int
    if len(parts) < 4 or not parts[2].lstrip('-').isdigit() or not parts[3].isdigit():
        return await bot.answer_callback_query(call.id, "This captcha has expired. Rejoin the group to try again.", show_alert=True)
    try:
        chat_id = int(parts[1])
        q_index = int(parts[2])
        opt_index = int(parts[3])
    except Exception:
        return await bot.answer_callback_query(call.id, "Invalid.", show_alert=True)
    if call.message.chat.type != "private":
        return await bot.answer_callback_query(call.id, "Verify in PM.", show_alert=True)
    key = session_key(chat_id, call.from_user.id)
    lock = _get_lock(key)
    async with lock:
        session = get_session(chat_id, call.from_user.id)
        if session is None:
            try:
                await bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception:
                pass
            return await bot.answer_callback_query(call.id, "This verification is no longer active.", show_alert=True)
        now = time.time()
        if is_expired(session, now):
            await punish_locked(session, "timeout")
            return await bot.answer_callback_query(call.id, "Time's up.", show_alert=True)
        if session.get("q_index") != q_index:
            return await bot.answer_callback_query(call.id, "That question is no longer active.", show_alert=True)
        db = IMYDB(f'runtime/greetings/{str(chat_id).lstrip("-")}_greetings.json')
        questions = get_captcha_questions(db)
        if not questions or q_index >= len(questions):
            # edited mid-session past end -> finish success
            await finish_success(session, None)
            return await bot.answer_callback_query(call.id, "Done!")
        q = questions[q_index]
        if opt_index < 0 or opt_index >= len(q['opts']):
            return await bot.answer_callback_query(call.id, "Invalid option.", show_alert=True)
        chosen_text = q['opts'][opt_index]
        correct_text = q['ans']
        max_tries = db.get('captcha_max_tries', 1)
        if chosen_text == correct_text:
            result = register_correct_answer(session, len(questions))
            save_session(chat_id, call.from_user.id, session)
            if result == "done":
                await finish_success(session, call.from_user)
                return await bot.answer_callback_query(call.id, "Correct!")
            else:
                await _send_question_pm(chat_id, call.from_user.id, session)
                return await bot.answer_callback_query(call.id, "Correct!")
        else:
            result = register_wrong_answer(session, max_tries)
            save_session(chat_id, call.from_user.id, session)
            log_event("captcha_fail", chat_id=chat_id, user_id=call.from_user.id, detail=f"q{q_index+1} attempt {session['tries']}/{max_tries}")
            if result == "kick":
                await bot.answer_callback_query(call.id, "Too many wrong answers.", show_alert=True)
                await punish_locked(session, "max_tries")
            else:
                await bot.answer_callback_query(call.id, f"Wrong! {max_tries - session['tries']} attempts left.", show_alert=True)
                await _send_question_pm(chat_id, call.from_user.id, session)

async def finish_success(session, user):
    chat_id = session.get("chat_id")
    user_id = session.get("user_id")
    # lock not strictly needed here because caller usually holds it or session is being finalized
    delete_session(chat_id, user_id)
    pop_join_msg(chat_id, user_id)
    reset_kicks(chat_id, user_id)
    # unmute with group default permissions
    try:
        chat = await bot.get_chat(chat_id)
        perms = getattr(chat, 'permissions', None)
        if perms is None:
            perms = ChatPermissions(
                can_send_messages=True, can_send_media_messages=True,
                can_send_polls=True, can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_send_audios=True, can_send_documents=True,
                can_send_photos=True, can_send_videos=True,
                can_send_video_notes=True, can_send_voice_notes=True,
            )
        await bot.restrict_chat_member(chat_id, user_id, permissions=perms)
    except Exception as e:
        pass
    # delete messages
    try:
        if session.get("group_msg_id"):
            await bot.delete_message(chat_id, session["group_msg_id"])
    except Exception:
        pass
    try:
        if session.get("pm_msg_id"):
            await bot.delete_message(user_id, session["pm_msg_id"])
    except Exception:
        pass
    # PM user
    try:
        if user:
            title = getattr(await bot.get_chat(chat_id), 'title', 'group')
            await bot.send_message(user_id, f"Verified! You can now chat in {title}.")
    except Exception:
        pass
    # greeting in group
    try:
        if user:
            from modules.greetings import send_standard_greeting
            db = IMYDB(f'runtime/greetings/{str(chat_id).lstrip("-")}_greetings.json')
            await send_standard_greeting(chat_id, user, db)
    except Exception:
        pass
    log_event("captcha_pass", chat_id=chat_id, user_id=user_id, detail="pm")

async def punish(session, reason):
    """Entry point for callers that do not hold the lock."""
    key = session_key(session.get("chat_id"), session.get("user_id"))
    lock = _get_lock(key)
    async with lock:
        await punish_locked(session, reason)

async def punish_locked(session, reason):
    """Caller MUST already hold the session lock; asyncio.Lock is not re-entrant."""
    chat_id = session.get("chat_id")
    user_id = session.get("user_id")
    fresh = get_session(chat_id, user_id)
    if fresh is None:
        return
    key = session_key(chat_id, user_id)
    # re-read so a stale sweeper snapshot can't kick a user who already verified
    join_msg_id = fresh.get("join_msg_id")
    # delete session first
    delete_session(chat_id, user_id)
    SILENT_EXITS.add(key)
    count = increment_kicks(chat_id, user_id)
    action = decide_punishment(count)
    # execute
    try:
        if action == "kick":
            await bot.ban_chat_member(chat_id, user_id)
            await bot.unban_chat_member(chat_id, user_id, only_if_banned=True)
        elif action == "ban":
            await bot.ban_chat_member(chat_id, user_id)
    except Exception:
        pass
    # delete messages
    try:
        if session.get("group_msg_id"):
            await bot.delete_message(chat_id, session["group_msg_id"])
    except Exception:
        pass
    try:
        if session.get("pm_msg_id"):
            await bot.delete_message(user_id, session["pm_msg_id"])
    except Exception:
        pass
    try:
        if join_msg_id is not None:
            await bot.delete_message(chat_id, join_msg_id)
    except Exception:
        pass
    # notify PM
    try:
        if action == "kick":
            msg = f"You were removed because you {'didn\'t finish in time.' if reason=='timeout' else 'failed the captcha.'} Kicks: {count}/3. Another {3-count} and you'll be banned."
        else:
            msg = "You have been banned from this group after 3 failed verifications."
        await bot.send_message(user_id, msg)
    except Exception:
        pass
    # group notice + schedule delete
    try:
        name = session.get("name", "User")
        if action == "ban":
            txt = f"{name} was banned: 3 failed verifications."
        else:
            txt = f"{name} was removed: {reason}."
        gm = await bot.send_message(chat_id, txt)
        async def _del():
            await asyncio.sleep(30)
            try:
                await bot.delete_message(chat_id, gm.message_id)
            except Exception:
                pass
        asyncio.create_task(_del())
    except Exception:
        pass
    # log events
    if reason == "timeout":
        log_event("captcha_timeout", chat_id=chat_id, user_id=user_id, detail=f"kicks={count}")
    elif action == "kick":
        log_event("captcha_kick", chat_id=chat_id, user_id=user_id, detail=f"kicks={count}")
    elif action == "ban":
        log_event("captcha_ban", chat_id=chat_id, user_id=user_id, detail=f"kicks={count}")

async def captcha_sweeper():
    while True:
        try:
            await asyncio.sleep(SWEEP_INTERVAL)
            now = time.time()
            for sess in list_sessions():
                if is_expired(sess, now):
                    try:
                        await asyncio.wait_for(punish(sess, "timeout"), timeout=30)
                    except Exception:
                        pass
        except Exception:
            pass

async def forget_user(chat_id, user_id):
    delete_session(chat_id, user_id)
    try:
        # group message cleanup not mandatory since session deleted; skip to avoid extra DB
        pass
    except Exception:
        pass