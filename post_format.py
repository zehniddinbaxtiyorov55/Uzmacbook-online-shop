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
    "title": "Sarlavha", "holat": "Holati", "rang": "Rangi",
    "cycles": "Battery sikli", "health": "Battery yomkosti",
    "ram": "RAM", "ssd": "SSD", "kafolat": "Kafolat", "komplekt": "Komplekt",
    "price": "Narx", "tags": "Teglar",
}
REQUIRED = ["title", "holat", "rang", "cycles", "health", "ram", "ssd", "kafolat", "komplekt", "price"]

COLORS = ["Space Black", "Space Gray", "Space Grey", "Rose Gold", "Sky Blue", "Midnight",
          "Starlight", "Silver", "Gold", "Blue", "Black", "White"]
COLOR_CANON = {"space grey": "Space Gray"}

RAM_SSD_RE = re.compile(r"\b(\d{1,3})\s*(?:gb)?\s*/\s*(\d{3,4}|\d\s*tb)\s*(?:gb)?\b", re.I)
BATTERY_RE = re.compile(r"(\d{2,3})\s*%\s*/\s*(\d{1,4})")                               # 94%/151sikl
BATTERY_RE2 = re.compile(r"(\d{1,4})\s*(?:sikl|cycle|цикл)\D{0,5}(\d{2,3})\s*%", re.I)  # 151sikl/94%
M_CHIP_RE = re.compile(r"\bM[1-9]\b", re.I)
INTEL_RE = re.compile(r"intel|\bi[3579]\b|core\s*i|\bi[3579]-", re.I)
REGION_RE = re.compile(r"(?<![A-Z])([A-Z]{1,3})\s*/\s*A\b")   # MKGR3LL/A -> LL


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


def clean_title(name, sku):
    t = str(name or "")
    if sku:
        t = t.replace(sku, " ")
    t = RAM_SSD_RE.sub(" ", t)
    for c in COLORS:
        t = re.sub(r"\b" + re.escape(c) + r"\b", " ", t, flags=re.I)
    t = re.sub(r"\b\d{2,3}\s*%\s*/\s*\d+\s*(sikl|cycle)?", " ", t, flags=re.I)
    t = re.sub(r"\(\s*\)", " ", t)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip(" -|,/·")


def model_tag(title):
    words = []
    for w in re.split(r"\s+", str(title or "")):
        w2 = re.sub(r"[^\w]", "", w)
        if not w2 or '"' in w or "”" in w or "″" in w or "/" in w:
            continue
        if w2.isdigit():          # 14", 2021 va h.k. tushib qoladi
            continue
        if re.fullmatch(r"\d+(gb|tb|inch|dyum)", w2, re.I):
            continue
        words.append(w2.lower())
    return ("#" + "".join(words)) if words else ""


def extract(p):
    """Billz tovarini post uchun kerakli ko'rinishga keltiradi."""
    pid = str(p.get("id") or "")
    sku = str(p.get("sku") or p.get("article") or p.get("vendor_code") or "").strip()
    name = str(p.get("name") or "").strip()
    fields = raw_fields(p)
    used = set()
    k = cfg.BILLZ_FIELDS
    holat = norm_holat(pick_field(fields, k["holat"], used))
    rang = norm_color(pick_field(fields, k["rang"], used))
    ram_f = pick_field(fields, k["ram"], used)
    ssd_f = pick_field(fields, k["ssd"], used)
    bat_f = pick_field(fields, k["battery"], used)
    cyc_f = pick_field(fields, k["cycles"], used)
    chip = pick_field(fields, k["chip"], used)

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

    all_text = " ".join([name, chip] + [v for _, v in fields])
    if M_CHIP_RE.search(name + " " + chip):
        chip_kind = "M"
    elif INTEL_RE.search(name + " " + chip):
        chip_kind = "INTEL"
    else:
        chip_kind = ""
    m = REGION_RE.search(all_text)
    region = "#" + m.group(1) + "A" if m else ""

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
        "title": clean_title(name, sku) or name,
        "holat": holat, "rang": rang,
        "cycles": cycles, "health": health, "ram": ram, "ssd": ssd,
        "battery": battery_text(cycles, health), "xotira": memory_text(ram, ssd),
        "chip": chip_kind, "region": region,
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
        return "…" + x["serial"][-5:]
    holat = (x.get("holat") or "").replace(" Category", "")
    bits = [b for b in (holat, x.get("rang"), x.get("xotira")) if b]
    return ", ".join(bits) or "ID " + str(x.get("id", ""))[-6:]


# ---------- Qoralama ----------
def warranty_for(x):
    if x.get("chip") == "M":
        return cfg.WARRANTY_M_CHIP
    if x.get("chip") == "INTEL":
        return cfg.WARRANTY_INTEL
    return ""


def auto_tags(title, region):
    return " ".join(t for t in (model_tag(title), region) if t)


def new_draft(x, brand):
    return {
        "product_id": x["id"], "sku": x["sku"], "serial": x.get("serial") or "",
        "title": x["title"], "holat": x["holat"], "rang": x["rang"],
        "cycles": x["cycles"], "health": x["health"], "ram": x["ram"], "ssd": x["ssd"],
        "kafolat": warranty_for(x), "komplekt": cfg.DEFAULT_KOMPLEKT,
        "price": x["price"], "old_price": x["old_price"], "currency": x["currency"],
        "installment": cfg.INSTALLMENT_DEFAULT,
        "manager": 0,
        "region": x.get("region") or "",
        "tags": auto_tags(x["title"], x.get("region")), "auto_tags": True,
        "brand": brand,
    }


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
    L.append("<b>%s</b>" % esc(d.get("title") or q))
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

    E = cfg.EMOJI
    if b.get("loc_text"):
        L.append("%s %s!" % (E["location"], link(b.get("loc_url"), b["loc_text"])))
        L.append("")
    L.append("<b>%s</b>%s<b>!</b>" % (esc(cfg.TEXT["services_prefix"]),
                                    link(b.get("services_url"), cfg.TEXT["services_word"])))
    L.append("")
    mh = manager_html(b, int(d.get("manager") or 0))
    if mh:
        L.append("%s <b>%s</b>" % (E["contact"], esc(cfg.TEXT["contact_title"])))
        L.append(mh)
        L.append("")
    if str(d.get("tags") or "").strip():
        L.append(esc(d["tags"].strip()))
    L.append("<b>%s</b>" % esc(cfg.TEXT["follow_title"]))
    L.append("%s %s <b>|</b> %s %s" % (E["telegram"], link(b.get("telegram_url"), "Telegram"),
                                       E["instagram"], link(b.get("instagram_url"), "Instagram")))
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
    if field == "tags":
        words = [w if w.startswith("#") else "#" + w for w in t.replace(",", " ").split()]
        return " ".join(words), None
    if field == "holat":
        return norm_holat(t), None
    if field == "rang":
        return norm_color(t), None
    return t, None
