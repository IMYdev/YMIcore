from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "src" / "web" / "templates"


def _forms_with_files(html: str) -> list:
    forms = []
    for block in html.split("<form"):
        if 'type="file"' in block:
            forms.append(block)
    return forms


def test_media_forms_use_multipart_enctype():
    for template in TEMPLATES.glob("*.html"):
        html = template.read_text(encoding="utf-8")
        for block in _forms_with_files(html):
            assert 'enctype="multipart/form-data"' in block, (
                f"{template.name} has a file input on a form without enctype"
            )