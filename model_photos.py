"""Model rasmlari: bir xil model + chip + ekran + rangdagi tovarlar uchun bitta rasm to'plami.

Billz'dagi xarakteristikalar (Model, Chip, Ekran, Rang) bo'yicha tovar guruhga tushadi,
masalan "MacBook Pro 14″ · M1 Pro · Space Gray". Admin paneldan guruhga rasm yuklanadi va
shu guruhdagi hamma tovarga (keyin keladiganlariga ham) avtomatik qo'yiladi.

Rasm tartibi Mini App'da: Billz'dagi tovarning o'z rasmi > model rasmi > Apple namunaviy rasmi.
Fayllar: <DB papkasi>/model_photos/<kalit>/<vaqt><tasodifiy>.jpg (+ label.txt — guruh nomi)."""
import os, re, threading, time

import db
from stock_photos import ACCESSORY, _size

DIR = os.path.join(os.path.dirname(db.PATH), "model_photos")
MAX = 8                       # bitta guruhga ko'pi bilan nechta rasm
MAX_BYTES = 8 * 1024 * 1024   # bitta rasm hajmi
KEY_RX = re.compile(r"^[a-z0-9][a-z0-9-]{0,90}$")
FILE_RX = re.compile(r"^\d{13}[0-9a-f]{4}\.(?:jpg|png|webp)$")

_lock = threading.Lock()
_index = {}   # kalit -> [fayl, ...] (tartib bo'yicha, birinchisi — asosiy)
_labels = {}  # kalit -> guruh nomi

# (kalit, nomi, regex) — tartib muhim: "rose gold" "gold" dan, "space black" "black" dan oldin
COLORS = [
    ("space-black", "Space Black", r"space\s*black"),
    ("space-gray", "Space Gray", r"space\s*gr[ae]y|kulrang|сер(ый|ая)|gr[ae]y"),
    ("silver", "Silver", r"silver|kumush(rang)?|серебр\w*"),
    ("rose-gold", "Rose Gold", r"rose\s*gold"),
    ("gold", "Gold", r"gold|oltin(rang)?|золот\w*"),
    ("midnight", "Midnight", r"midnight|т[её]мная\s*ночь"),
    ("starlight", "Starlight", r"starlight|сияющ\w*(\s*звезда)?"),
    ("sky-blue", "Sky Blue", r"sky\s*blue"),
    ("blue", "Blue", r"blue|ko'?k|син\w*"),
    ("black", "Black", r"black|qora|ч[её]рн\w*"),
    ("white", "White", r"white|oq|бел\w*"),
]
COLOR_NAMES = {k: n for k, n, _ in COLORS}

DETAIL_KEYS = {
    "model": ("model", "модель"),
    "chip": ("chip", "protsessor", "processor", "процессор", "cpu"),
    "screen": ("ekran", "screen", "diagonal", "экран", "диагональ"),
    "color": ("rang", "color", "colour", "цвет"),
}


def slug(s):
    s = re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")
    return s[:90].strip("-")


def _detail(details, kind):
    names = DETAIL_KEYS[kind]
    for k, v in details:
        kl = str(k).lower().strip()
        if any(kl == n or kl.startswith(n) for n in names):
            return str(v).strip()
    return ""


def color_of(details, name=""):
    """(kalit, nomi). Billz'dagi "Rang" maydoni to'liq tanish rang bo'lsa — standart nom
    ("Kulrang" -> Space Gray), notanish bo'lsa o'zi ("Sierra Blue"). Maydon bo'lmasa — nomidan."""
    raw = _detail(details, "color").strip()
    t = re.sub(r"\s+", " ", raw.lower())
    if t:
        for key, label, rx in COLORS:
            if re.fullmatch(rx, t):
                return key, label
        return slug(raw), raw
    n = (name or "").lower()
    for key, label, rx in COLORS:
        if re.search(r"(?<![\w'])(?:%s)(?!\w)" % rx, n):
            return key, label
    return "", ""


def _chip(text, name):
    m = re.search(r"\bm\s?([1-5])(?:\s*(pro|max|ultra))?\b", text)
    if m:
        return "M%s%s" % (m.group(1), (" " + m.group(2).title()) if m.group(2) else "")
    m = re.search(r"\b(?:core\s*)?i([3579])\b", text)
    if m:
        y = re.search(r"\b(20[12]\d)\b", name)  # yilni faqat nomidan (xarakteristikada sotib olingan sana bor)
        return "Intel i%s%s" % (m.group(1), (" " + y.group(1)) if y else "")
    return ""


