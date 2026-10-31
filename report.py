"""Kunlik savdo hisoboti: Billz -> Telegram.

Har kuni 22:00 da (Toshkent) REPORT_TO dagi odamlarga bugungi hisobot boradi:
cheklar, dona, tushum, foyda, marja, nimalar qanchadan sotildi, har biridan foyda,
kategoriyalar va oy boshidan jami.
Botga istalgan payt yozish mumkin: /hisobot, /hisobot kecha, /hisobot 25.10

Render -> Environment (hammasi ixtiyoriy):
  REPORT_TO    - kimga: @username yoki Telegram ID, vergul bilan. Standart: @baxtiyorov_zz
                 (u odam botga kamida bir marta /start bosgan bo'lishi kerak)
  REPORT_HOUR  - soat, Toshkent vaqti. Standart: 22
  REPORT_SHOPS - Billz do'kon ID lari, vergul bilan. Standart: Store UzMacbook
  KEEP_AWAKE   - 0 qilinsa server uxlab qolishiga ruxsat beriladi (unda hisobot kelmasligi mumkin)
"""
import asyncio, datetime, logging, os, re, time
import aiohttp
from aiohttp import web

log = logging.getLogger("BOT")
TZ = datetime.timezone(datetime.timedelta(hours=5))  # Toshkent
REPORT_TO = os.environ.get("REPORT_TO", "@baxtiyorov_zz")
try:
    HOUR = min(23, max(0, int(os.environ.get("REPORT_HOUR", "22"))))
except ValueError:
    HOUR = 22
SHOPS = [s.strip() for s in os.environ.get(
    "REPORT_SHOPS", "539ebeda-9f4f-4a63-82cd-48ae0413cd84").split(",") if s.strip()]
KEEP_AWAKE = os.environ.get("KEEP_AWAKE", "1") != "0"
MAX_ITEMS = 40
PURCHASES = "/v1/customer-purchases-table"

# Billz javobidagi maydonlar, birinchi topilgani ishlatiladi
TOTAL_FIELDS = ("net_gross_sales", "gross_sales", "net_sales", "total_price", "total_sum", "sales_sum")
UNIT_FIELDS = ("sold_price", "sale_price", "retail_price", "price")
SUPPLY_FIELDS = ("supply_price", "net_supply_price")
PROFIT_FIELDS = ("net_profit", "gross_profit", "profit")

WEEKDAYS = ("dushanba", "seshanba", "chorshanba", "payshanba", "juma", "shanba", "yakshanba")
MONTHS = ("yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust",
          "sentabr", "oktabr", "noyabr", "dekabr")

ctx = {}
users = {}          # username (kichik harf) -> chat id, botga yozganlardan
tasks = []
sched = {"day": "", "done": False, "tries": 0, "next": 0.0}
tip_sent = set()


# ---------- Ulash ----------
def setup(app, bot, login, state, billz_url, platform, num, url, admin):
    ctx.update(bot=bot, login=login, state=state, billz_url=billz_url, platform=platform,
               num=num, url=url, admin=str(admin or "").strip())
    app.router.add_get("/api/ping", ping)


def start():
    """Server ishga tushgandan keyin chaqiriladi: 22:00 jadvali va uyg'oq turish."""
    tasks.append(asyncio.create_task(scheduler()))
    if KEEP_AWAKE and ctx.get("url"):
        tasks.append(asyncio.create_task(keep_awake()))
    log.info("BOT: kunlik hisobot: har kuni %s:00, kimga: %s", HOUR, REPORT_TO)


async def ping(_):
    return web.Response(text="ok")


async def keep_awake():
    """Render bepul tarifi 15 daqiqa so'rov kelmasa serverni uxlatadi.
    O'z manziliga har 10 daqiqada so'rov yuborib, server va 22:00 jadvali uyg'oq turadi."""
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as s:
        while True:
            await asyncio.sleep(600)
            try:
                async with s.get(ctx["url"] + "api/ping") as r:
                    await r.read()
            except Exception as e:
                log.warning("BOT: uyg'otish so'rovi o'tmadi: %r", e)


async def remember_mw(handler, event, data):
    """Botga yozgan har bir odamning username -> ID sini eslab qoladi."""
    u = getattr(event, "from_user", None)
    if u and u.username:
        users[u.username.lower()] = u.id
    return await handler(event, data)


