"""Validation shared by the bot commands and the web panel."""

import re

TEMPLATE_FIELDS = {"firstname", "lastname", "username"}


def validate_template(template) -> bool:
    """True when a greeting/farewell only uses supported placeholders."""
    found = set(re.findall(r"{(.*?)}", template))
    return found.issubset(TEMPLATE_FIELDS)


def validate_question(q, opts, ans):
    """Return an error string for a captcha question, or None when valid."""
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
