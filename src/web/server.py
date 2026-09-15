import asyncio
import datetime
import functools
from pathlib import Path

from aiohttp import web
from jinja2 import Environment, FileSystemLoader

from info import (
    BOT_OWNER, Downloader, ERROR_LOG_CHAT_ID, Logs,
    TOKEN, WEB_BIND, WEB_PORT, WEB_URL,
)
from web.auth import (
    COOKIE_NAME, SESSION_TTL, USE_WIDGET,
    activate_token, can_manage_group, delete_token, establish_session,
    get_bot_username, is_owner, issue_admin_token, list_tokens, lookup_token,
    make_session, read_session, revoke_token, token_digest, valid_login_link,
    verify_csrf, verify_tg_widget,
)
from web.groups import group_title, list_groups, record_group
from web import settings_registry as registry
from web.media import is_file_field, relay_to_telegram
from core.activity import log_event, read_events, stats as activity_stats

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"

env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=True,
)
env.filters["ts"] = lambda ts: datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


# --------------------------------------------------------------------------
# Request helpers
# --------------------------------------------------------------------------

def render(request, template_name, **ctx) -> web.Response:
    user = request.get("user")
    base = {
        "csrf": user["c"] if user else "",
        "user": user,
        "is_owner": bool(user and is_owner(user["uid"])),
        "user_id": user["uid"] if user else "",
        "base_url": WEB_URL or f"http://{WEB_BIND}:{WEB_PORT}",
    }
    base.update(ctx)
    body = env.get_template(template_name).render(**base)
    return web.Response(text=body, content_type="text/html")


def set_cookie(resp: web.Response, cookie: str) -> None:
    resp.set_cookie(
        COOKIE_NAME, cookie,
        httponly=True,
        samesite="Lax",
        max_age=SESSION_TTL,
        secure=bool(WEB_URL and WEB_URL.startswith("https")),
    )


def authed(fn):
    @functools.wraps(fn)
    async def wrapper(request):
        user = read_session(request.cookies.get(COOKIE_NAME, ""))
        if not user or "uid" not in user:
            raise web.HTTPFound("/")
        request["user"] = user
        return await fn(request)
    return wrapper


def csrf(fn):
    @functools.wraps(fn)
    async def wrapper(request):
        form = await request.post()
        if not verify_csrf(request["user"], form.get("csrf", "")):
            raise web.HTTPBadRequest(text="Invalid CSRF token.")
        request["form"] = form
        log_event(
            "panel_action",
            user_id=request["user"]["uid"],
            detail=request.path,
        )
        return await fn(request)
    return wrapper


def owner_only(fn):
    @functools.wraps(fn)
    async def wrapper(request):
        if not is_owner(request["user"]["uid"]):
            raise web.HTTPForbidden(text="Owner only.")
        return await fn(request)
    return wrapper


async def ensure_group_access(request) -> str:
    gid = request.match_info["gid"]
    if not await can_manage_group(request["user"]["uid"], gid):
        raise web.HTTPForbidden(text="You do not have access to this group.")
    return gid


async def accessible_groups(user_payload) -> list:
    user_id = user_payload["uid"]
    groups = list_groups()
    checks = await asyncio.gather(*(can_manage_group(user_id, g["gid"]) for g in groups))
    return [g for g, ok in zip(groups, checks) if ok]


def saved_url(path: str) -> str:
    sep = "&" if "?" in path else "?"
    return f"{path}{sep}saved=1"


# --------------------------------------------------------------------------
# Auth routes
# --------------------------------------------------------------------------

async def index(request):
    if request.get("user"):
        raise web.HTTPFound("/panel")
    token = valid_login_link(request.query.get("t", ""))
    if token:
        record = lookup_token(token)
        if record:
            cookie, _ = make_session(record["uid"], token_digest(token))
            resp = web.HTTPFound("/panel")
            set_cookie(resp, cookie)
            return resp
        return await render_login(request, error="Invalid or revoked panel token.")
    return await render_login(request)