# ---------- Kimga yuboriladi ----------
async def recipients():
    """REPORT_TO dan chat ID lar va topilmagan @username lar."""
    ids, missing = [], []
    for t in re.split(r"[\s,;]+", REPORT_TO):
        if not t:
            continue
        if re.fullmatch(r"-?\d+", t):
            ids.append(int(t))
            continue
        name = t.lstrip("@").lower()
        cid = users.get(name) or await _by_admin(name)
        if cid:
            ids.append(cid)
        else:
            missing.append("@" + name)
    return list(dict.fromkeys(ids)), missing


async def _by_admin(name):
    """ADMIN_CHAT_ID shu username ga tegishli bo'lsa, o'shani ishlatadi (server qayta yonganda ham ishlaydi)."""
    admin = ctx.get("admin")
    if not admin or not re.fullmatch(r"-?\d+", admin):
        return None
    try:
        chat = await ctx["bot"].get_chat(int(admin))
        if (chat.username or "").lower() == name:
            users[name] = chat.id
            return chat.id
    except Exception as e:
        log.warning("BOT: ADMIN_CHAT_ID tekshirilmadi: %r", e)
    return None


async def send(chat_id, text):
    for part in split(text, 3800):
        try:
            await ctx["bot"].send_message(chat_id, part)
        except Exception:
            log.exception("BOT: hisobot %s ga yuborilmadi", chat_id)
            return False
    return True


async def notify(text):
    ids, _ = await recipients()
    admin = ctx.get("admin")
    if not ids and admin and re.fullmatch(r"-?\d+", admin):
        ids = [int(admin)]
    for cid in ids:
        await send(cid, text)


def split(text, size):
    parts, cur = [], ""
    for line in text.split("\n"):
        if cur and len(cur) + 1 + len(line) > size:
            parts.append(cur)
            cur = line
        else:
            cur = cur + "\n" + line if cur else line
    if cur:
        parts.append(cur)
    return parts


# ---------- Billz ----------
async def _get(session, path, params):
    state = ctx["state"]
    for attempt in (1, 2):
        if not state.get("token"):
            await ctx["login"](session)
        headers = {"Authorization": "Bearer " + state["token"], "platform-id": ctx["platform"],
                   "Billz-Response-Channel": "HTTP"}
        async with session.get(ctx["billz_url"] + path, params=params, headers=headers) as r:
            if r.status == 401 and attempt == 1:
                state["token"] = ""
                continue
            body = await r.json(content_type=None)
            if r.status != 200:
                raise RuntimeError("Billz %s status=%s %s" % (path, r.status, str(body)[:200]))
            return body or {}
    return {}


async def fetch(day_from, day_to):
    out = []
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90)) as s:
        for shop in SHOPS or [""]:
            got = 0
            for page in range(1, 101):
                params = {"start_date": day_from, "end_date": day_to, "page": page, "limit": 100}
                if shop:
                    params["shop_ids"] = shop
                body = await _get(s, PURCHASES, params)
                items = body.get("purchases") or []
                out.extend(items)
                got += len(items)
                total = ctx["num"](body.get("count"))
                if len(items) < 100 or (total and got >= total):
                    break
    return out


def _field(rows, names):
    for n in names:
        if any(r.get(n) not in (None, "") for r in rows):
            return n
    return ""


def _cat(p):
    c = p.get("categories_path")
    if isinstance(c, list) and c:
        first = c[0]
        return str(first.get("name") if isinstance(first, dict) else first).strip()
    if isinstance(c, str) and c.strip():
        return re.split(r"\s*[>/|]\s*", c.strip())[0]
    return str(p.get("category_name") or "").strip()


def parse(rows):
    """Billz qatorlari -> sotuv va qaytarish yozuvlari."""
    num = ctx["num"]
    f = {"total": _field(rows, TOTAL_FIELDS), "unit": _field(rows, UNIT_FIELDS),
         "supply": _field(rows, SUPPLY_FIELDS), "profit": _field(rows, PROFIT_FIELDS)}
    lines = []
    for p in rows:
        if p.get("order_type") != "Продажа":
            continue
        created = str(p.get("created_at") or "")
        day = created[:10]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            continue
        sold = num(p.get("sold_measurement_value"))
        ret = min(num(p.get("returned_measurement_value")), sold)
        base = {"day": day, "time": created[11:16], "order": str(p.get("order_id") or ""),
                "name": str(p.get("product_name") or "").strip() or "Nomsiz tovar",
                "cat": _cat(p) or "Boshqa"}
        if ret > 0:
            lines.append(dict(base, kind="return", qty=ret))
        qty = sold - ret
        if qty <= 0:
            continue
        profit = num(p.get(f["profit"])) if f["profit"] else 0.0
        if f["total"]:
            rev = num(p.get(f["total"]))
        elif f["unit"]:
            rev = num(p.get(f["unit"])) * qty
        elif f["supply"]:
            rev = num(p.get(f["supply"])) * qty + profit
        else:
            rev = 0.0
        lines.append(dict(base, kind="sale", qty=qty, rev=rev, profit=profit))
    return {"lines": lines, "fields": f, "rows": len(rows)}


