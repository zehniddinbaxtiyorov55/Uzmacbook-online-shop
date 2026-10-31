"""Kunlik savdo hisoboti: Billz -> Telegram.

Har kuni 22:00 da (Toshkent) REPORT_TO dagi odamlarga bugungi hisobot boradi:
cheklar, dona, tushum, foyda, marja; har bir chek bo'yicha: qaysi tovar va uning
xarakteristikalari, qanchaga sotilgani, foydasi, to'lov turlari (naqd, kimning kartasi,
qarz, trade-in - Billz'dagi to'lov turi nomi bilan) va chekdagi izoh; kun bo'yicha
to'lov turlari jami, kategoriyalar va oy boshidan jami. Mijoz ismi/telefoni yozilmaydi.
Botga istalgan payt yozish mumkin: /hisobot, /hisobot kecha, /hisobot 25.10
(/hisobot maydonlar - Billz maydon nomlarini ko'rsatadi, sozlash uchun)

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
MAX_ORDERS = 30     # xabarda ko'pi bilan nechta chek batafsil ko'rsatiladi
MAX_SPECS = 8       # bitta tovarga nechta xarakteristika
PURCHASES = "/v1/customer-purchases-table"
SKIP_SPEC = ("seriya", "imei", "serial", "shtrix", "barcode")

# Billz javobidagi maydonlar, birinchi topilgani ishlatiladi
TOTAL_FIELDS = ("sold_with_discount", "net_gross_sales", "gross_sales", "net_sales", "total_price",
                "total_sum", "sales_sum")
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
spec_cache = {}     # tovar -> (vaqt, xarakteristikalar)


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
                "cat": _cat(p) or "Boshqa",
                "pid": str(p.get("product_id") or ""), "sku": str(p.get("product_sku") or ""),
                "spec": specs_of(p, ("product_custom_fields", "custom_fields"))}
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
    return {"lines": lines, "fields": f, "rows": len(rows), "sample": rows[0] if rows else {}}


# ---------- Chek tafsilotlari: to'lovlar, izoh, xarakteristikalar ----------
def specs_of(p, keys=("custom_fields",)):
    """Tovar xarakteristikalari ("Sikl: 187" kabi), seriya/IMEI siz. Topilmasa []."""
    out = []
    for key in keys:
        for f in p.get(key) or []:
            if not isinstance(f, dict):
                continue
            name = str(f.get("custom_field_name") or f.get("name") or "").strip()
            val = f.get("custom_field_value", f.get("value"))
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val if v not in (None, ""))
            if val in (None, "") or not name or any(s in name.lower() for s in SKIP_SPEC):
                continue
            out.append("%s: %s" % (name, str(val).strip()))
    for a in p.get("product_attributes") or []:
        if isinstance(a, dict) and a.get("attribute_value"):
            out.append("%s: %s" % (a.get("attribute_name") or "", a["attribute_value"]))
    return list(dict.fromkeys(out))[:MAX_SPECS]


def parse_order(body):
    """GET /v2/order/:id javobi -> to'lovlar, qarz, izoh, tovarlar."""
    num = ctx["num"]
    if "order_detail" not in body and isinstance(body.get("data"), dict):
        body = body["data"]
    d = body.get("order_detail") or {}
    pays = []
    for p in d.get("order_payments") or []:
        t = p.get("company_payment_type") or {}
        name = str(t.get("name") or p.get("payment_type_name") or p.get("name") or "To'lov").strip()
        amount = num(p.get("paid_amount")) - num(p.get("returned_amount"))
        if abs(amount) > 0.004:
            pays.append([name, amount])
    for key, label in (("loyalty_payment", "Bonus/cashback"), ("gift_card_payment", "Sertifikat")):
        v = num(d.get(key))
        if v > 0:
            pays.append([label, v])
    items = []
    for it in d.get("order_items") or []:
        pr = it.get("product") or {}
        items.append({"id": str(pr.get("id") or ""), "sku": str(pr.get("sku") or ""),
                      "name": str(pr.get("name") or "").strip()})
    comment = re.sub(r"[ \t]+", " ", str(d.get("comment") or "")).strip()[:400]
    return {"number": str(body.get("order_number") or ""), "comment": comment,
            "payments": pays, "debt": max(0.0, num(body.get("debt"))), "items": items,
            "keys": sorted(d.keys())}


