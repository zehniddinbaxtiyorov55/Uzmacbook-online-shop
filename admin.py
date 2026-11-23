"""Admin panel: https://ADMIN_HOST/admin (login va parol .env da: ADMIN_USER, ADMIN_PASSWORD).

Bo'limlar: statistika, buyurtmalar, mijozlar, mijozlarga xabar yuborish,
tovarlarni yashirish/ko'rsatish, bot matnlari va sozlamalar."""
import asyncio, csv, datetime, hashlib, hmac, io, logging, os, time, uuid
from aiohttp import web
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramBadRequest
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import db
import settings
import webapp

log = logging.getLogger("BOT")
HERE = os.path.dirname(os.path.abspath(__file__))
USER = os.environ.get("ADMIN_USER", "admin").strip() or "admin"
PASSWORD = os.environ.get("ADMIN_PASSWORD", "").strip()
HOST = webapp.ADMIN_HOST
UPLOADS = os.path.join(os.path.dirname(db.PATH), "uploads")
SECRET = hashlib.sha256(("adm:%s:%s:%s" % (webapp.TOKEN, USER, PASSWORD)).encode()).digest()
SESSION_DAYS = 30
COOKIE = "adm"
PAGE = 50
TZ = datetime.timezone(datetime.timedelta(hours=5))

ctx = {}
fails = {}  # ip -> [urinishlar, bloklangan_vaqtgacha]
job = {"task": None, "id": None, "stop": False}


# ---------- Kirish ----------
def make_token():
    exp = int(time.time()) + SESSION_DAYS * 86400
    sig = hmac.new(SECRET, ("%s:%s" % (USER, exp)).encode(), hashlib.sha256).hexdigest()
    return "%s.%s" % (exp, sig)


