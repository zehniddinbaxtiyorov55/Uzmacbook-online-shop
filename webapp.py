"""Telegram Mini App do'kon: Billz tovarlari (rasm, narx, qoldiq) + savat + buyurtma."""
import asyncio, hashlib, hmac, json, logging, math, os, time
from urllib.parse import parse_qsl
from aiohttp import web
from aiogram.types import MenuButtonWebApp, WebAppInfo
from stock_photos import stock_photos

log = logging.getLogger("BOT")
HERE = os.path.dirname(os.path.abspath(__file__))
URL = os.environ.get("WEBAPP_URL") or os.environ.get("RENDER_EXTERNAL_URL", "")
if URL and not URL.endswith("/"):
    URL += "/"
ADMIN = os.environ.get("ADMIN_CHAT_ID", "")       # buyurtmalar keladigan chat
TOKEN = os.environ["BOT_TOKEN"]
SKIP = ("seriya", "imei", "serial")
# Bo'lib to'lash: boshlang'ich %, oylar oralig'i, qoldiqqa oylik ustama %
PLAN = {
    "down": float(os.environ.get("INSTALLMENT_DOWN_PCT", "50")),
    "min": int(os.environ.get("INSTALLMENT_MIN_MONTHS", "3")),
    "max": int(os.environ.get("INSTALLMENT_MAX_MONTHS", "8")),
    "pct": float(os.environ.get("INSTALLMENT_MONTHLY_PCT", "0")),
}


def plan_calc(price, months):
    down = math.ceil(price * PLAN["down"] / 100)
    rest = (price - down) * (1 + PLAN["pct"] / 100 * months)
    monthly = math.ceil(rest / months)
    return down, monthly, down + monthly * months

cache = {"items": [], "at": 0.0}
lock = asyncio.Lock()
ctx = {}


def photos_of(p):
    out = []
    for k in ("main_image_url_full", "main_image_url", "image_url", "photo_url"):
        if isinstance(p.get(k), str) and p[k]:
            out.append(p[k])
    for ph in p.get("photos") or p.get("images") or []:
        u = ph if isinstance(ph, str) else (
            ph.get("photo_url") or ph.get("url") or ph.get("photo") or ph.get("image_url"))
        if u:
            out.append(u)
    return list(dict.fromkeys(out))[:8]


def to_item(p):
    num = ctx["num"]
    name = (p.get("name") or "").strip()
    if not name:
        return None
    price, cur, promo = 0.0, "", 0.0
    for sp in p.get("shop_prices") or []:
        rp = num(sp.get("retail_price"))
        if rp > 0:
            price, cur = rp, sp.get("retail_currency") or ""
            pp = num(sp.get("promo_price"))
            promo = pp if 0 < pp < rp else 0.0
            break
    stocks = p.get("shop_measurement_values") or []
    qty = sum(num(s.get("active_measurement_value")) for s in stocks)
    if price <= 0 or (stocks and qty <= 0):
        return None

    details = []
    for f in p.get("custom_fields") or []:
        k, v = str(f.get("custom_field_name") or ""), f.get("custom_field_value")
        if v not in (None, "", []) and not any(s in k.lower() for s in SKIP):
            details.append([k, str(v)])
    for a in p.get("product_attributes") or []:
        if a.get("attribute_value"):
            details.append([str(a.get("attribute_name") or ""), str(a["attribute_value"])])
    cats = [c["name"] for c in p.get("categories") or [] if c.get("name")]
    return {
        "id": str(p.get("id") or p.get("sku") or name),
        "name": name,
        "brand": p.get("brand_name") or "",
        "category": cats[-1] if cats else "Boshqa",
        "price": price, "promo": promo, "currency": cur,
        "qty": qty if stocks else None,
        "photos": photos_of(p),
        "stock": stock_photos(name, details),
        "details": details[:12],
    }


async def load():
    if time.time() - cache["at"] > 120:
        async with lock:
            if time.time() - cache["at"] > 120:
                try:
                    raw = await ctx["billz_products"](False, 20)
                    cache["items"] = [x for x in map(to_item, raw) if x]
                    cache["at"] = time.time()
                    log.info("BOT: do'kon: %s ta tovar", len(cache["items"]))
                except Exception:
                    log.exception("BOT: do'kon uchun Billz xatosi")
                    cache["at"] = time.time() - 90  # 30 soniyadan keyin qayta urinadi
    return cache["items"]