async def render_login(request, error=None):
    ctx = {"error": error, "use_widget": False}
    if USE_WIDGET:
        try:
            ctx.update(
                use_widget=True,
                tg_bot_username=await get_bot_username(),
                widget_auth_url=f"{WEB_URL}/auth/telegram",
            )
        except Exception:
            ctx["use_widget"] = False
    return render(request, "login.html", **ctx)


async def auth_token(request):
    form = await request.post()
    token = valid_login_link(form.get("token", ""))
    record = lookup_token(token)
    if record is None:
        return await render_login(request, error="Invalid or revoked token. Send /panel again.")
    cookie, _ = make_session(record["uid"], token_digest(token))
    resp = web.HTTPFound("/panel")
    set_cookie(resp, cookie)
    return resp


async def auth_telegram(request):
    params = {k: v for k, v in request.query.items()}
    uid = verify_tg_widget(params)
    if uid is None:
        return await render_login(request, error="Telegram sign-in failed.")
    cookie, _ = establish_session(uid)
    resp = web.HTTPFound("/panel")
    set_cookie(resp, cookie)
    return resp


@authed
@csrf
async def logout(request):
    resp = web.HTTPFound("/")
    resp.del_cookie(COOKIE_NAME)
    return resp


# --------------------------------------------------------------------------
# Admin tokens (owner)
# --------------------------------------------------------------------------

def tokens_context(request, errors=None, created_token=None, form=None):
    return render(
        request, "tokens.html",
        tokens=list_tokens(), errors=errors or {}, created_token=created_token,
        saved="saved" in request.query, active="tokens",
        form_uid=(form or {}).get("uid", ""), form_label=(form or {}).get("label", ""),
    )


@authed
@owner_only
async def admin_tokens(request):
    return tokens_context(request)


@authed
@owner_only
@csrf
async def admin_tokens_create(request):
    form = request["form"]
    uid = form.get("uid", "").strip()
    label = form.get("label", "").strip()
    errors = {}
    if not uid.isdigit():
        errors["uid"] = "Telegram user ID must be a number."
    if len(label) > 40:
        errors["label"] = "Label must be 40 characters or fewer."
    if errors:
        return tokens_context(request, errors=errors, form=form)
    token, _ = issue_admin_token(int(uid), label or f"user {uid}")
    return tokens_context(request, created_token=token)


@authed
@owner_only
@csrf
async def admin_tokens_status(request):
    form = request["form"]
    digest = form.get("digest", "")
    if form.get("action") == "revoke":
        revoke_token(digest)
    elif form.get("action") == "activate":
        activate_token(digest)
    raise web.HTTPFound(saved_url("/tokens"))


@authed
@owner_only
@csrf
async def admin_tokens_delete(request):
    delete_token(request["form"].get("digest", ""))
    raise web.HTTPFound(saved_url("/tokens"))


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------

@authed
async def dashboard(request):
    groups = await accessible_groups(request["user"])
    for g in groups:
        g["enabled"], g["total"] = registry.module_stats(g["gid"])
    return render(request, "dashboard.html", groups=groups, active="dashboard")


# --------------------------------------------------------------------------
# Global settings (owner, read-only)
# --------------------------------------------------------------------------

def mask(value) -> str:
    if not value:
        return "(unset)"
    value = str(value)
    if len(value) <= 8:
        return "•" * len(value)
    return f"{value[:4]}…{value[-3:]}"


@authed
@owner_only
async def global_settings(request):
    values = [
        ("BOT_TOKEN", mask(TOKEN) if TOKEN else "(missing)", "Bot auth token."),
        ("LOG_ID", (ERROR_LOG_CHAT_ID) if ERROR_LOG_CHAT_ID else "(missing)", "Error report channel."),
        ("OWNER", (BOT_OWNER) if BOT_OWNER else "(missing)", "Owner Telegram ID."),
        ("Logs", Logs, "Error reporting enabled."),
        ("Downloader", Downloader, "Media downloader enabled."),
        ("WEB_BIND", WEB_BIND, "Panel bind address."),
        ("WEB_PORT", WEB_PORT, "Panel port."),
        ("WEB_URL", WEB_URL or "(unset - localhost)", "Public panel URL."),
    ]
    return render(request, "global.html", values=values, active="global")


