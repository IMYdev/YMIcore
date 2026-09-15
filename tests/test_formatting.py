from core.formatting import markdown_to_html as f


def test_basic_inline():
    assert "<b>hi</b>" in f("**hi**")
    assert "<i>hi</i>" in f("*hi*")
    assert "<i>hi</i>" in f("_hi_")
    assert "<code>x</code>" in f("`x`")
    assert "<s>x</s>" in f("~~x~~")
    assert "<tg-spoiler>x</tg-spoiler>" in f("||x||")


def test_link():
    assert '<a href="https://x.com">click</a>' in f("[click](https://x.com)")


def test_fenced_code():
    html = f("```python\nprint(1)\n```")
    assert "<pre>" in html
    assert "print(1)" in html


def test_heading():
    html = f("# Hello world")
    assert "<b>Hello world</b>" in html


def test_plain_escaping():
    html = f("5 < 6 & 'ok'")
    assert "5 &lt; 6" in html
    assert "&amp;" in html


def test_snake_case_not_italic():
    html = f("foo_bar_baz")
    assert "<i>" not in html


def test_empty_text():
    assert f("") == ""
    assert f(None) == ""


def test_plain_text_unchanged():
    assert f("hello") == "hello"
