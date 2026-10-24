"""Telegram Mini App do'kon: Billz tovarlari (rasm, narx, qoldiq) + savat + buyurtma."""
import asyncio, datetime, hashlib, hmac, html as htmlmod, json, logging, math, os, re, time
import aiohttp
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
    "pct": float(os.environ.get("INSTALLMENT_MONTHLY_PCT", "6")),
}


def plan_calc(price, months):
    down = math.ceil(price * PLAN["down"] / 100)
    rest = round((price - down) * (1 + PLAN["pct"] / 100 * months), 2)
    monthly = math.ceil(rest * 100 / months - 1e-9) / 100
    return down, monthly, round(down + rest, 2)

cache = {"items": [], "at": 0.0}
rate_cache = {"rate": None, "date": "", "src": "", "at": 0.0, "busy": False, "task": None, "diag": {}}
CBU = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/USD/%s"
RATE_TTL = 3600                                            # kurs har soatda tekshiriladi
RATE_EXTRA = float(os.environ.get("USD_RATE_EXTRA", "0"))  # kursga qo'shimcha so'm
BANK_PAGES = ["https://bank.uz/currency/dollar-ssha-uz-aqsh-dollari",
              "https://exchangerates.uz/rates/tashkent"]
UA = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
                    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
      "Accept-Language": "ru,uz;q=0.9"}


def buy_rates_from_html(page, cbu=None):
    """Sahifadagi 'Покупка' (bank olish) bo'limidagi kurslarni ajratib oladi."""
    page = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", page)
    text = htmlmod.unescape(re.sub(r"(?s)<[^>]+>", "\n", page)).replace("\xa0", " ")
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    lo, hi = (cbu * 0.9, cbu * 1.005) if cbu else (5000, 30000)
    out, inside = [], False
    for l in lines:
        low = l.lower()
        if low.startswith(("покупка", "sotib olish", "olish", "buy")):
            inside = True
            continue
        if low.startswith(("продажа", "sotish", "sell")):
            inside = False
            continue
        if inside:
            m = re.fullmatch(r"(\d{1,2} ?\d{3})(?:[.,]\d+)?\s*(сум|so'?m|uzs)?\.?", l, re.I)
            if m:
                v = int(m.group(1).replace(" ", ""))
                if lo <= v <= hi:
                    out.append(v)
    return out


async def _cbu_day(session, day):
    try:
        async with session.get(CBU % (day.isoformat() + "/" if day else "")) as r:
            data = await r.json(content_type=None)
        for row in data if isinstance(data, list) else [data]:
            low = {str(k).lower(): v for k, v in row.items()}
            if str(low.get("ccy", "")).upper() == "USD":
                return float(str(low.get("rate")).replace(",", ".")), str(low.get("date", ""))
    except Exception:
        pass
    return None


def usd_rate():
    """Saqlangan kursni darrov qaytaradi; eskirgan bo'lsa orqa fonda yangilaydi."""
    if time.time() - rate_cache["at"] > RATE_TTL and not rate_cache["busy"]:
        rate_cache["busy"] = True
        rate_cache["task"] = asyncio.get_event_loop().create_task(refresh_rate())
    return rate_cache["rate"], rate_cache["date"] + (" · " + rate_cache["src"] if rate_cache["src"] else "")


async def refresh_rate():
    """Banklarning bugungi dollar OLISH kursi: eng balandi (bank.uz). Bo'lmasa — MB kursi."""
    try:
        await asyncio.wait_for(_refresh_rate(), 30)
    except Exception:
        log.warning("BOT: MB kursi 30 soniyada kelmadi")
        if not rate_cache["rate"] and os.environ.get("USD_RATE"):
            rate_cache.update(rate=float(os.environ["USD_RATE"]), date="qo'lda", at=time.time())
        if not rate_cache["rate"]:
            rate_cache["at"] = time.time() - RATE_TTL + 300
    finally:
        rate_cache["busy"] = False


async def _refresh_rate():
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5))).date()  # Toshkent
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            got = await _cbu_day(session, today) or await _cbu_day(session, None)  # bugungi, bo'lmasa oxirgisi
            cbu = got[0] if got and got[0] > 0 else None
            rate_cache["diag"] = {"cbu.uz": cbu}
            buys = []
            for url in BANK_PAGES:
                try:
                    async with session.get(url, headers=UA) as r:
                        page = await r.text(errors="ignore")
                    buys = buy_rates_from_html(page, cbu)
                except Exception as e:
                    log.warning("BOT: %s ochilmadi: %r", url, e)
                rate_cache["diag"][url.split("/")[2]] = len(buys)
                if len(buys) >= 3:
                    break
        if len(buys) >= 3:
            best = max(buys)
            rate = round((best + RATE_EXTRA) / 10) * 10
            rate_cache.update(rate=rate, date=today.strftime("%d.%m.%Y"), src="banklar olish kursi", at=time.time())
            log.info("BOT: banklar olish kursi: %s ta bank, eng past %s, eng baland %s -> %s",
                     len(buys), min(buys), best, rate)
        elif cbu:
            rate = math.ceil((cbu + RATE_EXTRA) / 10) * 10
            rate_cache.update(rate=rate, date=got[1], src="Markaziy bank", at=time.time())
            log.warning("BOT: banklar kursi topilmadi, MB kursi ishlatildi: %s -> %s", cbu, rate)
    except Exception:
        log.exception("BOT: MB kursini olib bo'lmadi")
    if not rate_cache["rate"] and os.environ.get("USD_RATE"):
        rate_cache.update(rate=float(os.environ["USD_RATE"]), date="qo'lda", at=time.time())
    if not rate_cache["rate"]:
        rate_cache["at"] = time.time() - RATE_TTL + 300  # 5 daqiqadan keyin qayta urinadi
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
    v = round(v, 2)
    s = ("{:,.0f}" if v == int(v) else "{:,.2f}").format(v).replace(",", " ")
    return s + " $" if (not cur or cur.upper() in ("USD", "$")) else s + " so'm"


async def index(_):
    return web.FileResponse(os.path.join(HERE, "index.html"),
                            headers={"Cache-Control": "no-cache"})


async def rate_info(_):
    rate, rdate = usd_rate()
    return web.json_response({"rate": rate, "date": rdate, "topilgan": rate_cache.get("diag")})


async def logo(_):
    return web.FileResponse(os.path.join(HERE, "logo.png"),
                            headers={"Cache-Control": "public, max-age=86400"})


async def products(_):
    rate, rdate = usd_rate()
    if rate is None and rate_cache["task"]:
        # birinchi ochilishda kurs hali kelmagan bo'lsa, tovarlar bilan birga kutamiz (ko'pi 12 soniya)
        try:
            await asyncio.wait_for(asyncio.shield(rate_cache["task"]), 12)
        except Exception:
            pass
        rate, rdate = usd_rate()
    items = await load()
    return web.json_response({"items": items, "plan": PLAN, "usd_uzs": rate, "rate_date": rdate},
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
        totals2 = {}
        for it in chosen:
            c = it["currency"]
            totals2[c] = totals2.get(c, 0) + plan_calc(it["promo"] or it["price"], months)[2]
        pay = ("Bo'lib to'lash: %s oy (+%g%% oyiga)\nBoshlang'ich: %s\nOyiga: %s\nBo'lib to'lashda jami: %s"
               % (months, PLAN["pct"], join(downs), join(monthlies), join(totals2)))
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
    app.router.add_get("/api/rate", rate_info)
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