# --------------------------------------------------------------------------
# Statistics & activity (owner)
# --------------------------------------------------------------------------

_EVENT_LABELS = [
    ("Commands", "command"),
    ("Filter triggers", "filter_trigger"),
    ("Note fetches", "note_fetch"),
    ("Greetings", "greeting"),
    ("Farewells", "farewell"),
    ("Captcha passes", "captcha_pass"),
    ("Captcha failures", "captcha_fail"),
    ("Panel actions", "panel_action"),
]


@authed
@owner_only
async def statistics(request):
    counts = activity_stats()
    groups = list_groups()
    group_stats = []
    for g in groups:
        g_counts = activity_stats(chat_id=g["gid"])
        total = sum(g_counts.values())
        if total:
            group_stats.append({"gid": g["gid"], "title": g["title"], "counts": g_counts, "total": total})
    group_stats.sort(key=lambda g: g["total"], reverse=True)
    return render(
        request, "statistics.html",
        counts=counts, group_stats=group_stats,
        event_labels=_EVENT_LABELS, active="statistics",
    )


@authed
@owner_only
async def activity_page(request):
    events = read_events(limit=200)
    return render(request, "activity.html", events=events, active="activity")


# --------------------------------------------------------------------------
# Group pages
# --------------------------------------------------------------------------

@authed
async def group_modules(request):
    gid = await ensure_group_access(request)
    states = registry.read_module_states(gid)
    modules = []
    for name, cmds in registry.MODULE_MAP.items():
        cmd_states = {c: states[c] for c in cmds}
        modules.append({
            "name": name,
            "cmds": cmds,
            "enabled": any(cmd_states.values()),
            "states": cmd_states,
        })
    return render(
        request, "group_modules.html",
        gid=gid, title=group_title(gid), group_tab="modules",
        modules=modules, saved="saved" in request.query,
    )


@authed
@csrf
async def group_modules_save(request):
    gid = await ensure_group_access(request)
    form = request["form"]
    module = form.get("module")
    if module not in registry.MODULE_MAP:
        raise web.HTTPBadRequest(text="Unknown module.")
    selected = set(form.getall("cmd"))
    for command in registry.MODULE_MAP[module]:
        registry.set_module_enabled(gid, command, command in selected)
    raise web.HTTPFound(saved_url(f"/groups/{gid}/modules"))


@authed
async def group_greetings(request):
    gid = await ensure_group_access(request)
    data = registry.read_greetings(gid)
    return _greetings_page(request, gid, data, errors={}, saved="saved" in request.query)


def _greetings_page(request, gid, data, errors, saved=False, captcha=None, greeting=None, goodbye=None):
    greeting = greeting if greeting is not None else data.get("greeting", "Hello {firstname}, welcome!")
    goodbye = goodbye if goodbye is not None else data.get("goodbye", "Goodbye {firstname}, we will miss you!")
    media = {
        "greeting": (data.get("greeting_media_type"), data.get("greeting_media_id")),
        "goodbye": (data.get("goodbye_media_type"), data.get("goodbye_media_id")),
    }
    captcha = captcha or {
        "enabled": data.get("captcha_enabled", False),
        "question": data.get("captcha_q", ""),
        "options": data.get("captcha_opts", []),
        "answer": data.get("captcha_ans", ""),
        "tries": data.get("captcha_max_tries", 1),
    }
    return render(
        request, "group_greetings.html",
        gid=gid, title=group_title(gid), group_tab="greetings",
        greeting=greeting, goodbye=goodbye, media=media, captcha=captcha,
        errors=errors, saved=saved,
    )