# ---------- Hisoblash va matn ----------
def summary(lines, day_from, day_to):
    s = {"orders": 0, "qty": 0.0, "rev": 0.0, "profit": 0.0, "ret": 0.0, "items": {}, "cats": {}}
    seen = set()
    for l in lines:
        if not day_from <= l["day"] <= day_to:
            continue
        if l["kind"] == "return":
            s["ret"] += l["qty"]
            continue
        if not l["order"] or l["order"] not in seen:
            seen.add(l["order"])
            s["orders"] += 1
        s["qty"] += l["qty"]
        s["rev"] += l["rev"]
        s["profit"] += l["profit"]
        for key, group in ((l["name"], "items"), (l["cat"], "cats")):
            g = s[group].setdefault(key, {"name": key, "qty": 0.0, "rev": 0.0, "profit": 0.0})
            g["qty"] += l["qty"]
            g["rev"] += l["rev"]
            g["profit"] += l["profit"]
    return s


def money(x):
    s = ("%.2f" % abs(x))
    if s.endswith(".00"):
        s = s[:-3]
    whole, _, frac = s.partition(".")
    whole = "{:,}".format(int(whole)).replace(",", " ")
    return ("-" if x < -0.004 else "") + "$" + whole + ("." + frac if frac else "")


def qty_str(q):
    return str(int(q)) if q == int(q) else ("%.2f" % q).rstrip("0")


def margin(profit, rev):
    return " (marja %.1f%%)" % (profit / rev * 100) if rev > 0 else ""


def profit_word(p):
    return "⚠️ zarar " + money(-p) if p < 0 else "foyda " + money(p)


def dots(day):
    return "%s.%s.%s" % (day[8:10], day[5:7], day[:4])


def weekday(day):
    return WEEKDAYS[datetime.date.fromisoformat(day).weekday()]


def build_text(parsed, day, live):
    s = summary(parsed["lines"], day, day)
    out = ["📊 Kunlik hisobot: %s, %s" % (dots(day), weekday(day))]
    if live:
        out.append("(soat %s holatiga)" % datetime.datetime.now(TZ).strftime("%H:%M"))
    out.append("")
    if not s["qty"]:
        out.append("Bu kunda sotuv bo'lmadi.")
        if s["ret"]:
            out.append("↩️ Qaytarilgan: %s dona" % qty_str(s["ret"]))
    else:
        out.append("🧾 Cheklar: %s ta, tovarlar: %s dona" % (s["orders"], qty_str(s["qty"])))
        out.append("💵 Tushum: " + money(s["rev"]))
        out.append("💰 Foyda: " + money(s["profit"]) + margin(s["profit"], s["rev"]))
        if s["ret"]:
            out.append("↩️ Qaytarilgan: %s dona" % qty_str(s["ret"]))
        out.append("")
        out.append("📦 Nimalar sotildi:")
        items = sorted(s["items"].values(), key=lambda x: -x["rev"])
        for i, it in enumerate(items[:MAX_ITEMS], 1):
            out.append("%s. %s" % (i, it["name"]))
            out.append("   %s dona × %s = %s, %s" % (qty_str(it["qty"]), money(it["rev"] / it["qty"]),
                                                 money(it["rev"]), profit_word(it["profit"])))
        if len(items) > MAX_ITEMS:
            out.append("... yana %s xil tovar" % (len(items) - MAX_ITEMS))
        cats = sorted(s["cats"].values(), key=lambda x: -x["rev"])
        if len(cats) > 1:
            out.append("")
            out.append("🗂 Kategoriyalar:")
            for c in cats:
                out.append("%s: %s dona, %s, %s" % (c["name"], qty_str(c["qty"]), money(c["rev"]),
                                                   profit_word(c["profit"])))
    ms = summary(parsed["lines"], month_start(day), day)
    out.append("")
    out.append("📅 Oy boshidan (1-%s %s):" % (int(day[8:10]), MONTHS[int(day[5:7]) - 1]))
    out.append("Tushum %s, foyda %s%s" % (money(ms["rev"]), money(ms["profit"]), margin(ms["profit"], ms["rev"])))
    out.append("%s ta chek, %s dona tovar" % (ms["orders"], qty_str(ms["qty"])))
    return "\n".join(out)


