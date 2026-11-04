import asyncio, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
import modules.captcha as captcha
from modules.captcha import (
    get_captcha_questions, validate_question, add_question, remove_question,
    session_key, create_session, get_session, save_session, delete_session,
    list_sessions, is_expired, register_wrong_answer, register_correct_answer,
    get_kicks, increment_kicks, reset_kicks, decide_punishment, MAX_KICKS,
    remember_join_msg, pop_join_msg, attach_join_msg_to_session,
    punish, punish_locked, finish_success, handle_captcha_callback, SILENT_EXITS,
)
from core.imysdb import IMYDB

def tmp_db(tmp_path, name):
    return IMYDB(str(tmp_path / name))

class TestCaptchaQuestions:
    def test_get_new_list(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db = tmp_db(tmp_path, "g.json")
        db.set('captcha_questions', [{"q":"Q","opts":["A","B"],"ans":"A"}])
        assert len(get_captcha_questions(db)) == 1

    def test_legacy_fallback(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db = tmp_db(tmp_path, "g.json")
        db.set('captcha_q', "Old")
        db.set('captcha_opts', ["1","2"])
        db.set('captcha_ans', "1")
        result = get_captcha_questions(db)
        assert result == [{"q":"Old","opts":["1","2"],"ans":"1"}]

    def test_empty(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db = tmp_db(tmp_path, "g.json")
        assert get_captcha_questions(db) == []

class TestValidateQuestion:
    def test_valid(self):
        assert validate_question("Q", ["A","B"], "A") is None

    def test_empty_q(self):
        assert validate_question("", ["A","B"], "A") is not None

    def test_less_than_two_opts(self):
        assert validate_question("Q", ["A"], "A") is not None

    def test_duplicate_opts(self):
        assert validate_question("Q", ["A","A"], "A") is not None

    def test_answer_not_in_opts(self):
        assert validate_question("Q", ["A","B"], "C") is not None

    def test_too_many_opts(self):
        assert validate_question("Q", ["1","2","3","4","5","6","7","8","9"], "1") is not None

    def test_option_too_long(self):
        assert validate_question("Q", ["A","B" + "x"*60], "A") is not None

class TestAddRemove:
    def test_add_rejects_fourth(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db = tmp_db(tmp_path, "g.json")
        for i in range(3):
            assert add_question(db, f"Q{i}", ["A","B"], "A") is None
        assert add_question(db, "Q4", ["A","B"], "A") == "Maximum of 3 questions. Remove one first."

    def test_remove(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        db = tmp_db(tmp_path, "g.json")
        add_question(db, "Q", ["A","B"], "A")
        assert remove_question(db, 1) is True
        assert get_captcha_questions(db) == []

class TestSessions:
    def test_crud(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        s = create_session(-100, 1, "U", 100)
        fetched = get_session(-100, 1)
        assert fetched["name"] == "U"
        delete_session(-100, 1)
        assert get_session(-100, 1) is None

    def test_is_expired(self):
        sess = {"deadline": 100}
        assert is_expired(sess, 99) is False
        assert is_expired(sess, 100) is True
        assert is_expired(sess, 101) is True

    def test_wrong_answer(self):
        s = {"tries": 0}
        assert register_wrong_answer(s, 3) == "retry"
        assert s["tries"] == 1
        s["tries"] = 2
        assert register_wrong_answer(s, 3) == "kick"

    def test_correct_answer(self):
        s = {"q_index": 0}
        assert register_correct_answer(s, 2) == "next"
        assert s["q_index"] == 1
        assert register_correct_answer(s, 2) == "done"

class TestKicks:
    def test_increment_and_decide(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert increment_kicks(-1, 10) == 1
        assert increment_kicks(-1, 10) == 2
        assert decide_punishment(2) == "kick"
        assert decide_punishment(3) == "ban"
        reset_kicks(-1, 10)
        assert get_kicks(-1, 10) == 0

class TestJoinMsgs:
    def test_remember_pop_once(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        remember_join_msg(-100, 1, 555, 1000)
        assert pop_join_msg(-100, 1) == 555
        assert pop_join_msg(-100, 1) is None

    def test_remember_prunes_old(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        remember_join_msg(-100, 1, 111, 1000)
        remember_join_msg(-100, 2, 222, 1000 + 601)
        assert pop_join_msg(-100, 1) is None
        assert pop_join_msg(-100, 2) == 222

    def test_attach_without_session(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert attach_join_msg_to_session(-100, 1, 555) is False
        assert pop_join_msg(-100, 1) is None

    def test_attach_with_session(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        create_session(-100, 1, "U", 100)
        assert attach_join_msg_to_session(-100, 1, 555) is True
        assert get_session(-100, 1)["join_msg_id"] == 555

    def test_create_session_join_msg_id_none(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert create_session(-100, 1, "U", 100)["join_msg_id"] is None

    def test_keys_independent(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        remember_join_msg(-100, 1, 111, 1000)
        remember_join_msg(-100, 2, 222, 1000)
        remember_join_msg(-200, 1, 333, 1000)
        assert pop_join_msg(-100, 1) == 111
        assert pop_join_msg(-100, 2) == 222
        assert pop_join_msg(-200, 1) == 333


class FakeBot:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        async def fn(*args, **kwargs):
            self.calls.append((name, args))
            if name == "send_message":
                return type("Msg", (), {"message_id": 1})()
            return None
        return fn

    def called(self, name):
        return [args for n, args in self.calls if n == name]


class Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def make_callback(chat_id, user_id, option=0):
    return Obj(
        id="cb1",
        data=f"v_cap:{chat_id}:0:{option}",
        from_user=Obj(id=user_id, first_name="U"),
        message=Obj(chat=Obj(type="private", id=user_id), message_id=999),
    )


def setup_group(chat_id, max_tries=1):
    db = IMYDB(f'runtime/greetings/{str(chat_id).lstrip("-")}_greetings.json')
    db.set('captcha_questions', [{"q": "Q", "opts": ["3", "4"], "ans": "4"}])
    db.set('captcha_max_tries', max_tries)


def make_session(chat_id, user_id, join_msg_id=777, deadline=None):
    now = time.time()
    session = create_session(chat_id, user_id, "U", now)
    if deadline is not None:
        session["deadline"] = deadline
    session["join_msg_id"] = join_msg_id
    save_session(chat_id, user_id, session)
    return session


class TestPunish:
    def test_no_deadlock_on_max_tries(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        SILENT_EXITS.clear()
        fake = FakeBot()
        monkeypatch.setattr(captcha, "bot", fake)
        setup_group(-100, max_tries=1)
        make_session(-100, 1)

        async def run():
            await asyncio.wait_for(
                handle_captcha_callback(make_callback(-100, 1, option=0)), 3
            )
        asyncio.run(run())

        assert get_session(-100, 1) is None
        assert fake.called("ban_chat_member")
        assert fake.called("unban_chat_member")
        assert (-100, 777) in fake.called("delete_message")

    def test_no_deadlock_on_expired_in_callback(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        SILENT_EXITS.clear()
        fake = FakeBot()
        monkeypatch.setattr(captcha, "bot", fake)
        setup_group(-101)
        make_session(-101, 1, deadline=time.time() - 1)

        async def run():
            await asyncio.wait_for(
                handle_captcha_callback(make_callback(-101, 1, option=0)), 3
            )
        asyncio.run(run())

        assert get_session(-101, 1) is None
        assert fake.called("ban_chat_member")

    def test_sweeper_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        SILENT_EXITS.clear()
        fake = FakeBot()
        monkeypatch.setattr(captcha, "bot", fake)
        session = make_session(-102, 1, deadline=time.time() - 1)

        asyncio.run(asyncio.wait_for(punish(session, "timeout"), 3))

        assert (-102, 777) in fake.called("delete_message")
        assert fake.called("ban_chat_member")
        assert fake.called("unban_chat_member")

    def test_stale_snapshot_guard(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        SILENT_EXITS.clear()
        fake = FakeBot()
        monkeypatch.setattr(captcha, "bot", fake)
        session = make_session(-103, 1, deadline=time.time() - 1)
        delete_session(-103, 1)

        asyncio.run(asyncio.wait_for(punish(session, "timeout"), 3))

        assert fake.called("ban_chat_member") == []
        assert get_kicks(-103, 1) == 0

    def test_third_kick_bans(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        SILENT_EXITS.clear()
        fake = FakeBot()
        monkeypatch.setattr(captcha, "bot", fake)
        increment_kicks(-104, 1)
        increment_kicks(-104, 1)
        session = make_session(-104, 1, deadline=time.time() - 1)

        asyncio.run(asyncio.wait_for(punish(session, "timeout"), 3))

        assert fake.called("ban_chat_member")
        assert fake.called("unban_chat_member") == []
        assert get_kicks(-104, 1) == MAX_KICKS

    def test_success_leaves_the_notice(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        SILENT_EXITS.clear()
        fake = FakeBot()
        monkeypatch.setattr(captcha, "bot", fake)
        session = make_session(-105, 1)

        asyncio.run(asyncio.wait_for(finish_success(session, None), 3))

        assert (-105, 777) not in fake.called("delete_message")
        assert session_key(-105, 1) not in SILENT_EXITS
