# -*- coding: utf-8 -*-
"""Billz tovaridan post ma'lumotini yig'ish va post matnini (HTML) chizish. Telegramga bog'liq emas.

Post bo'limlari (har biri alohida tahrirlanadi):
  Sarlavha · Holati · Rangi · Battery (sikl + yomkost) · Xotira (RAM + SSD) ·
  Kafolat (90/30 kun) · Komplekt (Zaryadka / Full box) · Narx · Muddatli to'lov (mavjud / mavjud emas)
"""
import html
import math
import re

import post_config as cfg

LABELS = {
    "nomi": "Nomi", "chip": "Chip", "dyum": "Ekran", "yil": "Yili", "partiya": "Partiya",
    "holat": "Holati", "rang": "Rangi",
    "cycles": "Battery sikli", "health": "Battery yomkosti",
    "ram": "RAM", "ssd": "SSD", "kafolat": "Kafolat", "komplekt": "Komplekt",
    "price": "Narx", "tags": "Teglar",
}
REQUIRED = ["nomi", "chip", "dyum", "yil", "holat", "rang", "cycles", "health", "ram", "ssd",
            "kafolat", "komplekt", "price", "partiya"]

COLORS = ["Space Black", "Space Gray", "Space Grey", "Rose Gold", "Sky Blue", "Midnight",
          "Starlight", "Silver", "Gold", "Blue", "Black", "White"]
COLOR_CANON = {"space grey": "Space Gray"}

RAM_SSD_RE = re.compile(r"\b(\d{1,3})\s*(?:gb)?\s*/\s*(\d{3,4}|\d\s*tb)\s*(?:gb)?\b", re.I)
BATTERY_RE = re.compile(r"(\d{2,3})\s*%\s*/\s*(\d{1,4})")                               # 94%/151sikl
BATTERY_RE2 = re.compile(r"(\d{1,4})\s*(?:sikl|cycle|цикл)\D{0,5}(\d{2,3})\s*%", re.I)  # 151sikl/94%


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=False)


# ---------- Billz qiymatlarini o'qish ----------
def num(x):
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, dict):
        x = x.get("amount") or x.get("value") or x.get("price")
    s = re.sub(r"[^\d.,\-]", "", str(x or ""))
    if s.count(",") > 1 or ("," in s and "." in s):
        s = s.replace(",", "")
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def raw_fields(p):
    """Billz tovarining qo'shimcha maydon va atributlari: [(nomi, qiymati)] (seriya raqamisiz)."""
    out = []
    for f in p.get("custom_fields") or p.get("product_custom_fields") or []:
        name = str(f.get("custom_field_name") or f.get("name") or "").strip()
        val = f.get("custom_field_value", f.get("value"))
        if isinstance(val, list):
            val = ", ".join(str(v) for v in val if v not in (None, ""))
        out.append((name, str(val if val is not None else "").strip()))
    for a in p.get("product_attributes") or p.get("attributes") or []:
        name = str(a.get("attribute_name") or a.get("name") or "").strip()
        val = a.get("attribute_value", a.get("value"))
        out.append((name, str(val if val is not None else "").strip()))
    return [(n, v) for n, v in out if n and v and not any(k in n.lower() for k in cfg.SKIP_FIELDS)]


def serial_of(p):
    """Seriya raqami (faqat xodimga ko'rsatiladi — bir xil artikulli tovarlarni ajratish uchun)."""
    for f in p.get("custom_fields") or p.get("product_custom_fields") or []:
        name = str(f.get("custom_field_name") or f.get("name") or "").lower()
        if any(k in name for k in cfg.SKIP_FIELDS):
            v = re.sub(r"[^A-Za-z0-9]", "", str(f.get("custom_field_value", f.get("value")) or ""))
            if len(v) >= 4:
                return v.upper()
    return ""


def pick_field(fields, keys, used):
    for i, (name, val) in enumerate(fields):
        if i in used:
            continue
        if any(k in name.lower() for k in keys):
            used.add(i)
            return val
    return ""