def _pick_product(products, ref):
    for key, field in (("id", "id"), ("sku", "sku")):
        if ref.get(key):
            for p in products:
                if str(p.get(field) or "") == ref[key]:
                    return p
    for p in products:
        if (p.get("name") or "").strip().lower() == ref["name"].lower():
            return p
    return products[0] if len(products) == 1 else None


async def fetch_details(lines, day):
    """Kun cheklari uchun Billz'dan to'lovlar, izohlar va xarakteristikalar.
    Xato bo'lsa bo'sh qaytaradi: hisobot baribir yuboriladi."""
    order_ids = list(dict.fromkeys(l["order"] for l in lines
                                   if l["kind"] == "sale" and l["day"] == day and l["order"]))
    orders, specs = {}, {}
    sem = asyncio.Semaphore(5)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90)) as s:
        async def one_order(oid):
            async with sem:
                try:
                    orders[oid] = parse_order(await _get(s, "/v2/order/" + oid, None))
                except Exception as e:
                    log.warning("BOT: chek %s tafsiloti olinmadi: %r", oid, e)
        await asyncio.gather(*(one_order(o) for o in order_ids))

        # xarakteristikasi yo'q tovarlar: chekdagi tovar ID/SKU bo'yicha Billz'dan qidiriladi
        refs, line_key = {}, {}
        for l in lines:
            if l["kind"] != "sale" or l["day"] != day or l["spec"]:
                continue
            ref = {"id": l["pid"], "sku": l["sku"], "name": l["name"]}
            for it in (orders.get(l["order"]) or {}).get("items", []):
                if it["name"].lower() == l["name"].lower() or (l["pid"] and it["id"] == l["pid"]):
                    ref = {"id": it["id"] or l["pid"], "sku": it["sku"] or l["sku"], "name": l["name"]}
                    break
            key = ref["id"] or ref["sku"] or l["name"].lower()
            refs[key] = ref
            line_key[(l["order"], l["name"])] = key

        found_specs = {}

        async def one_spec(key, ref):
            hit = spec_cache.get(key)
            if hit and time.time() - hit[0] < 6 * 3600:
                found_specs[key] = hit[1]
                return
            async with sem:
                try:
                    body = await _get(s, "/v2/products", {"search": ref["sku"] or ref["name"], "limit": 20,
                                                          "include_empty_stocks": "true"})
                    p = _pick_product(body.get("products") or [], ref)
                    found_specs[key] = specs_of(p) if p else []
                    spec_cache[key] = (time.time(), found_specs[key])
                except Exception as e:
                    log.warning("BOT: %s xarakteristikasi olinmadi: %r", ref["name"], e)
        await asyncio.gather(*(one_spec(k, r) for k, r in refs.items()))
        for lk, key in line_key.items():
            specs[lk] = found_specs.get(key) or []
    return {"orders": orders, "specs": specs, "asked": len(order_ids)}


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


def order_blocks(lines, day, details):
    """Har bir chek uchun matn bloki va kun bo'yicha to'lov turlari jami."""
    orders, specs = details.get("orders", {}), details.get("specs", {})
    groups = {}
    for i, l in enumerate(lines):
        if l["kind"] == "sale" and l["day"] == day:
            groups.setdefault(l["order"] or "#%s" % i, []).append(l)
    keys = sorted(groups, key=lambda k: min(x["time"] for x in groups[k]))
    blocks, totals = [], {}
    for n, key in enumerate(keys, 1):
        g = sorted(groups[key], key=lambda x: -x["rev"])
        o = orders.get(key) or {}
        head = "%s) %s" % (n, g[0]["time"]) + (" · chek %s" % o["number"] if o.get("number") else "")
        rows = [head]
        for l in g:
            rows.append("• %s%s — %s, %s" % (l["name"], " ×" + qty_str(l["qty"]) if l["qty"] != 1 else "",
                                             money(l["rev"]), profit_word(l["profit"])))
            spec = l["spec"] or specs.get((l["order"], l["name"])) or []
            if spec:
                rows.append("  " + " · ".join(spec))
        pays = [[name, amt] for name, amt in o.get("payments", [])]
        if o.get("debt"):
            pays.append(["qarz (bo'lib to'lash)", o["debt"]])
        if pays:
            rows.append("💳 " + " + ".join("%s %s" % (money(a), name) for name, a in pays))
            for name, a in pays:
                totals[name] = totals.get(name, 0.0) + a
        if o.get("comment"):
            rows.append("📝 " + o["comment"])
        blocks.append("\n".join(rows))
    return blocks, totals