@authed
@csrf
async def group_greetings_save(request):
    gid = await ensure_group_access(request)
    form = request["form"]
    action = form.get("action", "")

    if action == "captcha":
        question = form.get("question", "").strip()
        options = [o.strip() for o in form.get("options", "").splitlines() if o.strip()]
        answer = form.get("answer", "").strip()
        tries = form.get("tries", "1").strip()
        error = registry.validate_captcha(question, options, answer, tries)
        if error:
            captcha = {
                "enabled": "enabled" in form,
                "question": question,
                "options": options,
                "answer": answer,
                "tries": tries,
            }
            data = registry.read_greetings(gid)
            return _greetings_page(request, gid, data, errors={"captcha": error}, captcha=captcha)
        registry.save_captcha(gid, question, options, answer, int(tries))
        registry.set_captcha_enabled(gid, "enabled" in form)
        raise web.HTTPFound(saved_url(f"/groups/{gid}/greetings"))

    if action == "clear_greeting_media":
        registry.clear_greeting_media(gid, "greeting")
        raise web.HTTPFound(saved_url(f"/groups/{gid}/greetings"))

    if action == "clear_goodbye_media":
        registry.clear_greeting_media(gid, "goodbye")
        raise web.HTTPFound(saved_url(f"/groups/{gid}/greetings"))

    greeting = form.get("greeting", "").strip()
    goodbye = form.get("goodbye", "").strip()
    errors = {}
    if greeting:
        err = registry.validate_message_template(greeting)
        if err:
            errors["greeting"] = err
    if goodbye:
        err = registry.validate_message_template(goodbye)
        if err:
            errors["goodbye"] = err
    if errors:
        data = registry.read_greetings(gid)
        return _greetings_page(
            request, gid, data,
            errors=errors,
            greeting=greeting or data.get("greeting", ""),
            goodbye=goodbye or data.get("goodbye", ""),
        )
    registry.save_greeting_messages(gid, greeting or None, goodbye or None)
    raise web.HTTPFound(saved_url(f"/groups/{gid}/greetings"))


@authed
async def group_filters(request):
    gid = await ensure_group_access(request)
    filters = registry.read_filters(gid)
    return render(
        request, "group_filters.html",
        gid=gid, title=group_title(gid), group_tab="filters",
        filters=filters.items(), errors={}, saved="saved" in request.query,
    )


@authed
@csrf
async def group_filters_add(request):
    gid = await ensure_group_access(request)
    form = request["form"]
    keyword = form.get("keyword", "").strip().lower()
    body = form.get("body", "")
    upload = form.get("media")

    relayed = None
    if not keyword:
        error = "Keyword is required."
    elif is_file_field(upload):
        relayed = await relay_to_telegram(upload, BOT_OWNER)
        error = None if relayed else "This file cannot be used as a filter."
    else:
        error = registry.validate_named_text(keyword, body)

    if error:
        return render(
            request, "group_filters.html",
            gid=gid, title=group_title(gid), group_tab="filters",
            filters=registry.read_filters(gid).items(),
            errors={"form": error}, saved=False,
        )

    if relayed:
        registry.add_filter(gid, keyword, "", relayed["type"], relayed["file_id"])
    else:
        registry.add_filter(gid, keyword, body)
    raise web.HTTPFound(saved_url(f"/groups/{gid}/filters"))


@authed
@csrf
async def group_filters_delete(request):
    gid = await ensure_group_access(request)
    keyword = request["form"].get("keyword", "")
    registry.delete_filter(gid, keyword)
    raise web.HTTPFound(saved_url(f"/groups/{gid}/filters"))


@authed
async def group_notes(request):
    gid = await ensure_group_access(request)
    notes = registry.read_notes(gid)
    return render(
        request, "group_notes.html",
        gid=gid, title=group_title(gid), group_tab="notes",
        notes=notes.items(), errors={}, saved="saved" in request.query,
    )


@authed
@csrf
async def group_notes_add(request):
    gid = await ensure_group_access(request)
    form = request["form"]
    name = form.get("name", "").strip()
    body = form.get("body", "")
    upload = form.get("media")

    relayed = None
    if not name:
        error = "Note name is required."
    elif is_file_field(upload):
        relayed = await relay_to_telegram(upload, BOT_OWNER)
        error = None if relayed else "This file cannot be used as a note."
    else:
        error = registry.validate_named_text(name, body)

    if error:
        return render(
            request, "group_notes.html",
            gid=gid, title=group_title(gid), group_tab="notes",
            notes=registry.read_notes(gid).items(),
            errors={"form": error}, saved=False,
        )

    if relayed:
        registry.add_note(gid, name, "", relayed["type"], relayed["file_id"])
    else:
        registry.add_note(gid, name, body)
    raise web.HTTPFound(saved_url(f"/groups/{gid}/notes"))


