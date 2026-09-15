from web import settings_registry as registry


def test_validate_message_template():
    assert registry.validate_message_template("Hello {firstname}!") is None
    assert registry.validate_message_template("{lastname} {username}") is None
    assert registry.validate_message_template("{bad}") is not None
    assert registry.validate_message_template("") is not None


def test_validate_captcha():
    options = ["Yes", "No"]
    assert registry.validate_captcha("Human?", options, "Yes", "3") is None
    assert registry.validate_captcha("", options, "Yes", "3") is not None
    assert registry.validate_captcha("Human?", ["Only"], "Only", "3") is not None
    assert registry.validate_captcha("Human?", options, "Maybe", "3") is not None
    assert registry.validate_captcha("Human?", options, "Yes", "abc") is not None
    assert registry.validate_captcha("Human?", options, "Yes", "0") is not None


def test_validate_named_text():
    assert registry.validate_named_text("key", "body") is None
    assert registry.validate_named_text("", "body") is not None
    assert registry.validate_named_text("key", "") is not None


def test_filters_add_delete(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gid = "-100111"
    registry.add_filter(gid, "hello", "hi there")
    assert registry.read_filters(gid) == {"hello": {"type": "text", "data": "hi there"}}
    registry.delete_filter(gid, "hello")
    assert registry.read_filters(gid) == {}


def test_filters_add_media(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gid = "-100112"
    registry.add_filter(gid, "pic", "", "photo", "FILEX")
    assert registry.read_filters(gid) == {"pic": {"type": "photo", "data": "FILEX"}}
    registry.add_filter(gid, "once", "")
    assert registry.read_filters(gid)["once"] == {"type": "text", "data": ""}


def test_notes_add_delete_renumbers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gid = "-100222"
    registry.add_note(gid, "rules", "be nice")
    registry.add_note(gid, "links", "link here")
    notes = registry.read_notes(gid)
    assert len(notes) == 2
    assert notes["1"]["name"] == "rules"
    assert notes["2"]["name"] == "links"
    registry.delete_note(gid, "1")
    notes = registry.read_notes(gid)
    assert list(notes) == ["1"]
    assert notes["1"]["name"] == "links"


def test_notes_add_media(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gid = "-100223"
    registry.add_note(gid, "pic", "", "photo", "FILEY")
    notes = registry.read_notes(gid)
    assert notes["1"]["reply"] == {"type": "photo", "data": "FILEY"}
    registry.add_note(gid, "txt", "plain")
    assert registry.read_notes(gid)["2"]["reply"] == {"type": "text", "data": "plain"}


def test_stickers_add_delete(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gid = "-100333"
    assert registry.add_sticker(gid, "RainbowSet")
    assert not registry.add_sticker(gid, "RainbowSet")
    assert registry.read_stickers(gid) == ["RainbowSet"]
    registry.delete_sticker(gid, "RainbowSet")
    assert registry.read_stickers(gid) == []


def test_module_states_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gid = "-100444"
    states = registry.read_module_states(gid)
    assert states["ban"] is True
    registry.set_module_enabled(gid, "ban", False)
    assert registry.read_module_states(gid)["ban"] is False
    enabled, total = registry.module_stats(gid)
    assert enabled == total - 1


def test_greetings_messages_media(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gid = "-100555"
    registry.save_greeting_messages(gid, greeting="Hi {firstname}")
    data = registry.read_greetings(gid)
    assert data["greeting"] == "Hi {firstname}"
    registry.clear_greeting_media(gid, "greeting")
    assert registry.read_greetings(gid)["greeting_media_type"] is None


def test_greetings_set_media(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gid = "-100556"
    registry.set_greeting_media(gid, "greeting", "photo", "FILEG")
    assert registry.read_greetings(gid)["greeting_media_type"] == "photo"
    assert registry.read_greetings(gid)["greeting_media_id"] == "FILEG"
    registry.set_greeting_media(gid, "greeting", "video", "FILEV")
    assert registry.read_greetings(gid)["greeting_media_id"] == "FILEV"
    registry.clear_greeting_media(gid, "greeting")
    assert registry.read_greetings(gid)["greeting_media_type"] is None


def test_captcha_save(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gid = "-100666"
    registry.save_captcha(gid, "Human?", ["Yes", "No"], "Yes", 2)
    registry.set_captcha_enabled(gid, True)
    data = registry.read_greetings(gid)
    assert data["captcha_q"] == "Human?"
    assert data["captcha_opts"] == ["Yes", "No"]
    assert data["captcha_max_tries"] == 2
    assert data["captcha_enabled"] is True