def norm_currency(c):
    c = str(c or "").strip().lower()
    if c in ("usd", "$", "dollar", "долл", "у.е.", "ye"):
        return "USD"
    if c in ("uzs", "so'm", "sum", "сум", "сўм", "som", "so‘m"):
        return "UZS"
    return c.upper() or "USD"


def norm_holat(v):
    v = str(v or "").strip()
    if not v:
        return ""
    if re.fullmatch(r"[A-Da-d][+\-]?", v):
        return v.upper() + " Category"
    m = re.fullmatch(r"([A-Da-d][+\-]?)\s*(category|kategoriya|kategoria|class|sinf)", v, re.I)
    if m:
        return m.group(1).upper() + " Category"
    m = re.fullmatch(r"(category|kategoriya|kategoria|class|sinf)\s*([A-Da-d][+\-]?)", v, re.I)
    if m:
        return m.group(2).upper() + " Category"
    return v


GRADE_KEYS = ("kategor", "category", "grade", "sinf", "daraja", "klass")


def grade_from(fields, used):
    """Holati = A/B/C/D Category. Avval kategoriya/grade maydoni, keyin «Holati».
    «B/U», «Yangi» kabi qiymatlar holat emas — topilmasa bo'sh qoladi (xodim tanlaydi)."""
    for keys in (GRADE_KEYS, cfg.BILLZ_FIELDS["holat"]):
        for i, (name, v) in enumerate(fields):
            if i in used or not any(k in name.lower() for k in keys):
                continue
            g = norm_holat(v)
            if g.endswith(" Category"):
                used.add(i)
                return g
    return ""


def find_color(text):
    low = str(text or "").lower()
    for c in COLORS:
        if re.search(r"\b" + re.escape(c.lower()) + r"\b", low):
            return COLOR_CANON.get(c.lower(), c)
    return ""


def norm_color(v):
    return find_color(v) or str(v or "").strip()


def norm_ram(v):
    m = re.search(r"\d{1,3}", str(v or ""))
    return str(int(m.group())) if m else ""


