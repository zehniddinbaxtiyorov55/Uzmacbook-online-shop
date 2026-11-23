"""Telegram Mini App do'kon: Billz tovarlari (rasm, narx, qoldiq) + savat + buyurtma."""
import asyncio, datetime, hashlib, hmac, html as htmlmod, json, logging, math, os, re, time
import aiohttp
from urllib.parse import parse_qsl
from aiohttp import web
from aiogram.types import MenuButtonWebApp, WebAppInfo
from stock_photos import stock_photos
import db
import model_photos
import settings

log = logging.getLogger("BOT")
HERE = os.path.dirname(os.path.abspath(__file__))
URL = os.environ.get("WEBAPP_URL") or os.environ.get("RENDER_EXTERNAL_URL", "")
if URL and not URL.endswith("/"):
    URL += "/"
ADMIN = os.environ.get("ADMIN_CHAT_ID", "")       # buyurtmalar keladigan chat
ADMIN_HOST = os.environ.get("ADMIN_HOST", "").strip()  # admin panel manzili, masalan admin.magicpro.uz
TOKEN = os.environ["BOT_TOKEN"]
SKIP = ("seriya", "imei", "serial")
# Bo'lib to'lash: boshlang'ich %, oylar oralig'i, umumiy narxga har oy qo'shiladigan ustama %.
# Standart qiymatlar env'dan, admin panelda o'zgartirilsa — bazadagisi ishlatiladi.
settings.DEFAULTS.update(
    inst_down=os.environ.get("INSTALLMENT_DOWN_PCT", "50"),
    inst_min=os.environ.get("INSTALLMENT_MIN_MONTHS", "3"),
    inst_max=os.environ.get("INSTALLMENT_MAX_MONTHS", "8"),
    inst_pct=os.environ.get("INSTALLMENT_MONTHLY_PCT", "6"),
    usd_rate_extra=os.environ.get("USD_RATE_EXTRA", "0"),
    usd_rate=os.environ.get("USD_RATE", ""),  # zaxira kurs (admin panelda o'zgartiriladi)
    order_thanks="Rahmat! Buyurtmangiz qabul qilindi, menejerimiz tez orada bog'lanadi.",
)


def plan():
    return {"down": settings.num("inst_down"), "min": int(settings.num("inst_min")),
            "max": int(settings.num("inst_max")), "pct": settings.num("inst_pct")}


MAC_RX = re.compile(r"macbook|\bmbp\b|\bmba\b", re.I)


def is_mac(name, category, details):
    """Bo'lib to'lash hozircha faqat MacBooklar uchun."""
    return bool(MAC_RX.search(" ".join([name, category] + [v for _, v in details])))


def plan_calc(price, months, p=None):
    # Boshlang'ich to'lov + (qolgan summa + har oy umumiy narxning p["pct"]% i)
    # Masalan $2000, 3 oy: down $1000, ustama 6%*2000*3=$360, qolgani $1000+$360=$1360, jami $2360
    p = p or plan()
    down = math.ceil(price * p["down"] / 100)
    markup = price * p["pct"] / 100 * months
    rest = round((price - down) + markup, 2)
    monthly = math.ceil(rest * 100 / months - 1e-9) / 100
    return down, monthly, round(down + rest, 2)

cache = {"items": [], "at": 0.0}
rate_cache = {"rate": None, "date": "", "src": "", "at": 0.0, "busy": False, "task": None, "diag": {}}
CBU = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/USD/%s"
RATE_TTL = 3600                                            # kurs har soatda tekshiriladi
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


def apply_manual_rate():
    """Bank saytlari ochilmay, hali birorta kurs ham olinmagan bo'lsa — admin paneldagi zaxira kurs."""
    manual = settings.num("usd_rate")
    if not rate_cache["rate"] and manual > 0:
        rate_cache.update(rate=manual, date="zaxira kurs", src="", at=time.time())
        log.warning("BOT: bank kursi olinmadi, zaxira kurs ishlatildi: %s", manual)


