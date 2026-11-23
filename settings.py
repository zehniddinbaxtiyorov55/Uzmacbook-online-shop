"""Admin paneldan o'zgartiriladigan matnlar va sozlamalar.

Standart qiymatlar kodda (shop_bot.py / webapp.py) turadi va DEFAULTS ga yoziladi.
Admin panelda o'zgartirilgani bazada saqlanadi va standartdan ustun turadi.
Bo'sh qoldirilsa — standart qiymat qaytadi."""
import db

DEFAULTS = {}

# (kalit, nomi, turi, izoh)
FIELDS = [
    ("welcome", "Salomlashish (/start)", "text", "Mijoz botga kirganda chiqadigan matn"),
    ("install", "💳 Muddatli to'lov", "text", "Ustama % ni o'zgartirsangiz, misoldagi raqamlarni ham yangilang"),
    ("warranty", "🛡 Garantiya", "text", ""),
    ("service", "🔧 24/7 Servis", "text", ""),
    ("cashback_how", "💰 Cashback qanday ishlaydi", "text", "Cashbackim tugmasi bosilganda"),
    ("not_bought", "💰 Cashback: hali xarid qilmagan mijoz", "text", "Raqami bazada topilmasa"),
    ("order_thanks", "Buyurtmadan keyin mijozga", "text", "Mini App orqali buyurtma bergan mijozga boradigan xabar boshi"),
    ("questions_contact", "✍️ Savollar uchun Telegram username", "str", "@ siz, masalan: sherxonjumayev"),
    ("inst_down", "Boshlang'ich to'lov, %", "num", "Masalan 50"),
    ("inst_min", "Eng kam muddat, oy", "int", "Masalan 3"),
    ("inst_max", "Eng ko'p muddat, oy", "int", "Masalan 8"),
    ("inst_pct", "Har oy ustama, % (to'liq narxdan)", "num", "Masalan 6"),
    ("usd_rate_extra", "Dollar kursiga qo'shimcha, so'm", "num", "Banklar olish kursiga qo'shiladi. 0 — qo'shilmaydi"),
    ("usd_rate", "Zaxira dollar kursi, so'm", "num",
     "Kurs bank saytlaridan o'zi olinadi. Ular ochilmay qolsagina shu kurs ishlatiladi. Bo'sh — zaxira yo'q"),
]
KINDS = {k: kind for k, _, kind, _ in FIELDS}


def get(key):
    v = db.get_setting(key)
    return v if v not in (None, "") else DEFAULTS.get(key, "")


def num(key):
    try:
        return float(str(get(key)).replace(",", "."))
    except ValueError:
        return float(DEFAULTS.get(key) or 0)


def clean(key, value):
    """Admin yuborgan qiymatni tekshiradi. Bo'sh -> standartga qaytarish. Xato bo'lsa ValueError."""
    kind = KINDS.get(key)
    if kind is None:
        raise ValueError("noma'lum sozlama: %s" % key)
    value = "" if value is None else str(value).strip()
    if value == "":
        return ""
    if kind == "text":
        if len(value) > 4000:
            raise ValueError("%s: matn 4000 belgidan oshmasin (Telegram cheklovi)" % key)
        return value
    if kind == "str":
        return value.lstrip("@")[:64]
    try:
        f = float(value.replace(",", "."))
    except ValueError:
        raise ValueError("%s: raqam kiriting" % key)
    if kind == "int":
        if f != int(f) or not 1 <= f <= 36:
            raise ValueError("%s: 1 dan 36 gacha butun son" % key)
        return str(int(f))
    if key in ("inst_down", "inst_pct") and not 0 <= f <= 100:
        raise ValueError("%s: 0 dan 100 gacha" % key)
    if key == "usd_rate" and not 1000 <= f <= 100000:
        raise ValueError("Zaxira kurs: so'mda yozing, masalan 12040")
    return ("%g" % f)


def all_for_admin():
    out = []
    for key, label, kind, hint in FIELDS:
        saved = db.get_setting(key)
        out.append({"key": key, "label": label, "kind": kind, "hint": hint,
                    "value": saved if saved not in (None, "") else "",
                    "default": str(DEFAULTS.get(key, "")),
                    "custom": saved not in (None, "")})
    return out


def save(values):
    """{key: value} — hammasini tekshirib, keyin saqlaydi. Muddatlar mantiqiyligini ham tekshiradi."""
    cleaned = {k: clean(k, v) for k, v in values.items()}

    def effective(key):  # saqlangandan keyingi qiymat
        if key in cleaned:
            return float(cleaned[key] or DEFAULTS.get(key) or 0)
        return num(key)
    if effective("inst_min") > effective("inst_max"):
        raise ValueError("Eng kam muddat eng ko'p muddatdan katta bo'lmasin")
    for k, v in cleaned.items():
        db.set_setting(k, v)
    return cleaned