@authed
@csrf
async def group_notes_delete(request):
    gid = await ensure_group_access(request)
    note_id = request["form"].get("note_id", "")
    registry.delete_note(gid, note_id)
    raise web.HTTPFound(saved_url(f"/groups/{gid}/notes"))


@authed
async def group_stickers(request):
    gid = await ensure_group_access(request)
    stickers = registry.read_stickers(gid)
    return render(
        request, "group_stickers.html",
        gid=gid, title=group_title(gid), group_tab="stickers",
        stickers=stickers, errors={}, saved="saved" in request.query,
    )


@authed
@csrf
async def group_stickers_add(request):
    gid = await ensure_group_access(request)
    set_name = request["form"].get("set_name", "").strip()
    if not set_name:
        return render(
            request, "group_stickers.html",
            gid=gid, title=group_title(gid), group_tab="stickers",
            stickers=registry.read_stickers(gid),
            errors={"form": "Sticker set name is required."}, saved=False,
        )
    registry.add_sticker(gid, set_name)
    raise web.HTTPFound(saved_url(f"/groups/{gid}/stickers"))


@authed
@csrf
async def group_stickers_delete(request):
    gid = await ensure_group_access(request)
    set_name = request["form"].get("set_name", "")
    registry.delete_sticker(gid, set_name)
    raise web.HTTPFound(saved_url(f"/groups/{gid}/stickers"))


# --------------------------------------------------------------------------
# App factory
# --------------------------------------------------------------------------

def create_app() -> web.Application:
    app = web.Application()
    app.router.add_static("/static", STATIC_DIR)
    app.add_routes([
        web.get("/", index),
        web.post("/auth/token", auth_token),
        web.get("/auth/telegram", auth_telegram),
        web.post("/auth/logout", logout),
        web.get("/tokens", admin_tokens),
        web.post("/tokens/create", admin_tokens_create),
        web.post("/tokens/status", admin_tokens_status),
        web.post("/tokens/delete", admin_tokens_delete),
        web.get("/panel", dashboard),
        web.get("/settings/global", global_settings),
        web.get("/statistics", statistics),
        web.get("/activity", activity_page),
        web.get("/groups/{gid}", lambda r: web.HTTPFound(f"/groups/{r.match_info['gid']}/modules")),
        web.get("/groups/{gid}/modules", group_modules),
        web.post("/groups/{gid}/modules", group_modules_save),
        web.get("/groups/{gid}/greetings", group_greetings),
        web.post("/groups/{gid}/greetings", group_greetings_save),
        web.get("/groups/{gid}/filters", group_filters),
        web.post("/groups/{gid}/filters/add", group_filters_add),
        web.post("/groups/{gid}/filters/delete", group_filters_delete),
        web.get("/groups/{gid}/notes", group_notes),
        web.post("/groups/{gid}/notes/add", group_notes_add),
        web.post("/groups/{gid}/notes/delete", group_notes_delete),
        web.get("/groups/{gid}/stickers", group_stickers),
        web.post("/groups/{gid}/stickers/add", group_stickers_add),
        web.post("/groups/{gid}/stickers/delete", group_stickers_delete),
    ])
    return app


async def start_web_server() -> None:
    from web.auth import ensure_owner_token
    owner_token, created = ensure_owner_token()
    app = create_app()
    try:
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, WEB_BIND, WEB_PORT)
        await site.start()
    except Exception as exc:
        print(f"[!] Web panel failed to start on {WEB_BIND}:{WEB_PORT}: {exc}")
        return
    print(f"[+] Web panel running at {WEB_URL or f'http://{WEB_BIND}:{WEB_PORT}'}")
    if created and owner_token:
        print(f"[+] Owner panel token: {owner_token} (re-send /panel anytime to rotate)")
    await asyncio.Event().wait()