async def refresh_rate():
    """Banklarning bugungi dollar OLISH kursi: eng balandi (bank.uz). Bo'lmasa — MB kursi."""
    try:
        await asyncio.wait_for(_refresh_rate(), 30)
    except Exception:
        log.warning("BOT: MB kursi 30 soniyada kelmadi")
        apply_manual_rate()
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
            rate = round((best + settings.num("usd_rate_extra")) / 10) * 10
            rate_cache.update(rate=rate, date=today.strftime("%d.%m.%Y"), src="banklar olish kursi", at=time.time())
            log.info("BOT: banklar olish kursi: %s ta bank, eng past %s, eng baland %s -> %s",
                     len(buys), min(buys), best, rate)
        elif cbu:
            rate = math.ceil((cbu + settings.num("usd_rate_extra")) / 10) * 10
            rate_cache.update(rate=rate, date=got[1], src="Markaziy bank", at=time.time())
            log.warning("BOT: banklar kursi topilmadi, MB kursi ishlatildi: %s -> %s", cbu, rate)
    except Exception:
        log.exception("BOT: MB kursini olib bo'lmadi")
    apply_manual_rate()
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

    details, serial = [], []  # serial (seriya/IMEI) — faqat menejerga, Mini App'ga yuborilmaydi
    pairs = [(f.get("custom_field_name"), f.get("custom_field_value")) for f in p.get("custom_fields") or []]
    pairs += [(a.get("attribute_name"), a.get("attribute_value")) for a in p.get("product_attributes") or []]
    for k, v in pairs:
        k = str(k or "")
        if v in (None, "", []):
            continue
        (serial if any(s in k.lower() for s in SKIP) else details).append([k, str(v)])
    cats = [c["name"] for c in p.get("categories") or [] if c.get("name")]
    mkey, mlabel = model_photos.key_of(name, details, cats[-1] if cats else "")
    return {
        "id": str(p.get("id") or p.get("sku") or name),
        "name": name,
        "brand": p.get("brand_name") or "",
        "category": cats[-1] if cats else "Boshqa",
        "price": price, "promo": promo, "currency": cur,
        "qty": qty if stocks else None,
        "photos": photos_of(p),
        "stock": stock_photos(name, details, cats[-1] if cats else ""),
        "mac": is_mac(name, cats[-1] if cats else "", details),
        "mkey": mkey, "mlabel": mlabel,
        "details": details[:12],
        "_serial": serial,  # "_" bilan boshlanganlar Mini App'ga chiqmaydi (products() da olib tashlanadi)
    }


def serial_text(item):
    """'Seriya raqami: C02XYZ' — buyurtma xabari va admin panel uchun."""
    return " · ".join("%s: %s" % (k, v) for k, v in item.get("_serial") or [])


def visible(items):
    """Admin panelda yashirilgan tovarlar va kategoriyalarsiz."""
    hidden, cats = db.hidden_ids(), db.hidden_cats()
    if not (hidden or cats):
        return items
    return [i for i in items if i["id"] not in hidden and i["category"] not in cats]


def public(i):
    """Mini App'ga boradigan ko'rinish: maxfiy maydonlarsiz (seriya va h.k.) + model rasmlari."""
    out = {k: v for k, v in i.items() if not k.startswith("_")}
    out["mphotos"] = model_photos.urls(i.get("mkey") or "")
    return out


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


async def photos_info(_):
    """Tekshiruv: har bir tovarga qaysi rasm qo'yilgani."""
    rows = []
    for i in await load():
        mp = model_photos.urls(i.get("mkey") or "")
        src = "billz" if i["photos"] else ("model" if mp else ("apple" if i["stock"] else "yo'q"))
        url = (i["photos"] or mp or i["stock"] or [""])[0]
        rows.append({"nom": i["name"], "kategoriya": i["category"], "rasm": src,
                     "guruh": i.get("mlabel") or "",
                     "fayl": url.rsplit("/", 1)[-1] if src == "apple" else url[:80]})
    rows.sort(key=lambda r: (r["rasm"], r["kategoriya"], r["nom"]))
    return web.json_response({"jami": len(rows), "tovarlar": rows},
                             dumps=lambda o: json.dumps(o, ensure_ascii=False, indent=1))


async def model_photo(req):
    """Admin paneldan yuklangan model rasmlari. Fayl nomi har safar yangi — abadiy keshlanadi."""
    p = model_photos.path(req.match_info["key"], req.match_info["name"])
    if not p:
        raise web.HTTPNotFound()
    return web.FileResponse(p, headers={"Cache-Control": "public, max-age=31536000, immutable"})


async def me(req):
    try:
        body = await req.json()
    except Exception:
        body = {}
    user = check_init(body.get("initData"))
    if not user:
        return web.json_response({"ok": False}, status=401)
    return web.json_response({"ok": True, "phone": db.get_phone(user.get("id"))})


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
    items = [public(i) for i in visible(await load())]
    return web.json_response({"items": items, "plan": plan(), "usd_uzs": rate,
                              "rate_date": rdate},
                             headers={"Cache-Control": "no-store"})