def build_text(parsed, day, live, details=None):
    details = details or {}
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
        blocks, totals = order_blocks(parsed["lines"], day, details)
        out.append("")
        out.append("🧾 Sotuvlar:")
        for b in blocks[:MAX_ORDERS]:
            out.append("")
            out.append(b)
        if len(blocks) > MAX_ORDERS:
            out.append("")
            out.append("... yana %s ta chek" % (len(blocks) - MAX_ORDERS))
        if details.get("asked") and not details.get("orders"):
            out.append("")
            out.append("(to'lov va izohlarni Billz'dan olib bo'lmadi)")
        if totals:
            out.append("")
            out.append("💳 Bugungi to'lovlar:")
            for name, a in sorted(totals.items(), key=lambda x: -x[1]):
                out.append("%s: %s" % (name[:1].upper() + name[1:], money(a)))
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
    text = build_text(parsed, day, False, await safe_details(parsed, day))
    for cid in ids:
        await send(cid, text)
    if missing:
        await notify("⚠️ Kunlik hisobot %s ga yuborilmadi: u bu botga /start bosmagan "
                     "yoki uning ID sini bilmayman. U botga /hisobot deb yozsin." % ", ".join(missing))
    log.info("BOT: kunlik hisobot yuborildi: %s ta odamga, sotuv qatorlari: %s", len(ids), parsed["rows"])


async def safe_details(parsed, day):
    try:
        return await fetch_details(parsed["lines"], day)
    except Exception:
        log.exception("BOT: chek tafsilotlari xatosi")
        return {"asked": 1}


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
    if (args or "").strip().lower() in ("maydonlar", "debug"):
        await send(m.chat.id, await fields_text())
        return True
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
    await send(m.chat.id, build_text(parsed, day, day == today(), await safe_details(parsed, day)))
    # @username orqali topilgan bo'lsa: server qayta yonganda ham ishlashi uchun ID ni yozib qo'yish maslahati
    numeric = set(re.findall(r"-?\d+", REPORT_TO))
    if str(m.chat.id) not in numeric and str(m.chat.id) != admin and m.chat.id not in tip_sent:
        tip_sent.add(m.chat.id)
        await send(m.chat.id, "Kunlik hisobot har kuni %s:00 da shu yerga keladi. Doim ishonchli kelishi uchun "
                              "Render → Environment ga REPORT_TO = %s deb yozib qo'ying." % (HOUR, m.chat.id))
    return True


async def fields_text():
    """Sozlash uchun: Billz qaytarayotgan maydon nomlari (qiymatlarsiz, mijoz ma'lumotisiz)."""
    t = today()
    start = (datetime.date.fromisoformat(t) - datetime.timedelta(days=30)).isoformat()
    try:
        parsed = parse(await fetch(start, t))
    except Exception as e:
        return "Billz xatosi: %s" % str(e)[:200]
    out = ["Oxirgi 30 kun: %s ta qator" % parsed["rows"],
           "Hisobda: tushum=%s, foyda=%s" % (parsed["fields"]["total"] or parsed["fields"]["unit"]
                                              or parsed["fields"]["supply"] or "TOPILMADI",
                                              parsed["fields"]["profit"] or "TOPILMADI"),
           "", "Sotuv qatori maydonlari:", ", ".join(sorted(parsed["sample"].keys()))]
    sales = [l for l in parsed["lines"] if l["kind"] == "sale"]
    if sales:
        last = sales[-1]
        try:
            d = await fetch_details([last], last["day"])
            o = d["orders"].get(last["order"])
            if o:
                out += ["", "Chek maydonlari:", ", ".join(o["keys"]),
                        "To'lov turlari: " + (", ".join(n for n, _ in o["payments"]) or "yo'q"),
                        "Izoh bormi: " + ("ha" if o["comment"] else "yo'q")]
            sp = last["spec"] or d["specs"].get((last["order"], last["name"])) or []
            out += ["", "Xarakteristika nomlari: " + (", ".join(x.split(":")[0] for x in sp) or "topilmadi")]
        except Exception as e:
            out.append("Chek xatosi: %s" % str(e)[:200])
    return "\n".join(out)