def norm_ssd(v):
    """'512', '512GB', '1TB', '1 TB', '1024' -> '512' yoki '1TB'."""
    s = str(v or "").lower().replace(" ", "")
    m = re.search(r"\d+(?:\.\d+)?", s)
    if not m:
        return ""
    n = float(m.group())
    if "tb" in s or n in (1, 2, 4, 8):
        return "%gTB" % n
    if n >= 1000:
        return "%dTB" % (int(n // 1024) or 1)
    return str(int(n))


def memory_text(ram, ssd):
    """'16/512 GB', '16GB/1TB'. Bittasi yo'q bo'lsa o'rniga ❓."""
    if not ram and not ssd:
        return ""
    ram, ssd = ram or "❓", ssd or "❓"
    if ssd.endswith("TB"):
        return "%sGB/%s" % (ram, ssd)
    return "%s/%s GB" % (ram, ssd)


def battery_text(cycles, health):
    """'175 / 86%' (sikl / yomkost). Bittasi yo'q bo'lsa o'rniga ❓."""
    if not cycles and not health:
        return ""
    return "%s / %s%%" % (cycles or "❓", health or "❓")


def battery_from(text):
    """Artikuldan: 'U-MBA-0164-94%/151sikl' -> ('151', '94')."""
    t = str(text or "")
    m = BATTERY_RE.search(t)
    if m:
        return str(int(m.group(2))), str(int(m.group(1)))
    m = BATTERY_RE2.search(t)
    if m:
        return str(int(m.group(1))), str(int(m.group(2)))
    return "", ""


# Model yili (Billz'da yil bo'lmasa): (oila, M avlodi, chip turi) -> {dyuym: yil}
YEARS = {
    ("air", 1, ""): {13: 2020},
    ("air", 2, ""): {13: 2022, 15: 2023},
    ("air", 3, ""): {13: 2024, 15: 2024},
    ("air", 4, ""): {13: 2025, 15: 2025},
    ("pro", 1, ""): {13: 2020},
    ("pro", 1, "pro"): {14: 2021, 16: 2021},
    ("pro", 1, "max"): {14: 2021, 16: 2021},
    ("pro", 2, ""): {13: 2022},
    ("pro", 2, "pro"): {14: 2023, 16: 2023},
    ("pro", 2, "max"): {14: 2023, 16: 2023},
    ("pro", 3, ""): {14: 2023},
    ("pro", 3, "pro"): {14: 2023, 16: 2023},
    ("pro", 3, "max"): {14: 2023, 16: 2023},
    ("pro", 4, ""): {14: 2024},
    ("pro", 4, "pro"): {14: 2024, 16: 2024},
    ("pro", 4, "max"): {14: 2024, 16: 2024},
    ("pro", 5, ""): {14: 2025},
}
MODEL_KEYS = ("model", "модель")
CHIP_KEYS = ("chip", "protsessor", "processor", "процессор", "cpu")
SCREEN_KEYS = ("ekran", "screen", "diagonal", "экран", "диагональ", "dyuym")
YEAR_KEYS = ("yil", "year", "год")
PARTIYA_KEYS = ("partiya", "партия", "partia", "batch")
DYUM_RE = re.compile(r"\b(1[1-7](?:[.,]\d)?)\s*(?:\"|”|″|''|-?\s*inch|dyuym|дюйм)", re.I)
DYUM_BARE_RE = re.compile(r"(?<![\d/.,%])(1[1-7](?:[.,]\d)?)(?![\d/%.,])(?!\s*(?:gb|tb|%|sikl|cycle))", re.I)


def field_by(fields, keys):
    for name, v in fields:
        if any(name.lower().strip().startswith(k) or k in name.lower() for k in keys):
            return v
    return ""


def nomi_from(sku, name, model_field):
    """Artikulda MBP -> Macbook Pro, MBA -> Macbook Air (bo'lmasa Billz «Model» maydoni yoki nomidan)."""
    s = str(sku or "").upper()
    if re.search(r"(?<![A-Z])MBP(?![A-Z])", s):
        return "Macbook Pro"
    if re.search(r"(?<![A-Z])MBA(?![A-Z])", s):
        return "Macbook Air"
    for t in (model_field, name):
        low = str(t or "").lower()
        if re.search(r"\bmbp\b|mac\s*book\s*pro", low):
            return "Macbook Pro"
        if re.search(r"\bmba\b|mac\s*book\s*air", low):
            return "Macbook Air"
    return ""


def norm_chip(v):
    """'Apple M1 Pro' -> 'M1 Pro', 'core i7' / 'i7' -> 'Intel Core i7'."""
    s = re.sub(r"(?i)\bapple\b", " ", str(v or "")).strip()
    m = re.search(r"\bM\s*([1-9])(?:\s*(pro|max|ultra))?\b", s, re.I)
    if m:
        return "M%s%s" % (m.group(1), (" " + m.group(2).capitalize()) if m.group(2) else "")
    m = re.search(r"\bcore\s*i?([3579])\b", s, re.I) or re.search(r"\bi([3579])\b", s, re.I)
    if m:
        return "Intel Core i%s" % m.group(1)
    if re.search(r"intel", s, re.I):
        return "Intel"
    return ""


def norm_dyum(v):
    """'13,3 dyuym' / '13.3"' / '14' -> '13.3' / '14'."""
    t = str(v or "")
    m = DYUM_RE.search(t) or re.search(r"(?<![\d.,])(1[1-7](?:[.,]\d)?)(?![\d])", t)
    if not m:
        return ""
    n = m.group(1).replace(",", ".")
    return n[:-2] if n.endswith(".0") else n


def dyum_in_name(name, sku):
    t = str(name or "").replace(str(sku or ""), " ") if sku else str(name or "")
    t = RAM_SSD_RE.sub(" ", t)
    t = re.sub(r"\b\d{2,3}\s*%\s*/\s*\d+", " ", t)
    m = DYUM_RE.search(t) or DYUM_BARE_RE.search(re.sub(r"\b20[0-3]\d\b", " ", t))
    return norm_dyum(m.group(0)) if m else ""


def model_year(nomi, chip, dyum):
    low = str(nomi or "").lower()
    fam = "air" if "air" in low else "pro" if "pro" in low else ""
    m = re.fullmatch(r"M([1-5])(?:\s+(Pro|Max))?", str(chip or ""))
    if not fam or not m:
        return ""
    table = YEARS.get((fam, int(m.group(1)), (m.group(2) or "").lower()))
    if not table:
        return ""
    try:
        size = int(float(dyum)) if dyum else 0
    except ValueError:
        size = 0
    if size:
        y = table.get(size)
        return str(y) if y else ""
    years = set(table.values())
    return str(years.pop()) if len(years) == 1 else ""


def partiya_code(v):
    """Billz «Partiya» qiymati -> US / UZ / KR (notanish bo'lsa — o'zi, katta harfda)."""
    s = str(v or "").upper().strip()
    if not s:
        return ""
    if re.search(r"\b(US|USA|AQSH|AMERIKA|АМЕРИКА|США)\b", s):
        return "US"
    if re.search(r"\b(UZ|UZB|O'?ZB\w*|УЗБ\w*)\b", s):
        return "UZ"
    if re.search(r"\b(KR|KOR|KOREA|KOREYA|КОРЕЯ)\b", s):
        return "KR"
    return s


def partiya_tag(code):
    for c, tag in cfg.PARTIYA:
        if c == code:
            return tag
    return ("#" + re.sub(r"[^\w]", "", code)) if code else ""


def title_text(d):
    """Sarlavha = Nomi + Chip + Ekran + Yili. Eski postlarda — saqlangan «title»."""
    if not any(k in d for k in ("nomi", "chip", "dyum", "yil")):
        return d.get("title") or "❓"
    q = "❓"
    dy = d.get("dyum")
    return " ".join([d.get("nomi") or q, d.get("chip") or q, (dy + '"') if dy else q, d.get("yil") or q])


def extract(p):
    """Billz tovarini post uchun kerakli ko'rinishga keltiradi."""
    pid = str(p.get("id") or "")
    sku = str(p.get("sku") or p.get("article") or p.get("vendor_code") or "").strip()
    name = str(p.get("name") or "").strip()
    fields = raw_fields(p)
    used = set()
    k = cfg.BILLZ_FIELDS
    holat = grade_from(fields, used)
    rang = norm_color(pick_field(fields, k["rang"], used))
    ram_f = pick_field(fields, k["ram"], used)
    ssd_f = pick_field(fields, k["ssd"], used)
    bat_f = pick_field(fields, k["battery"], used)
    cyc_f = pick_field(fields, k["cycles"], used)
    chip_f = field_by(fields, CHIP_KEYS)

    # Xotira: "16/512" ko'rinishidagi maydon, yoki alohida RAM/SSD, yoki nomdan
    ram = ssd = ""
    for v in (ssd_f, ram_f, name):
        m = RAM_SSD_RE.search(v or "")
        if m:
            ram, ssd = norm_ram(m.group(1)), norm_ssd(m.group(2))
            break
    if not ram and ram_f:
        ram = norm_ram(ram_f)
    if not ssd and ssd_f:
        ssd = norm_ssd(ssd_f)

    # Battery: avval artikuldan, keyin nomdan, keyin maydonlardan
    cycles, health = battery_from(sku)
    if not (cycles or health):
        cycles, health = battery_from(name)
    if not health and bat_f:
        h = re.search(r"\d{2,3}", bat_f)
        health = str(int(h.group())) if h else ""
    if not cycles and cyc_f:
        c = re.search(r"\d{1,4}", cyc_f)
        cycles = str(int(c.group())) if c else ""

    if not rang:
        rang = find_color(name)

    # Sarlavha: Nomi / Chip / Ekran / Yili
    nomi = nomi_from(sku, name, field_by(fields, MODEL_KEYS))
    chip = norm_chip(chip_f) or norm_chip(name)
    dyum = norm_dyum(field_by(fields, SCREEN_KEYS)) or dyum_in_name(name, sku)
    ym = re.search(r"\b(20[0-3]\d)\b", field_by(fields, YEAR_KEYS)) or re.search(r"\b(20[0-3]\d)\b", name)
    yil = ym.group(1) if ym else model_year(nomi, chip, dyum)
    partiya = partiya_code(field_by(fields, PARTIYA_KEYS))

    # Narx va qoldiq
    shop_id = settings_shop_id()
    price, old, cur = 0.0, 0.0, ""
    prices = p.get("shop_prices") or []
    if shop_id:
        prices = sorted(prices, key=lambda sp: str(sp.get("shop_id") or "") != shop_id)
    for sp in prices:
        rp = num(sp.get("retail_price"))
        if rp > 0:
            cur = sp.get("retail_currency") or sp.get("currency") or ""
            pp = num(sp.get("promo_price"))
            if 0 < pp < rp:
                price, old = pp, rp
            else:
                price = rp
            break
    qty = 0.0
    for s in p.get("shop_measurement_values") or []:
        if shop_id and str(s.get("shop_id") or "") not in ("", shop_id):
            continue
        qty += num(s.get("active_measurement_value"))

    cats = [str(c.get("name") or "") for c in (p.get("categories") or []) if isinstance(c, dict)]
    nm = re.search(r"-(\d{3,6})(?:-|$)", sku)
    serial = serial_of(p)
    return {
        "id": pid, "sku": sku, "name": name,
        "nomi": nomi, "dyum": dyum, "yil": yil, "partiya": partiya,
        "holat": holat, "rang": rang,
        "cycles": cycles, "health": health, "ram": ram, "ssd": ssd,
        "battery": battery_text(cycles, health), "xotira": memory_text(ram, ssd),
        "chip": chip,
        "price": price, "old_price": old, "currency": norm_currency(cur), "qty": qty,
        "categories": cats,
        "num": int(nm.group(1)) if nm else 0,
        "serial": serial,
        "search": (sku + " " + name + " " + serial).lower(),
    }


_SHOP = {"id": ""}


def settings_shop_id():
    return _SHOP["id"]


def set_shop_id(v):
    _SHOP["id"] = (v or "").strip()


def distinguish(x):
    """Bir xil artikulli tovarlarni ajratadigan qisqa yozuv: seriya oxiri, bo'lmasa xarakteristikalar."""
    if x.get("serial"):
        return "…" + x["serial"][-4:]
    holat = (x.get("holat") or "").replace(" Category", "")
    bits = [b for b in (holat, x.get("rang"), x.get("xotira")) if b]
    return ", ".join(bits) or "ID " + str(x.get("id", ""))[-6:]


# ---------- Qoralama ----------
def warranty_for(x):
    chip = str(x.get("chip") or "")
    if re.match(r"M\d", chip):
        return cfg.WARRANTY_M_CHIP
    if "intel" in chip.lower():
        return cfg.WARRANTY_INTEL
    return ""


def model_tag(d):
    """#macbookprom1pro — nomi + chip."""
    t = re.sub(r"[^a-z0-9]", "", (str(d.get("nomi") or "") + str(d.get("chip") or "")).lower())
    return "#" + t if t else ""


def auto_tags(d):
    return " ".join(t for t in (model_tag(d), partiya_tag(d.get("partiya") or "")) if t)


def refresh_tags(d):
    if d.get("auto_tags"):
        d["tags"] = auto_tags(d)


def new_draft(x, brand):
    d = {
        "product_id": x["id"], "sku": x["sku"], "serial": x.get("serial") or "",
        "nomi": x["nomi"], "chip": x["chip"], "dyum": x["dyum"], "yil": x["yil"], "partiya": x["partiya"],
        "holat": x["holat"], "rang": x["rang"],
        "cycles": x["cycles"], "health": x["health"], "ram": x["ram"], "ssd": x["ssd"],
        "kafolat": warranty_for(x), "komplekt": cfg.DEFAULT_KOMPLEKT,
        "price": x["price"], "old_price": x["old_price"], "currency": x["currency"],
        "installment": cfg.INSTALLMENT_DEFAULT,
        "manager": 0,
        "tags": "", "auto_tags": True,
        "brand": brand,
    }
    d["tags"] = auto_tags(d)
    return d


def missing(d):
    out = []
    for k in REQUIRED:
        v = d.get(k)
        if k == "price":
            try:
                ok = float(v or 0) > 0
            except (TypeError, ValueError):
                ok = False
            if not ok:
                out.append(LABELS[k])
        elif not str(v or "").strip():
            out.append(LABELS[k])
    return out


# ---------- Formatlash ----------
def fmt_money(v, cur):
    v = float(v or 0)
    if cur == "UZS":
        return "{:,}".format(int(round(v))).replace(",", " ") + " so'm"
    s = ("%d" % v) if v == int(v) else ("%.2f" % v).rstrip("0").rstrip(".")
    return s + "$"


def default_plan():
    return {"down": 50.0, "max": 8, "pct": 6.0}


# Do'kon botida webapp.plan() ga ulanadi (admin panelda o'zgartirilgan foizlar shu yerga ham ta'sir qiladi)
plan_fn = default_plan


def monthly(price, cur):
    """Eng uzun muddat bo'yicha oylik to'lov: (narx - oldindan) + har oy narxning pct% i, oylarga bo'linadi."""
    p = plan_fn()
    n = max(1, int(p["max"]))
    down = math.ceil(price * p["down"] / 100)
    m = ((price - down) + price * p["pct"] / 100 * n) / n
    if cur == "UZS":
        return math.ceil(m / 1000) * 1000
    return math.ceil(m)


def installment_text(d):
    price = float(d.get("price") or 0)
    if d.get("installment") and price > 0:
        p = plan_fn()
        cur = d.get("currency") or "USD"
        return cfg.TEXT["installment"].format(down="%g" % p["down"], monthly=fmt_money(monthly(price, cur), cur),
                                              months=int(p["max"]))
    return cfg.TEXT["no_installment"]


def icon(b, key):
    """Namuna postdan olingan premium ikonka (bo'lmasa oddiy emoji)."""
    plain = b.get("emoji_%s_alt" % key) or cfg.EMOJI[key]
    eid = str(b.get("emoji_" + key) or "").strip()
    if eid.isdigit():
        return '<tg-emoji emoji-id="%s">%s</tg-emoji>' % (eid, esc(plain))
    return cfg.EMOJI[key]


def strip_custom_emoji(text):
    """Premium ikonka ishlamasa — oddiy emojiga qaytarish."""
    return re.sub(r'<tg-emoji emoji-id="\d+">(.*?)</tg-emoji>', r"\1", text)


def link(url, text):
    if url:
        return '<a href="%s">%s</a>' % (html.escape(url, quote=True), esc(text))
    return esc(text)


def manager_lines(b):
    return [ln.strip() for ln in str(b.get("managers") or "").splitlines() if ln.strip()]


def manager_html(b, idx):
    lines = manager_lines(b)
    if not lines:
        return ""
    ln = lines[idx] if 0 <= idx < len(lines) else lines[0]
    parts = [p.strip() for p in ln.split("|") if p.strip()]
    return " <b>|</b> ".join(esc(p) for p in parts)


def render(d, b, sold=False):
    """Post matni (HTML). d - qoralama, b - brend sozlamalari. sold=True — narx ustidan chiziladi."""
    q = "❓"
    L = []
    if sold and cfg.TEXT.get("sold"):
        L += ["<b>%s</b>" % esc(cfg.TEXT["sold"]), ""]
    L.append("<b>%s</b>" % esc(title_text(d)))
    L.append("")
    rows = [
        ("Holati", d.get("holat")),
        ("Rangi", d.get("rang")),
        ("Battery", battery_text(d.get("cycles"), d.get("health"))),
        ("Xotira", memory_text(d.get("ram"), d.get("ssd"))),
        ("Kafolat", d.get("kafolat")),
        ("Komplektda", d.get("komplekt")),
    ]
    for label, v in rows:
        L.append("• %s: %s" % (label, esc(v or q)))
    L.append("")

    cur = d.get("currency") or "USD"
    price = float(d.get("price") or 0)
    p = fmt_money(price, cur) if price > 0 else q
    old = float(d.get("old_price") or 0)
    if sold:
        p = "<s>%s</s>" % esc(p)
    elif old > price > 0:
        p = "<s>%s</s> %s" % (esc(fmt_money(old, cur)), esc(p))
    else:
        p = esc(p)
    L.append("<b>%s</b> %s" % (esc(cfg.TEXT["price_label"]), p))
    L.append("<b>(%s)</b>" % esc(installment_text(d)))
    L.append("")

    if b.get("loc_text"):
        L.append("%s %s!" % (icon(b, "location"), link(b.get("loc_url"), b["loc_text"])))
        L.append("")
    L.append("<b>%s</b>%s<b>!</b>" % (esc(cfg.TEXT["services_prefix"]),
                                    link(b.get("services_url"), cfg.TEXT["services_word"])))
    L.append("")
    mh = manager_html(b, int(d.get("manager") or 0))
    if mh:
        L.append("%s <b>%s</b>" % (icon(b, "contact"), esc(cfg.TEXT["contact_title"])))
        L.append(mh)
        L.append("")
    if str(d.get("tags") or "").strip():
        L.append(esc(d["tags"].strip()))
    L.append("<b>%s</b>" % esc(cfg.TEXT["follow_title"]))
    L.append("%s %s <b>|</b> %s %s" % (icon(b, "telegram"), link(b.get("telegram_url"), "Telegram"),
                                       icon(b, "instagram"), link(b.get("instagram_url"), "Instagram")))
    return "\n".join(L)


def visible_len(caption_html):
    return len(html.unescape(re.sub(r"<[^>]+>", "", caption_html)))


# ---------- Qo'lda kiritilgan qiymatlarni tekshirish ----------
def parse_input(field, text, d):
    """(yangi qiymat, xato matni). '-' maydonni tozalaydi."""
    t = text.strip()
    if t == "-":
        return "", None
    if field == "price":
        low = t.lower()
        v = num(re.sub(r"\s", "", t))
        if v <= 0:
            return None, "Narxni raqam bilan yozing, masalan: 889"
        cur = d.get("currency") or "USD"
        if "$" in t or "usd" in low:
            cur = "USD"
        elif any(w in low for w in ("so'm", "som", "sum", "сум", "so‘m")):
            cur = "UZS"
        d["currency"] = cur
        d["old_price"] = 0
        return v, None
    if field == "cycles":
        m = re.fullmatch(r"(\d{1,4})\s*(sikl|cycle|цикл)?", t, re.I)
        if not m:
            return None, "Siklni raqam bilan yozing, masalan: 175"
        return str(int(m.group(1))), None
    if field == "health":
        m = re.fullmatch(r"(\d{1,3})\s*%?", t)
        if not m or not 1 <= int(m.group(1)) <= 100:
            return None, "Yomkostni foizda yozing (1–100), masalan: 86"
        return str(int(m.group(1))), None
    if field == "ram":
        m = re.fullmatch(r"(\d{1,3})\s*(gb)?", t, re.I)
        if not m or not 2 <= int(m.group(1)) <= 256:
            return None, "RAM ni GB da yozing, masalan: 16"
        return str(int(m.group(1))), None
    if field == "ssd":
        v = norm_ssd(t)
        if not v or not re.fullmatch(r"\d+(?:\.\d+)?\s*(gb|tb)?", t.strip(), re.I):
            return None, "SSD ni yozing, masalan: 512 yoki 1TB"
        return v, None
    if field == "nomi":
        low = t.lower()
        if re.search(r"\bmbp\b|pro", low):
            return "Macbook Pro", None
        if re.search(r"\bmba\b|air", low):
            return "Macbook Air", None
        return t, None
    if field == "chip":
        return norm_chip(t) or t, None
    if field == "dyum":
        v = norm_dyum(t)
        if not v:
            return None, "Ekranni dyuymda yozing, masalan: 13.3 yoki 14"
        return v, None
    if field == "yil":
        m = re.fullmatch(r"(20[0-3]\d)", t)
        if not m:
            return None, "Yilni yozing, masalan: 2020"
        return m.group(1), None
    if field == "tags":
        words = [w if w.startswith("#") else "#" + w for w in t.replace(",", " ").split()]
        return " ".join(words), None
    if field == "holat":
        return norm_holat(t), None
    if field == "rang":
        return norm_color(t), None
    return t, None