async def order(req):
    try:
        body = await req.json()
    except Exception:
        return web.json_response({"ok": False}, status=400)
    user = check_init(body.get("initData"))
    if not user:
        return web.json_response({"ok": False, "error": "auth"}, status=401)
    by_id = {i["id"]: i for i in visible(await load())}
    chosen = [by_id[i] for i in (body.get("items") or [])[:20] if i in by_id]
    uid = user.get("id")
    phone = db.get_phone(uid)
    if not phone and body.get("shared"):
        # Telegram kontakt xabari botga biroz kechikib kelishi mumkin
        for _ in range(16):
            await asyncio.sleep(0.5)
            phone = db.get_phone(uid)
            if phone:
                break
    raw_phone = phone or str(body.get("phone") or "")[:30]
    if phone:
        phone += " (Telegram ✓)"
    else:
        phone = str(body.get("phone") or "")[:30]
        phone = (phone + " (qo'lda yozilgan)") if phone else ""
    try:
        months = int(body.get("months") or 0)
    except (TypeError, ValueError):
        months = 0
    p = plan()
    if not p["min"] <= months <= p["max"]:
        months = 0
    if not chosen:
        return web.json_response({"ok": False, "error": "empty"}, status=400)
    if not any(it.get("mac") for it in chosen):
        months = 0

    totals, downs, monthlies = {}, {}, {}
    lines, admin_lines = [], []  # mijozga — seriyasiz, menejerga — seriya bilan
    for it in chosen:
        pr = it["promo"] or it["price"]
        c = it["currency"]
        totals[c] = totals.get(c, 0) + pr
        lines.append("• %s — %s" % (it["name"], money(pr, c)))
        sn = serial_text(it)
        admin_lines.append(lines[-1] + ("\n   🔢 %s" % sn if sn else ""))
        if months and it.get("mac"):
            d, mo, _ = plan_calc(pr, months, p)
            downs[c] = downs.get(c, 0) + d
            monthlies[c] = monthlies.get(c, 0) + mo
        elif months:
            downs[c] = downs.get(c, 0) + pr  # MacBook emas — to'liq to'lanadi
    join = lambda dct: " + ".join(money(v, c) for c, v in dct.items())
    if months:
        totals2 = {}
        for it in chosen:
            c = it["currency"]
            pr = it["promo"] or it["price"]
            totals2[c] = totals2.get(c, 0) + (plan_calc(pr, months, p)[2] if it.get("mac") else pr)
        pay = ("Bo'lib to'lash: %s oy (har oy narxning +%g%% ustama)\nBoshlang'ich: %s\nOyiga: %s\nBo'lib to'lashda jami: %s"
               % (months, p["pct"], join(downs), join(monthlies), join(totals2)))
    else:
        pay = "To'lov: to'liq"
    who = (user.get("first_name") or "") + " " + (user.get("last_name") or "")
    uname = "@" + user["username"] if user.get("username") else "username yo'q"
    oid = db.add_order(
        uid, who.strip(), user.get("username") or "", raw_phone,
        [{"id": it["id"], "name": it["name"], "price": it["promo"] or it["price"],
          "currency": it["currency"], "mac": bool(it.get("mac")), "serial": serial_text(it)}
         for it in chosen],
        totals, months, pay)
    text = ("🛒 Yangi buyurtma №%s (Mini App)\n\nMijoz: %s (%s)\nTelefon: %s\nID: %s\n\n%s\n\nJami: %s\n%s"
            % (oid, who.strip(), uname, phone or "—", user.get("id"), "\n".join(admin_lines),
               join(totals), pay))
    if ADMIN_HOST:
        text += "\n\nAdmin panel: https://%s/admin#orders" % ADMIN_HOST
    bot = ctx["bot"]
    try:
        await bot.send_message(int(ADMIN), text)
    except Exception:
        # buyurtma bazada saqlandi — admin panelda ko'rinadi
        log.exception("BOT: buyurtmani menejerga yuborib bo'lmadi (ADMIN_CHAT_ID?)")
    try:
        await bot.send_message(user["id"], settings.get("order_thanks") + "\n\nBuyurtma №%s\n" % oid
                               + "\n".join(lines) + "\n\n" + pay)
    except Exception:
        pass
    log.info("BOT: Mini App buyurtma: %s ta tovar", len(chosen))
    return web.json_response({"ok": True})


def make_app(bot, billz_products, num):
    ctx.update(bot=bot, billz_products=billz_products, num=num)
    app = web.Application(client_max_size=12 * 1024 * 1024)  # admin paneldan rasm yuklash uchun
    app.router.add_get("/", index)
    app.router.add_get("/logo.png", logo)
    app.router.add_get("/api/rate", rate_info)
    app.router.add_get("/api/photos", photos_info)
    app.router.add_get("/mp/{key}/{name}", model_photo)
    app.router.add_get("/api/products", products)
    app.router.add_post("/api/order", order)
    app.router.add_post("/api/me", me)
    app.router.add_get("/api/alive", alive)
    return app


ALIVE = hashlib.sha256(("alive:" + TOKEN).encode()).hexdigest()[:24]


async def alive(_):
    """Bot o'z HTTPS manzili ishlayotganini (va aynan shu server ekanini) tekshirishi uchun."""
    return web.Response(text=ALIVE)


async def set_menu(bot):
    if URL:
        try:
            await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(
                text="Do'kon", web_app=WebAppInfo(url=URL)))
        except Exception:
            log.exception("BOT: menyu tugmasini o'rnatib bo'lmadi")