def check_init(init):
    """Telegram initData imzosini tekshiradi. To'g'ri bo'lsa user dict qaytaradi."""
    data = dict(parse_qsl(init or "", keep_blank_values=True))
    got = data.pop("hash", "")
    check = "\n".join("%s=%s" % kv for kv in sorted(data.items()))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not got or not hmac.compare_digest(calc, got):
        return None
    if time.time() - int(data.get("auth_date") or 0) > 86400:
        return None
    try:
        return json.loads(data.get("user") or "{}")
    except ValueError:
        return None


def money(v, cur):
    s = "{:,}".format(int(round(v))).replace(",", " ")
    return s + " $" if (not cur or cur.upper() in ("USD", "$")) else s + " so'm"


async def index(_):
    return web.FileResponse(os.path.join(HERE, "index.html"),
                            headers={"Cache-Control": "no-cache"})


async def logo(_):
    return web.FileResponse(os.path.join(HERE, "logo.png"),
                            headers={"Cache-Control": "public, max-age=86400"})


async def products(_):
    return web.json_response({"items": await load(), "plan": PLAN},
                             headers={"Cache-Control": "no-store"})


async def order(req):
    try:
        body = await req.json()
    except Exception:
        return web.json_response({"ok": False}, status=400)
    user = check_init(body.get("initData"))
    if not user:
        return web.json_response({"ok": False, "error": "auth"}, status=401)
    by_id = {i["id"]: i for i in await load()}
    chosen = [by_id[i] for i in (body.get("items") or [])[:20] if i in by_id]
    phone = str(body.get("phone") or "")[:30]
    try:
        months = int(body.get("months") or 0)
    except (TypeError, ValueError):
        months = 0
    if not PLAN["min"] <= months <= PLAN["max"]:
        months = 0
    if not chosen:
        return web.json_response({"ok": False, "error": "empty"}, status=400)

    totals, downs, monthlies = {}, {}, {}
    lines = []
    for it in chosen:
        p = it["promo"] or it["price"]
        c = it["currency"]
        totals[c] = totals.get(c, 0) + p
        lines.append("• %s — %s" % (it["name"], money(p, c)))
        if months:
            d, mo, _ = plan_calc(p, months)
            downs[c] = downs.get(c, 0) + d
            monthlies[c] = monthlies.get(c, 0) + mo
    join = lambda dct: " + ".join(money(v, c) for c, v in dct.items())
    if months:
        pay = ("Bo'lib to'lash: %s oy\nBoshlang'ich: %s\nOyiga: %s"
               % (months, join(downs), join(monthlies)))
    else:
        pay = "To'lov: to'liq"
    who = (user.get("first_name") or "") + " " + (user.get("last_name") or "")
    uname = "@" + user["username"] if user.get("username") else "username yo'q"
    text = ("🛒 Yangi buyurtma (Mini App)\n\nMijoz: %s (%s)\nTelefon: %s\nID: %s\n\n%s\n\nJami: %s\n%s"
            % (who.strip(), uname, phone or "—", user.get("id"), "\n".join(lines),
               join(totals), pay))
    bot = ctx["bot"]
    try:
        await bot.send_message(int(ADMIN), text)
    except Exception:
        log.exception("BOT: buyurtmani menejerga yuborib bo'lmadi (ADMIN_CHAT_ID?)")
        return web.json_response({"ok": False, "error": "admin"}, status=500)
    try:
        await bot.send_message(user["id"], "Rahmat! Buyurtmangiz qabul qilindi, "
                               "menejerimiz tez orada bog'lanadi.\n\n" + "\n".join(lines) + "\n\n" + pay)
    except Exception:
        pass
    log.info("BOT: Mini App buyurtma: %s ta tovar", len(chosen))
    return web.json_response({"ok": True})


def make_app(bot, billz_products, num):
    ctx.update(bot=bot, billz_products=billz_products, num=num)
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/logo.png", logo)
    app.router.add_get("/api/products", products)
    app.router.add_post("/api/order", order)
    return app


async def set_menu(bot):
    if URL:
        try:
            await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(
                text="Do'kon", web_app=WebAppInfo(url=URL)))
        except Exception:
            log.exception("BOT: menyu tugmasini o'rnatib bo'lmadi")