# ---------- Sanalar ----------
def today():
    return datetime.datetime.now(TZ).date().isoformat()


def month_start(day):
    return day[:8] + "01"


def parse_day(arg):
    a = (arg or "").strip().lower()
    t = today()
    if a in ("", "bugun", "сегодня"):
        return t
    if a in ("kecha", "вчера"):
        return (datetime.date.fromisoformat(t) - datetime.timedelta(days=1)).isoformat()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", a)
    if not m:
        m2 = re.fullmatch(r"(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{2}|\d{4}))?", a)
        if not m2:
            return ""
        y = int(m2.group(3)) if m2.group(3) else int(t[:4])
        if y < 100:
            y += 2000
        m = (str(y), m2.group(2), m2.group(1))
        explicit_year = bool(m2.group(3))
    else:
        m = m.groups()
        explicit_year = True
    try:
        d = datetime.date(int(m[0]), int(m[1]), int(m[2]))
    except ValueError:
        return ""
    if d.isoformat() > t and not explicit_year:
        try:
            d = d.replace(year=d.year - 1)
        except ValueError:
            return ""
    return d.isoformat() if d.isoformat() <= t else ""


# ---------- Har kuni 22:00 ----------
async def send_daily(day):
    ids, missing = await recipients()
    parsed = parse(await fetch(month_start(day), day))  # Billz xato bersa shu yerda to'xtaydi
    text = build_text(parsed, day, False)
    for cid in ids:
        await send(cid, text)
    if missing:
        await notify("⚠️ Kunlik hisobot %s ga yuborilmadi: u bu botga /start bosmagan "
                     "yoki uning ID sini bilmayman. U botga /hisobot deb yozsin." % ", ".join(missing))
    log.info("BOT: kunlik hisobot yuborildi: %s ta odamga, sotuv qatorlari: %s", len(ids), parsed["rows"])


async def tick(now=None, clock=time.time):
    now = now or datetime.datetime.now(TZ)
    day = now.date().isoformat()
    if sched["day"] != day:
        sched.update(day=day, done=False, tries=0, next=0.0)
    if sched["done"] or now.hour != HOUR or clock() < sched["next"]:
        return
    sched["tries"] += 1
    try:
        await send_daily(day)
        sched["done"] = True
    except Exception as e:
        log.exception("BOT: kunlik hisobot xatosi (%s-urinish)", sched["tries"])
        if sched["tries"] >= 3:
            sched["done"] = True
            await notify("⚠️ Bugungi hisobotni Billz'dan olib bo'lmadi: %s" % str(e)[:200])
        else:
            sched["next"] = clock() + 600  # 10 daqiqadan keyin qayta


async def scheduler():
    while True:
        try:
            await tick()
        except Exception:
            log.exception("BOT: hisobot jadvali xatosi")
        await asyncio.sleep(60)


# ---------- /hisobot ----------
async def on_command(m, args):
    """Ruxsat bo'lsa hisobotni yuboradi va True qaytaradi. Begona odam uchun False."""
    ids, _ = await recipients()
    admin = ctx.get("admin")
    if m.chat.id not in ids and str(m.chat.id) != admin:
        return False
    day = parse_day(args)
    if not day:
        await send(m.chat.id, "Masalan:\n/hisobot - bugungi\n/hisobot kecha - kechagi\n/hisobot 25.10 - shu kungi")
        return True
    try:
        parsed = parse(await fetch(month_start(day), day))
    except Exception:
        log.exception("BOT: /hisobot uchun Billz xatosi")
        await send(m.chat.id, "⚠️ Billz'dan ma'lumot olib bo'lmadi, birozdan keyin qayta yozing.")
        return True
    await send(m.chat.id, build_text(parsed, day, day == today()))
    # @username orqali topilgan bo'lsa: server qayta yonganda ham ishlashi uchun ID ni yozib qo'yish maslahati
    numeric = set(re.findall(r"-?\d+", REPORT_TO))
    if str(m.chat.id) not in numeric and str(m.chat.id) != admin and m.chat.id not in tip_sent:
        tip_sent.add(m.chat.id)
        await send(m.chat.id, "Kunlik hisobot har kuni %s:00 da shu yerga keladi. Doim ishonchli kelishi uchun "
                              "Render → Environment ga REPORT_TO = %s deb yozib qo'ying." % (HOUR, m.chat.id))
    return True
