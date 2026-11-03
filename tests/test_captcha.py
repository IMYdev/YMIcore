import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from modules.captcha import (
    get_captcha_questions, validate_question, add_question, remove_question,
    session_key, create_session, get_session, save_session, delete_session,
    list_sessions, is_expired, register_wrong_answer, register_correct_answer,
    get_kicks, increment_kicks, reset_kicks, decide_punishment, MAX_KICKS,
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