def valid_token(tok):
    try:
        exp, sig = (tok or "").split(".", 1)
        if int(exp) < time.time():
            return False
    except ValueError:
        return False
    good = hmac.new(SECRET, ("%s:%s" % (USER, exp)).encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(good, sig)


def client_ip(req):
    return (req.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or req.remote or "?")


def is_admin_path(path):
    return path == "/admin" or path.startswith("/admin/")


@web.middleware
async def guard(req, handler):
    if not is_admin_path(req.path):
        return await handler(req)
    if HOST and req.host.split(":")[0].lower() != HOST.lower():
        raise web.HTTPNotFound()  # admin panel faqat o'z domenida ochiladi
    if not PASSWORD:
        return web.Response(status=503, content_type="text/html", text=(
            "<h3>Admin panel o'chiq</h3><p>Serverdagi <code>.env</code> fayliga "
            "<code>ADMIN_PASSWORD=...</code> yozing va botni qayta ishga tushiring.</p>"))
    if req.path.startswith("/admin/api/") and req.path != "/admin/api/login":
        if not valid_token(req.cookies.get(COOKIE)):
            return web.json_response({"ok": False, "error": "login"}, status=401)
    resp = await handler(req)
    resp.headers.setdefault("Cache-Control", "no-store")
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    return resp


async def page(_):
    return web.FileResponse(os.path.join(HERE, "admin.html"))


async def login(req):
    ip = client_ip(req)
    cnt, until = fails.get(ip, [0, 0])
    if until > time.time():
        return web.json_response({"ok": False, "error": "Ko'p urinish. %s daqiqadan keyin qayta urinib ko'ring."
                                  % (int(until - time.time()) // 60 + 1)}, status=429)
    try:
        body = await req.json()
    except Exception:
        body = {}
    u, p = str(body.get("user") or ""), str(body.get("password") or "")
    ok = hmac.compare_digest(u.strip().lower(), USER.lower()) & hmac.compare_digest(p, PASSWORD)
    if not ok:
        cnt += 1
        fails[ip] = [cnt, time.time() + 900 if cnt >= 8 else 0]
        log.warning("ADMIN: noto'g'ri login, ip=%s, urinish %s", ip, cnt)
        await asyncio.sleep(1)
        return web.json_response({"ok": False, "error": "Login yoki parol noto'g'ri"}, status=401)
    fails.pop(ip, None)
    log.info("ADMIN: kirish, ip=%s", ip)
    resp = web.json_response({"ok": True, "user": USER})
    secure = req.secure or req.headers.get("X-Forwarded-Proto") == "https"
    resp.set_cookie(COOKIE, make_token(), max_age=SESSION_DAYS * 86400, httponly=True,
                    secure=secure, samesite="Strict", path="/admin")
    return resp


async def logout(_):
    resp = web.json_response({"ok": True})
    resp.del_cookie(COOKIE, path="/admin")
    return resp


async def me(_):
    return web.json_response({"ok": True, "user": USER})


# ---------- Statistika ----------
async def stats(_):
    out = db.stats()
    items = webapp.cache["items"]
    hidden = db.hidden_ids()
    rate, rdate = webapp.usd_rate()
    if "bot_name" not in ctx:
        try:
            ctx["bot_name"] = (await ctx["bot"].get_me()).username
        except Exception:
            pass
    out["products"] = {"total": len(items), "hidden": len([i for i in items if i["id"] in hidden]),
                       "loaded": bool(webapp.cache["at"])}
    out["rate"] = {"rate": rate, "date": rdate}
    out["bot"] = ctx.get("bot_name") or ""
    out["shop_url"] = webapp.URL
    _, recent = db.orders(limit=6)
    out["recent"] = recent
    return web.json_response(out)


# ---------- Buyurtmalar ----------
def arg_int(req, key, default=0):
    try:
        return max(0, int(req.query.get(key, default)))
    except ValueError:
        return default


async def orders(req):
    total, rows = db.orders(req.query.get("status", ""), req.query.get("q", ""),
                            PAGE, arg_int(req, "offset"))
    return web.json_response({"total": total, "items": rows, "page": PAGE})


async def order_update(req):
    try:
        oid = int(req.match_info["id"])
        body = await req.json()
        row = db.update_order(oid, body.get("status"), body.get("note"))
    except (ValueError, TypeError):
        return web.json_response({"ok": False, "error": "Noto'g'ri ma'lumot"}, status=400)
    if not row:
        return web.json_response({"ok": False, "error": "Buyurtma topilmadi"}, status=404)
    return web.json_response({"ok": True, "item": row})


def fmt_time(t):
    return datetime.datetime.fromtimestamp(t or 0, TZ).strftime("%d.%m.%Y %H:%M") if t else ""


def csv_response(name, header, rows):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(header)
    w.writerows(rows)
    return web.Response(body=("﻿" + buf.getvalue()).encode("utf-8"), headers={
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": 'attachment; filename="%s"' % name})


STATUS_UZ = {"new": "Yangi", "contacted": "Bog'lanildi", "sold": "Sotildi", "cancelled": "Bekor"}


async def orders_csv(req):
    _, rows = db.orders(req.query.get("status", ""), req.query.get("q", ""), 100000, 0)
    return csv_response("buyurtmalar.csv",
                        ["№", "Sana", "Mijoz", "Username", "Telefon", "Tovarlar", "Jami", "Muddat (oy)",
                         "Holati", "Izoh"],
                        [[r["id"], fmt_time(r["created_at"]), r["name"], r["username"], r["phone"],
                          " | ".join("%s — %s %s" % (i["name"], i["price"], i["currency"]) for i in r["items"]),
                          " + ".join("%s %s" % (v, c) for c, v in r["totals"].items()),
                          r["months"] or "", STATUS_UZ.get(r["status"], r["status"]), r["note"]]
                         for r in rows])


# ---------- Mijozlar ----------
async def users(req):
    total, rows = db.users(req.query.get("q", ""), PAGE, arg_int(req, "offset"))
    return web.json_response({"total": total, "items": rows, "page": PAGE})


async def users_csv(req):
    _, rows = db.users(req.query.get("q", ""), 1000000, 0)
    return csv_response("mijozlar.csv",
                        ["Telegram ID", "Ism", "Familiya", "Username", "Telefon", "Birinchi kirgan",
                         "Oxirgi faollik", "Buyurtmalar", "Botni bloklagan"],
                        [[r["id"], r["first_name"], r["last_name"], r["username"], r["phone"],
                          fmt_time(r["created_at"]), fmt_time(r["last_seen"]), r["orders"],
                          "ha" if r["blocked"] else ""] for r in rows])


# ---------- Sozlamalar ----------
async def settings_get(_):
    return web.json_response({"fields": settings.all_for_admin()})


async def settings_save(req):
    try:
        body = await req.json()
        values = body.get("values") or {}
        old_extra = settings.num("usd_rate_extra")
        settings.save(values)
    except ValueError as e:
        return web.json_response({"ok": False, "error": str(e)}, status=400)
    if settings.num("usd_rate_extra") != old_extra:
        webapp.rate_cache["at"] = 0  # kurs yangi qo'shimcha bilan qayta hisoblansin
        webapp.usd_rate()
    log.info("ADMIN: sozlamalar saqlandi: %s", ", ".join(values.keys()))
    return web.json_response({"ok": True, "fields": settings.all_for_admin()})


# ---------- Tovarlar ----------
async def products(req):
    if req.query.get("refresh"):
        webapp.cache["at"] = 0
    items = await webapp.load()
    hidden = db.hidden_ids()
    out = [{"id": i["id"], "name": i["name"], "category": i["category"], "price": i["price"],
            "promo": i["promo"], "currency": i["currency"], "qty": i["qty"],
            "photo": (i["photos"] or i["stock"] or [""])[0], "hidden": i["id"] in hidden,
            "in_stock": True} for i in items]
    have = {i["id"] for i in items}
    for r in db.q("SELECT product_id, name FROM hidden"):
        if r["product_id"] not in have:
            out.append({"id": r["product_id"], "name": r["name"], "category": "Billz'da hozir yo'q",
                        "price": 0, "promo": 0, "currency": "", "qty": 0, "photo": "",
                        "hidden": True, "in_stock": False})
    out.sort(key=lambda x: (x["category"], x["name"]))
    return web.json_response({"items": out, "loaded_at": webapp.cache["at"]})


async def product_hide(req):
    try:
        body = await req.json()
        pid = str(body["id"])[:200]
    except Exception:
        return web.json_response({"ok": False}, status=400)
    db.set_hidden(pid, str(body.get("name") or "")[:300], bool(body.get("hidden")))
    log.info("ADMIN: tovar %s: %s", "yashirildi" if body.get("hidden") else "ko'rsatildi", body.get("name"))
    return web.json_response({"ok": True})


# ---------- Xabar yuborish ----------
def shop_kb():
    if not webapp.URL:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text="🛍 Online do'kon", web_app=WebAppInfo(url=webapp.URL))]])


async def send_one(chat_id, text, photo, kb):
    bot = ctx["bot"]
    if photo:
        return await bot.send_photo(chat_id, photo, caption=text or None, reply_markup=kb)
    return await bot.send_message(chat_id, text, reply_markup=kb)


async def run_broadcast(bid, ids, text, photo_path, kb):
    photo = FSInputFile(photo_path) if photo_path else None
    sent = failed = blocked = 0
    status = "done"
    try:
        for n, cid in enumerate(ids, 1):
            if job["stop"]:
                status = "stopped"
                break
            for _ in range(3):
                try:
                    msg = await send_one(cid, text, photo, kb)
                    if isinstance(photo, FSInputFile) and msg.photo:
                        photo = msg.photo[-1].file_id  # keyingilarga tez yuboriladi
                    sent += 1
                    break
                except TelegramRetryAfter as e:
                    await asyncio.sleep(e.retry_after + 1)
                except TelegramForbiddenError:
                    db.set_blocked(cid)
                    blocked += 1
                    break
                except TelegramBadRequest:
                    failed += 1
                    break
                except Exception:
                    log.exception("ADMIN: xabar %s ga yuborilmadi", cid)
                    failed += 1
                    break
            else:
                failed += 1
            if n % 20 == 0:
                db.update_broadcast(bid, sent=sent, failed=failed, blocked=blocked)
            await asyncio.sleep(0.05)  # Telegram: sekundiga 30 tadan oshmasin
    except Exception:
        log.exception("ADMIN: xabar yuborish to'xtadi")
        status = "error"
    finally:
        db.update_broadcast(bid, sent=sent, failed=failed, blocked=blocked, status=status,
                            finished_at=int(time.time()))
        job.update(task=None, id=None, stop=False)
        log.info("ADMIN: xabar yuborish #%s tugadi: %s ta yuborildi, %s ta bloklagan, %s ta xato",
                 bid, sent, blocked, failed)


async def broadcast(req):
    try:
        form = await req.post()
    except Exception:
        return web.json_response({"ok": False, "error": "Rasm juda katta (10 MB gacha)"}, status=400)
    text = str(form.get("text") or "").strip()
    test = form.get("test") == "1"
    kb = shop_kb() if form.get("button") == "1" else None
    photo = form.get("photo")
    has_photo = hasattr(photo, "file") and getattr(photo, "filename", "")
    if not text and not has_photo:
        return web.json_response({"ok": False, "error": "Matn yoki rasm kiriting"}, status=400)
    if has_photo and len(text) > 1024:
        return web.json_response({"ok": False, "error": "Rasm bilan matn 1024 belgidan oshmasin "
                                  "(hozir %s)" % len(text)}, status=400)
    if len(text) > 4096:
        return web.json_response({"ok": False, "error": "Matn 4096 belgidan oshmasin"}, status=400)
    path = ""
    if has_photo:
        ext = os.path.splitext(photo.filename)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            return web.json_response({"ok": False, "error": "Rasm JPG, PNG yoki WEBP bo'lsin"}, status=400)
        os.makedirs(UPLOADS, exist_ok=True)
        path = os.path.join(UPLOADS, uuid.uuid4().hex + ext)
        with open(path, "wb") as f:
            f.write(photo.file.read())

    if test:
        if not webapp.ADMIN:
            return web.json_response({"ok": False, "error": ".env da ADMIN_CHAT_ID yo'q"}, status=400)
        try:
            await send_one(int(webapp.ADMIN), text, FSInputFile(path) if path else None, kb)
        except Exception as e:
            return web.json_response({"ok": False, "error": "Yuborilmadi: %s" % e}, status=400)
        return web.json_response({"ok": True, "test": True})

    if job["task"]:
        return web.json_response({"ok": False, "error": "Oldingi xabar hali yuborilyapti"}, status=409)
    ids = db.audience()
    if not ids:
        return web.json_response({"ok": False, "error": "Hali mijozlar yo'q"}, status=400)
    bid = db.add_broadcast(text, os.path.basename(path), bool(kb), len(ids))
    job.update(id=bid, stop=False)
    job["task"] = asyncio.create_task(run_broadcast(bid, ids, text, path, kb))
    log.info("ADMIN: xabar yuborish #%s boshlandi: %s ta mijoz", bid, len(ids))
    return web.json_response({"ok": True, "id": bid, "total": len(ids)})


async def broadcast_stop(_):
    if job["task"]:
        job["stop"] = True
    return web.json_response({"ok": True})


async def broadcasts(_):
    return web.json_response({"items": db.broadcasts(), "running": job["id"],
                              "audience": len(db.audience())})


def setup(app, bot, main_menu=None):
    ctx.update(bot=bot, main_menu=main_menu)
    app.middlewares.append(guard)
    r = app.router
    r.add_get("/admin", page)
    r.add_get("/admin/", page)
    r.add_post("/admin/api/login", login)
    r.add_post("/admin/api/logout", logout)
    r.add_get("/admin/api/me", me)
    r.add_get("/admin/api/stats", stats)
    r.add_get("/admin/api/orders", orders)
    r.add_get("/admin/api/orders.csv", orders_csv)
    r.add_post("/admin/api/orders/{id}", order_update)
    r.add_get("/admin/api/users", users)
    r.add_get("/admin/api/users.csv", users_csv)
    r.add_get("/admin/api/settings", settings_get)
    r.add_post("/admin/api/settings", settings_save)
    r.add_get("/admin/api/products", products)
    r.add_post("/admin/api/products/hide", product_hide)
    r.add_get("/admin/api/broadcasts", broadcasts)
    r.add_post("/admin/api/broadcast", broadcast)
    r.add_post("/admin/api/broadcast/stop", broadcast_stop)
    if not PASSWORD:
        log.warning("ADMIN: ADMIN_PASSWORD yo'q — admin panel o'chiq")
    else:
        log.info("ADMIN: admin panel: %s/admin", ("https://" + HOST) if HOST else "")