def key_of(name, details, category=""):
    """Tovar qaysi guruhga tushadi: (kalit, nomi). Guruhlab bo'lmasa ("", "")."""
    n = (name or "").lower().replace("”", '"')
    c = (category or "").lower()
    model = _detail(details, "model").lower()
    ckey, cname = color_of(details, n)
    accessory = ACCESSORY.search(n) or ACCESSORY.search(c)
    is_mac = not accessory and ("macbook" in model or "macbook" in c
                                or re.search(r"\b(mba|mbp|macbook)\b", n))
    if is_mac:
        if "air" in model or (not model and re.search(r"\bair\b|\bmba\b", n)):
            family = "MacBook Air"
        elif "pro" in model or (not model and re.search(r"\bmbp\b|\bpro\b", n)):
            family = "MacBook Pro"
        elif re.search(r"\bair\b|\bmba\b", n):
            family = "MacBook Air"
        elif re.search(r"\bmbp\b|\bpro\b", n):
            family = "MacBook Pro"
        else:
            family = "MacBook"
        chip = _chip((_detail(details, "chip") + " " + n).lower(), n)
        screen = _detail(details, "screen").lower().replace("”", '"')
        size = _size(n) or _size(screen + ('"' if screen and '"' not in screen else ""))
        if not (chip or size):
            return "", ""  # ma'lumot yetarli emas — noto'g'ri guruhga tushmasin
        parts = [family + (" %s″" % size if size else ""), chip, cname or "rang ko'rsatilmagan"]
        label = " · ".join(p for p in parts if p)
        key = slug("-".join(p for p in (family, size, chip, ckey) if p))
        return key, label
    # MacBook bo'lmagan tovarlar: nomidan xotira/konfiguratsiyani olib tashlab + rang
    base = re.sub(r"\b\d+\s*/\s*\d+\b|\b\d+\s*(?:gb|tb|гб|тб)\b|\(.*?\)", " ", (name or ""), flags=re.I)
    base = re.sub(r"\s+", " ", base).strip(" -·,")
    if not base:
        return "", ""
    label = base + (" · " + cname if cname else "")
    key = slug(base + ("-" + ckey if ckey else ""))
    return (key, label) if key else ("", "")


# ---------- fayllar ----------
def _gdir(key):
    return os.path.join(DIR, key)


def _sniff(data):
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return ""


def load():
    """Diskdagi rasmlarni xotiraga o'qiydi (ishga tushganda bir marta)."""
    idx, labels = {}, {}
    if os.path.isdir(DIR):
        for k in os.listdir(DIR):
            p = _gdir(k)
            if not (KEY_RX.match(k) and os.path.isdir(p)):
                continue
            files = sorted(f for f in os.listdir(p) if FILE_RX.match(f))
            if files:
                idx[k] = files
            try:
                with open(os.path.join(p, "label.txt"), encoding="utf-8") as f:
                    labels[k] = f.read().strip()[:200]
            except OSError:
                pass
    with _lock:
        _index.clear()
        _index.update(idx)
        _labels.clear()
        _labels.update(labels)


def files(key):
    return list(_index.get(key) or [])


def keys():
    return list(_index.keys())


def label(key):
    return _labels.get(key, "")


def urls(key, base=""):
    """Rasm manzillari. base="" — nisbiy (Mini App uchun), aks holda to'liq manzil."""
    return [base + "mp/%s/%s" % (key, f) for f in _index.get(key) or []]


def path(key, name):
    if not (KEY_RX.match(key or "") and FILE_RX.match(name or "")):
        return ""
    p = os.path.join(_gdir(key), name)
    return p if os.path.isfile(p) else ""


def _new_name(ext, ms=None):
    ms = int(time.time() * 1000) if ms is None else ms
    return "%013d%s.%s" % (max(0, ms), os.urandom(2).hex(), ext)


def save(key, data, group_label=""):
    """Rasmni guruhga qo'shadi. Xato bo'lsa ValueError (o'zbekcha matn bilan)."""
    if not KEY_RX.match(key or ""):
        raise ValueError("Noto'g'ri guruh")
    if not data:
        raise ValueError("Rasm bo'sh")
    if len(data) > MAX_BYTES:
        raise ValueError("Rasm juda katta (8 MB gacha)")
    ext = _sniff(data)
    if not ext:
        raise ValueError("Rasm JPG, PNG yoki WEBP bo'lsin")
    with _lock:
        cur = list(_index.get(key) or [])
        if len(cur) >= MAX:
            raise ValueError("Bitta guruhga %s tadan ko'p rasm qo'yib bo'lmaydi" % MAX)
        os.makedirs(_gdir(key), exist_ok=True)
        name = _new_name(ext)
        while name in cur:
            name = _new_name(ext)
        tmp = os.path.join(_gdir(key), "." + name + ".tmp")
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, os.path.join(_gdir(key), name))
        _index[key] = sorted(cur + [name])
        if group_label:
            group_label = group_label.strip()[:200]
            if _labels.get(key) != group_label:
                with open(os.path.join(_gdir(key), "label.txt"), "w", encoding="utf-8") as f:
                    f.write(group_label)
                _labels[key] = group_label
    return name


def delete(key, name):
    p = path(key, name)
    if not p:
        raise ValueError("Rasm topilmadi")
    with _lock:
        os.remove(p)
        left = [f for f in _index.get(key) or [] if f != name]
        if left:
            _index[key] = left
        else:
            _index.pop(key, None)


def make_main(key, name):
    """Rasmni birinchi (asosiy) qiladi — Mini App kartochkasida shu ko'rinadi."""
    p = path(key, name)
    if not p:
        raise ValueError("Rasm topilmadi")
    with _lock:
        cur = list(_index.get(key) or [])
        if not cur or cur[0] == name:
            return name
        first_ms = int(cur[0][:13])
        new = _new_name(name.rsplit(".", 1)[1], first_ms - 1)
        os.replace(p, os.path.join(_gdir(key), new))
        _index[key] = sorted([f for f in cur if f != name] + [new])
    return new


load()
