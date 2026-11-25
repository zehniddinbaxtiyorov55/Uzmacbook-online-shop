"""«📢 Kanalga post» bo'limi (faqat admin va ruxsat berilgan xodimlar uchun).

Rasm yuboriladi -> Billz artikuli tanlanadi -> post kanaldagi namunadagidek yig'iladi ->
tekshirib, tugmalar bilan o'zgartiriladi -> kanalga joylanadi.
Tovar Billz'da sotilsa, kanaldagi postga o'zi "🔴 SOTILDI" qo'yiladi, narx o'zgarsa yangilanadi.

Admin (POST_ADMINS / post_config.ADMINS) "👥 Ruxsatlar" orqali boshqalarga ruxsat beradi.
Mijozlar bu bo'limni ko'rmaydi."""
import asyncio
import json
import logging
import os
import re
import time

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.types import (CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto,
                           InputMediaVideo, LinkPreviewOptions, Message)

import db
import post_config as cfg
import post_format as pf
from post_format import esc

log = logging.getLogger("POST")
router = Router(name="post")
ctx = {"bot": None, "fetch": None}
H = ParseMode.HTML
NO_PREVIEW = LinkPreviewOptions(is_disabled=True)
PAGE = 8
MAX_MEDIA = 10
HOME_BTN = "📢 Kanalga post"

BRAND_FIELDS = [
    ("channel", "📢 Kanal"),
    ("loc_text", "📍 Manzil matni"),
    ("loc_url", "🗺 Manzil linki"),
    ("services_url", "🛠 Xizmatlar linki"),
    ("telegram_url", "✈️ Telegram linki"),
    ("instagram_url", "📷 Instagram linki"),
    ("managers", "👤 Menejerlar"),
]
SETTING_HINTS = {
    "channel": "Kanal @username yoki -100... ID sini yuboring.\nBot o'sha kanalda admin bo'lishi shart "
               "(post joylash va tahrirlash huquqi bilan).",
    "loc_text": "Postdagi manzil matnini yuboring, masalan: A-34 Hovli tomondan kirishda",
    "loc_url": "Manzil (xarita) linkini yuboring.",
    "services_url": "«Xizmatlar» so'ziga qo'yiladigan linkni yuboring.",
    "telegram_url": "Telegram kanal linkini yuboring, masalan: https://t.me/uzmacbook",
    "instagram_url": "Instagram linkini yuboring.",
    "managers": "Menejerlarni yuboring, har qatorda bittasi:\n910130770 | @sherxonjumayev",
}
PROMPTS = {
    "title": "✍️ Model nomini yozing, masalan: Macbook Pro M1 Pro 14\" 2021",
    "battery": "✍️ Battery: sikl / foiz, masalan: 175 / 86%",
    "xotira": "✍️ Xotira: RAM/SSD, masalan: 16/512",
    "price": "✍️ Narxni yozing, masalan: 889  (so'mda bo'lsa: 8 900 000 so'm)",
    "tags": "✍️ Teglarni yozing, masalan: #macbookprom1pro #LLA",
    "holat": "✍️ Holatini yozing, masalan: B Category",
    "rang": "✍️ Rangini yozing, masalan: Silver",
    "kafolat": "✍️ Kafolat muddatini yozing, masalan: 90 kun",
    "komplekt": "✍️ Komplektni yozing, masalan: Zaryadka!",
}
CHOICE_FIELDS = ("holat", "rang", "kafolat", "komplekt")


# ---------- Ruxsatlar ----------
def admin_tokens():
    raw = os.environ.get("POST_ADMINS") or cfg.ADMINS
    ids, names = set(), set()
    for t in re.split(r"[\s,;]+", raw or ""):
        t = t.strip().lstrip("@")
        if not t:
            continue
        if t.lstrip("-").isdigit():
            ids.add(int(t))
        else:
            names.add(t.lower())
    return ids, names


def is_admin(u):
    if not u:
        return False
    ids, names = admin_tokens()
    return u.id in ids or (u.username or "").lower() in names


def acl():
    try:
        v = json.loads(db.get_setting("post.allowed") or "[]")
        return v if isinstance(v, list) else []
    except ValueError:
        return []


def save_acl(lst):
    db.set_setting("post.allowed", json.dumps(lst, ensure_ascii=False) if lst else "")


def is_allowed(u):
    """Admin yoki admin ruxsat bergan xodim."""
    if not u or getattr(u, "is_bot", False):
        return False
    if is_admin(u):
        return True
    uname = (u.username or "").lower()
    lst = acl()
    for e in lst:
        if e.get("id"):
            if e["id"] == u.id:
                return True
        elif uname and e.get("username") == uname:
            e["id"] = u.id            # @username bilan qo'shilgan edi — endi ID ni eslab qolamiz
            save_acl(lst)
            return True
    return False


def admin_ids():
    ids, names = admin_tokens()
    out = set(ids)
    for n in names:
        r = db.user_by_username(n)
        if r:
            out.add(r["id"])
    return out


def entry_name(e):
    parts = [e.get("name") or ""]
    if e.get("username"):
        parts.append("@" + e["username"])
    elif e.get("id"):
        parts.append("ID %s" % e["id"])
    return " ".join(p for p in parts if p).strip() or "?"


def menu_row(user):
    """Asosiy menyuga qo'shiladigan tugma (faqat ruxsati borlarga)."""
    if user is not None and is_allowed(user):
        return [InlineKeyboardButton(text=HOME_BTN, callback_data="pm:home")]
    return None


# ---------- Holat ----------
class Draft:
    def __init__(self):
        self.media = []        # [(message_id, "photo"|"video", file_id)]
        self.d = None
        self.query = ""
        self.page = 0
        self.list_ids = []
        self.list_msg = None
        self.awaiting = None   # qo'lda yozilayotgan maydon yoki "media"
        self.prompt = None
        self.opts = []
        self.preview = []
        self.panel = None
        self.busy = False


drafts = {}
album_tasks = {}
setting_wait = {}   # user_id -> (brand, field)
grant_wait = set()  # ruxsat beriladigan odamni kutayotgan adminlar


def reset(uid):
    """Foydalanuvchi asosiy menyuga qaytsa — post rejimidan chiqadi."""
    drafts.pop(uid, None)
    setting_wait.pop(uid, None)
    grant_wait.discard(uid)
    t = album_tasks.pop(uid, None)
    if t:
        t.cancel()


def in_post_mode(uid):
    return uid in drafts or uid in setting_wait or uid in grant_wait


# ---------- Billz (o'z keshi: artikul va maydonlar kerak) ----------
class Stock:
    def __init__(self):
        self.items, self.raw = [], {}
        self.loaded_at = 0.0
        self.last_count = 0
        self.lock = asyncio.Lock()

    async def products(self, force=False):
        if not force and self.items and time.time() - self.loaded_at < 300:
            return self.items
        async with self.lock:
            if not force and self.items and time.time() - self.loaded_at < 300:
                return self.items
            raw = await ctx["fetch"](False, 30)
            items, by_id = [], {}
            cat = (cfg.CATEGORY_FILTER or "").lower().strip()
            for p in raw:
                try:
                    x = pf.extract(p)
                except Exception:
                    log.exception("POST: tovarni o'qib bo'lmadi: %s", p.get("name"))
                    continue
                if not x["id"] or x["qty"] <= 0:
                    continue
                if cat and not any(cat in c.lower() for c in x["categories"]):
                    continue
                items.append(x)
                by_id[x["id"]] = p
            self.items, self.raw = items, by_id
            self.loaded_at = time.time()
            self.last_count = len(items)
            return items

    def find(self, pid):
        return next((x for x in self.items if x["id"] == pid), None)

    def values(self, field):
        seen = []
        for x in self.items:
            v = (x.get(field) or "").strip()
            if v and v not in seen:
                seen.append(v)
        return seen


stock = Stock()


# ---------- Yordamchilar ----------
def bot():
    return ctx["bot"]


def kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=c) for t, c in row] for row in rows])


def pairs(items, n=2):
    return [items[i:i + n] for i in range(0, len(items), n)]


def brand_keys():
    return list(cfg.BRANDS.keys())


def brand_cfg(key):
    base = dict(cfg.BRANDS.get(key) or next(iter(cfg.BRANDS.values())))
    for f, _ in BRAND_FIELDS:
        v = db.get_setting("post.%s.%s" % (key, f))
        if v is not None:
            base[f] = v.strip()
    return base


async def send(chat_id, text, markup=None):
    return await bot().send_message(chat_id, text, parse_mode=H, reply_markup=markup,
                                    link_preview_options=NO_PREVIEW)


async def safe_delete(chat_id, msg_id):
    if not msg_id:
        return
    try:
        await bot().delete_message(chat_id, msg_id)
    except Exception:
        pass


async def send_or_edit(chat_id, msg_id, text, markup=None):
    if msg_id:
        try:
            await bot().edit_message_text(text=text, chat_id=chat_id, message_id=msg_id, parse_mode=H,
                                          reply_markup=markup, link_preview_options=NO_PREVIEW)
            return msg_id
        except TelegramBadRequest as e:
            if "not modified" in str(e):
                return msg_id
    m = await send(chat_id, text, markup)
    return m.message_id


async def send_post(chat_id, media, caption):
    """Rasm(lar) + post matni. Qaytaradi: (xabar id lari, chat id)."""
    media = [(k, f) for _, k, f in media][:MAX_MEDIA]
    if len(media) == 1:
        kind, fid = media[0]
        send_fn = bot().send_video if kind == "video" else bot().send_photo
        m = await send_fn(chat_id, fid, caption=caption, parse_mode=H)
        return [m.message_id], m.chat.id
    group = []
    for i, (kind, fid) in enumerate(media):
        extra = {"caption": caption, "parse_mode": H} if i == 0 else {}
        group.append(InputMediaVideo(media=fid, **extra) if kind == "video" else InputMediaPhoto(media=fid, **extra))
    msgs = await bot().send_media_group(chat_id, group)
    return [x.message_id for x in msgs], msgs[0].chat.id


async def post_link(chat_id, msg_id):
    try:
        chat = await bot().get_chat(chat_id)
        if chat.username:
            return "https://t.me/%s/%s" % (chat.username, msg_id)
    except Exception:
        pass
    s = str(chat_id)
    return "https://t.me/c/%s/%s" % (s[4:], msg_id) if s.startswith("-100") else ""


async def notify(text, extra_ids=()):
    for uid in admin_ids() | {i for i in extra_ids if i}:
        try:
            await send(uid, text)
        except Exception:
            pass


def render(d, b=None, sold=False):
    return pf.render(d, b or brand_cfg(d["brand"]), sold=sold)


# ---------- Bosh sahifa ----------
def home_text():
    return ("📢 <b>Kanalga post</b>\n\n"
            "Rasmlarni yuboring (1–10 ta, albom qilib) yoki «🆕 Yangi post» ni bosing — "
            "bot Billz artikuli bo'yicha postni o'zi yig'adi.\n"
            "Tovar sotilsa, kanaldagi postga «🔴 SOTILDI» o'zi qo'yiladi.")


def home_kb(user):
    rows = [[("🆕 Yangi post", "pm:new"), ("📋 Postlar", "pm:posts")]]
    if is_admin(user):
        rows.append([("⚙️ Sozlamalar", "pm:set"), ("👥 Ruxsatlar", "pm:acl")])
    rows.append([("⬅️ Menyu", "menu")])
    return kb(rows)


# ---------- Ro'yxat: qaysi model? ----------
async def show_list(chat_id, uid, header="", edit=None, typed=False):
    dr = drafts.get(uid)
    if not dr:
        return
    try:
        items = await stock.products()
    except Exception as e:
        log.exception("POST: Billz xatosi")
        dr.list_msg = await send_or_edit(
            chat_id, edit, "⚠️ Billz bilan bog'lanib bo'lmadi:\n<code>%s</code>" % esc(str(e)[:300]),
            kb([[("🔁 Qayta urinish", "pm:ls:retry")], [("❌ Bekor", "pm:x")]]))
        return
    q = dr.query.lower().strip()
    found = [x for x in items if q in x["search"]] if q else list(items)
    if typed and q and len(found) == 1:
        return await choose(chat_id, uid, found[0])
    posted = db.posted_product_ids()
    found.sort(key=lambda x: (x["id"] in posted, -x["num"], x["sku"]))
    pages = max(1, -(-len(found) // PAGE))
    dr.page = min(max(dr.page, 0), pages - 1)
    chunk = found[dr.page * PAGE:(dr.page + 1) * PAGE]
    dr.list_ids = [x["id"] for x in chunk]

    lines = [header] if header else []
    lines.append("<b>Qaysi model?</b> Artikulning bir qismini yozing (masalan <code>0164</code> "
                 "yoki <code>MBA</code>) yoki ro'yxatdan tanlang 👇")
    if q:
        lines.append("🔎 «%s» bo'yicha: %s ta" % (esc(dr.query), len(found)))
    if not found:
        lines.append("Hech narsa topilmadi. Boshqacha yozib ko'ring.")
    if any(x["id"] in posted for x in chunk):
        lines.append("✅ — kanalga avval joylangan")
    rows = []
    for i, x in enumerate(chunk):
        label = ("✅ " if x["id"] in posted else "") + (x["sku"] or x["name"])[:42]
        rows.append([(label + " · " + pf.fmt_money(x["price"], x["currency"]), "pm:p:%d" % i)])
    nav = []
    if dr.page > 0:
        nav.append(("◀️", "pm:pg:%d" % (dr.page - 1)))
    if pages > 1:
        nav.append(("%d/%d" % (dr.page + 1, pages), "pm:noop"))
    if dr.page < pages - 1:
        nav.append(("▶️", "pm:pg:%d" % (dr.page + 1)))
    if nav:
        rows.append(nav)
    last = [("🔄 Yangilash", "pm:ls:refresh")]
    if q:
        last.append(("🔎 Hammasi", "pm:ls:all"))
    last.append(("❌ Bekor", "pm:x"))
    rows.append(last)
    dr.list_msg = await send_or_edit(chat_id, edit, "\n".join(lines), kb(rows))


async def choose(chat_id, uid, x, list_msg=None):
    dr = drafts.get(uid)
    if not dr:
        return
    dr.d = pf.new_draft(x, brand_keys()[0])
    note = "✅ Tanlandi: <code>%s</code>" % esc(x["sku"] or x["name"])
    if list_msg or dr.list_msg:
        await send_or_edit(chat_id, list_msg or dr.list_msg, note)
    else:
        await send(chat_id, note)
    dr.list_msg = None
    if dr.media:
        await show_preview(chat_id, uid)
    else:
        await send(chat_id, "📸 Endi shu model rasmlarini yuboring (1–10 ta, albom qilib).")


# ---------- Ko'rinish va boshqaruv paneli ----------
def panel_text(dr):
    d = dr.d
    lines = ["📝 <b>Post tayyor — tekshiring</b>",
             "Artikul: <code>%s</code>" % esc(d.get("sku") or "—")]
    x = stock.find(d["product_id"])
    if x:
        lines.append("Billz: %s · qoldiq %s" % (pf.fmt_money(x["price"], x["currency"]), int(x["qty"])))
    if d["product_id"] in db.posted_product_ids():
        lines.append("ℹ️ Bu tovar kanalga avval joylangan")
    miss = pf.missing(d)
    lines.append("⚠️ To'ldiring: " + ", ".join(miss) if miss else "✅ Hammasi to'ldirilgan")
    n = pf.visible_len(render(d))
    if n > 1024:
        lines.append("⚠️ Matn juda uzun (%s/1024) — Telegram qabul qilmaydi" % n)
    if not dr.media:
        lines.append("🖼 Rasm yo'q — rasmlarni yuboring")
    return "\n".join(lines)


def panel_kb(dr):
    d = dr.d
    rows = [
        [("✏️ Nomi", "pm:e:title"), ("🏷 Holati", "pm:e:holat"), ("🎨 Rangi", "pm:e:rang")],
        [("🔋 Battery", "pm:e:battery"), ("💾 Xotira", "pm:e:xotira"), ("🛡 Kafolat", "pm:e:kafolat")],
        [("📦 Komplekt", "pm:e:komplekt"), ("💵 Narx", "pm:e:price"),
         ("💳 Muddatli: " + ("✅" if d.get("installment") else "❌"), "pm:t:inst")],
        [("👤 Menejer", "pm:e:manager"), ("#️⃣ Teglar", "pm:e:tags"), ("🖼 Rasmlar", "pm:e:media")],
    ]
    if len(brand_keys()) > 1:
        rows.append([("🏪 Brend: " + brand_cfg(d["brand"])["name"], "pm:t:brand")])
    rows.append([("📢 Kanalga joylash", "pm:pub")])
    rows.append([("📋 Matnni olish", "pm:copy"), ("❌ Bekor", "pm:x")])
    return kb(rows)


async def show_preview(chat_id, uid):
    dr = drafts.get(uid)
    if not dr or not dr.d:
        return
    for mid in dr.preview:
        await safe_delete(chat_id, mid)
    await safe_delete(chat_id, dr.panel)
    dr.preview, dr.panel = [], None
    if dr.media:
        try:
            dr.preview, _ = await send_post(chat_id, dr.media, render(dr.d))
        except TelegramBadRequest as e:
            await send(chat_id, "⚠️ Ko'rinishni chiqarib bo'lmadi: %s" % esc(str(e)))
    m = await send(chat_id, panel_text(dr), panel_kb(dr))
    dr.panel = m.message_id


async def refresh(chat_id, uid):
    dr = drafts.get(uid)
    if not dr or not dr.d:
        return
    if dr.preview:
        try:
            await bot().edit_message_caption(chat_id=chat_id, message_id=dr.preview[0],
                                             caption=render(dr.d), parse_mode=H)
        except TelegramBadRequest as e:
            if "not modified" not in str(e):
                log.warning("POST: caption yangilanmadi: %s", e)
    dr.panel = await send_or_edit(chat_id, dr.panel, panel_text(dr), panel_kb(dr))


async def ask_text(chat_id, dr, field):
    dr.awaiting = field
    await safe_delete(chat_id, dr.prompt)
    cur = dr.d.get(field)
    if field == "price" and cur:
        cur = pf.fmt_money(cur, dr.d.get("currency"))
    m = await send(chat_id, PROMPTS[field] + "\nHozir: <code>%s</code>\n«-» yozsangiz tozalanadi." % esc(cur or "—"))
    dr.prompt = m.message_id


# ---------- Sozlamalar (faqat admin) ----------
async def settings_menu(chat_id, key, edit=None):
    b = brand_cfg(key)
    lines = ["⚙️ <b>%s</b> — post sozlamalari" % esc(b["name"]), ""]
    for f, label in BRAND_FIELDS:
        v = str(b.get(f) or "").strip()
        lines.append("%s: %s" % (label, esc(v.replace("\n", "; ")) if v else "— <i>(kiritilmagan)</i>"))
    lines += ["", "O'zgartirish uchun tugmani bosing:"]
    rows = pairs([(label, "pm:sf:%s:%s" % (key, f)) for f, label in BRAND_FIELDS])
    rows.append([("⬅️ Orqaga", "pm:home")])
    await send_or_edit(chat_id, edit, "\n".join(lines), kb(rows))


async def check_channel(value):
    try:
        chat = await bot().get_chat(value)
        me = await bot().get_me()
        member = await bot().get_chat_member(chat.id, me.id)
    except Exception as e:
        return value, "⚠️ Kanal topilmadi yoki bot unga qo'shilmagan: <code>%s</code>" % esc(str(e)[:200])
    title = esc(chat.title or chat.username or chat.id)
    if member.status not in ("administrator", "creator"):
        return str(chat.id), "⚠️ «%s» topildi, lekin bot admin emas. Kanalda botni admin qiling." % title
    if member.status == "administrator" and (getattr(member, "can_post_messages", True) is False
                                             or getattr(member, "can_edit_messages", True) is False):
        return str(chat.id), "⚠️ «%s»: botga «post joylash» va «tahrirlash» huquqini bering." % title
    return str(chat.id), "✅ Kanal «%s» ulandi, bot admin." % title


async def save_setting(m, key, field):
    v = (m.text or "").strip()
    note = ""
    if v == "-":
        v = " "                               # bo'sh (standart qiymatga qaytmaydi)
    elif field.endswith("_url") and not re.match(r"https?://", v, re.I):
        v = "https://" + v.lstrip("/")
    if field == "channel" and v.strip():
        v, note = await check_channel(v)
    db.set_setting("post.%s.%s" % (key, field), v)
    await m.answer("✅ Saqlandi. " + note, parse_mode=H)
    await settings_menu(m.chat.id, key)


# ---------- Ruxsatlar ekrani (faqat admin) ----------
async def acl_menu(chat_id, edit=None):
    ids, names = admin_tokens()
    admins = ["@" + n for n in sorted(names)] + [str(i) for i in sorted(ids)]
    lst = acl()
    lines = ["👥 <b>Ruxsatlar</b>", "", "Admin: %s" % esc(", ".join(admins) or "—"), ""]
    if lst:
        lines.append("Post joylay oladiganlar:")
        lines += ["%d. %s" % (i + 1, esc(entry_name(e))) for i, e in enumerate(lst)]
    else:
        lines.append("Hozircha hech kimga ruxsat berilmagan.")
    lines += ["", "Olib tashlash uchun ismini bosing."]
    rows = [[("❌ " + entry_name(e), "pm:acl:del:%d" % i)] for i, e in enumerate(lst)]
    rows.append([("➕ Ruxsat berish", "pm:acl:add")])
    rows.append([("⬅️ Orqaga", "pm:home")])
    await send_or_edit(chat_id, edit, "\n".join(lines), kb(rows))


def target_from(m):
    """Ruxsat beriladigan odam: forward qilingan xabar, @username yoki ID. (entry, xato)"""
    fo = getattr(m, "forward_origin", None)
    if fo is not None:
        su = getattr(fo, "sender_user", None)
        if su:
            return {"id": su.id, "username": (su.username or "").lower(),
                    "name": " ".join(x for x in (su.first_name, su.last_name) if x)}, None
        return None, "Bu odam forward'ni yopib qo'ygan. Uning @username ini yuboring."
    t = (m.text or "").strip()
    if not t:
        return None, "@username yoki ID yuboring."
    if t.lstrip("-").isdigit():
        r = db.one("SELECT * FROM users WHERE id=?", (int(t),))
        e = {"id": int(t), "username": "", "name": ""}
    else:
        if not re.fullmatch(r"@?[A-Za-z0-9_]{4,32}", t):
            return None, "Username noto'g'ri. Masalan: @baxtiyorov_zz"
        r = db.user_by_username(t)
        e = {"id": 0, "username": t.lstrip("@").lower(), "name": ""}
    if r:
        e.update(id=r["id"], username=(r.get("username") or e["username"]).lower(),
                 name=" ".join(x for x in (r.get("first_name"), r.get("last_name")) if x))
    return e, None


# ---------- Buyruqlar ----------
@router.message(Command("post"), F.from_user.func(is_allowed))
async def cmd_post(m: Message):
    await m.answer(home_text(), parse_mode=H, reply_markup=home_kb(m.from_user))


@router.message(Command("maydon"), F.from_user.func(is_allowed))
async def cmd_fields(m: Message, command: CommandObject):
    """Billz'dagi asl maydonlar va bot nimani olgani — xatoni tekshirish uchun."""
    q = (command.args or "").strip().lower()
    if not q:
        await m.answer("Masalan: <code>/maydon 0164</code>", parse_mode=H)
        return
    try:
        items = await stock.products()
    except Exception as e:
        await m.answer("⚠️ Billz: <code>%s</code>" % esc(str(e)[:300]), parse_mode=H)
        return
    found = [x for x in items if q in x["search"]][:2]
    if not found:
        await m.answer("Topilmadi.")
        return
    for x in found:
        p = stock.raw.get(x["id"], {})
        out = ["Nomi: %s" % p.get("name"), "Artikul (sku): %s" % p.get("sku"),
               "Kategoriya: %s" % ", ".join(x["categories"]), "", "Billz maydonlari:"]
        out += ["  %s = %s" % (n, v) for n, v in pf.raw_fields(p)] or ["  (yo'q)"]
        out += ["", "Bot olgani:"]
        for k in ("title", "holat", "rang", "battery", "xotira", "chip", "region"):
            out.append("  %s = %s" % (k, x.get(k) or "—"))
        out.append("  narx = %s, qoldiq = %s" % (pf.fmt_money(x["price"], x["currency"]), x["qty"]))
        await m.answer("<pre>%s</pre>" % esc("\n".join(out)[:3800]), parse_mode=H)


# ---------- Admin ruxsat beradigan odamni yuboradi ----------
@router.message(F.from_user.func(lambda u: u is not None and u.id in grant_wait))
async def on_grant(m: Message):
    uid = m.from_user.id
    if not is_admin(m.from_user):
        grant_wait.discard(uid)
        return
    if (m.text or "").strip() == "-":
        grant_wait.discard(uid)
        await acl_menu(m.chat.id)
        return
    e, err = target_from(m)
    if err:
        await m.answer("⚠️ " + err + "\nBekor qilish: «-»")
        return
    grant_wait.discard(uid)
    lst = acl()
    if any((x.get("id") and x["id"] == e["id"]) or (e["username"] and x.get("username") == e["username"])
           for x in lst):
        await m.answer("Bu odamda ruxsat allaqachon bor.")
    else:
        lst.append(e)
        save_acl(lst)
        note = ""
        if e["id"]:
            try:
                await send(e["id"], "✅ Sizga <b>kanalga post</b> joylash ruxsati berildi.\n"
                                    "/start → «%s»" % HOME_BTN)
                note = " Unga xabar yuborildi."
            except Exception:
                note = " (Unga xabar bora olmadi — botga /start bosishi kerak.)"
        else:
            note = " U botga /start bossa, tugma ko'rinadi."
        await m.answer("✅ %s ga ruxsat berildi.%s" % (entry_name(e), note))
    await acl_menu(m.chat.id)


# ---------- Rasm / video ----------
@router.message(F.photo | F.video, F.from_user.func(is_allowed))
async def on_media(m: Message):
    uid = m.from_user.id
    dr = drafts.get(uid)
    old_prompt = None
    setting_wait.pop(uid, None)
    if uid in album_tasks and dr:
        pass                                   # albomning davomi
    elif dr and dr.awaiting == "media":
        dr.media, dr.awaiting = [], None       # rasmlarni almashtirish
        old_prompt, dr.prompt = dr.prompt, None
    elif dr and (not dr.d or not dr.media):
        pass                                   # artikul hali tanlanmagan yoki rasm kutilmoqda
    else:
        dr = drafts[uid] = Draft()             # yangi post
    item = (m.message_id, "video", m.video.file_id) if m.video else (m.message_id, "photo", m.photo[-1].file_id)
    dr.media.append(item)
    if m.caption and not dr.d:
        dr.query = m.caption.strip()
    old = album_tasks.get(uid)
    if old:
        old.cancel()
    album_tasks[uid] = asyncio.create_task(after_album(uid, m.chat.id))
    await safe_delete(m.chat.id, old_prompt)


async def after_album(uid, chat_id):
    try:
        await asyncio.sleep(1.5)
    except asyncio.CancelledError:
        return
    album_tasks.pop(uid, None)
    dr = drafts.get(uid)
    if not dr:
        return
    try:
        dr.media.sort(key=lambda t: t[0])      # albom tartibi saqlansin
        if len(dr.media) > MAX_MEDIA:
            dr.media = dr.media[:MAX_MEDIA]
            await send(chat_id, "⚠️ Albomga ko'pi bilan 10 ta rasm sig'adi, birinchi 10 tasi olindi.")
        if dr.d:
            await show_preview(chat_id, uid)
        else:
            await safe_delete(chat_id, dr.list_msg)
            dr.list_msg = None
            await show_list(chat_id, uid, header="📸 %s ta rasm qabul qilindi." % len(dr.media),
                            typed=bool(dr.query))
    except Exception:
        log.exception("POST: rasmdan keyingi qadamda xato")


# ---------- Matn (faqat post rejimida) ----------
@router.message(F.text, F.from_user.func(lambda u: u is not None and in_post_mode(u.id) and is_allowed(u)))
async def on_text(m: Message):
    uid = m.from_user.id
    text = m.text.strip()
    sw = setting_wait.pop(uid, None)
    if sw:
        if is_admin(m.from_user):
            await save_setting(m, *sw)
        return
    dr = drafts.get(uid)
    if dr and dr.d and dr.awaiting and dr.awaiting != "media":
        field = dr.awaiting
        val, err = pf.parse_input(field, text, dr.d)
        if err:
            await m.answer("⚠️ " + err)
            return
        dr.d[field] = val
        dr.awaiting = None
        await safe_delete(m.chat.id, m.message_id)
        await safe_delete(m.chat.id, dr.prompt)
        dr.prompt = None
        await refresh(m.chat.id, uid)
        return
    if dr and dr.d and dr.media:
        await m.answer("Postni o'zgartirish uchun paneldagi tugmalarni bosing.\n"
                       "Yangi post uchun rasm yuboring yoki «🆕 Yangi post».")
        return
    if not dr:
        dr = drafts[uid] = Draft()
    dr.d = None
    dr.query, dr.page = text, 0
    await safe_delete(m.chat.id, dr.list_msg)
    dr.list_msg = None
    await show_list(m.chat.id, uid, typed=True)


# ---------- Tugmalar ----------
async def staff_cb(cb: CallbackQuery, admin_only=False):
    ok = is_admin(cb.from_user) if admin_only else is_allowed(cb.from_user)
    if not ok:
        await cb.answer("⛔ Ruxsat yo'q", show_alert=True)
    return ok


async def draft_of(cb: CallbackQuery):
    if not await staff_cb(cb):
        return None
    dr = drafts.get(cb.from_user.id)
    if not dr or not cb.message or cb.message.message_id not in (dr.panel, dr.list_msg):
        await cb.answer("Bu xabar eskirgan. Yangi post uchun rasm yuboring.", show_alert=True)
        return None
    return dr


@router.callback_query(F.data == "pm:noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()


@router.callback_query(F.data == "pm:home")
async def cb_home(cb: CallbackQuery):
    if not await staff_cb(cb):
        return
    setting_wait.pop(cb.from_user.id, None)
    grant_wait.discard(cb.from_user.id)
    await cb.answer()
    await send_or_edit(cb.message.chat.id, cb.message.message_id, home_text(), home_kb(cb.from_user))


@router.callback_query(F.data == "pm:new")
async def cb_new(cb: CallbackQuery):
    if not await staff_cb(cb):
        return
    uid = cb.from_user.id
    drafts[uid] = Draft()
    await cb.answer()
    await show_list(cb.message.chat.id, uid, edit=cb.message.message_id,
                    header="🆕 Yangi post. Rasmlarni hozir ham, keyin ham yuborsangiz bo'ladi.")


@router.callback_query(F.data == "pm:posts")
async def cb_posts(cb: CallbackQuery):
    if not await staff_cb(cb):
        return
    await cb.answer()
    rows = db.recent_channel_posts(15)
    if not rows:
        text = "Hali post joylanmagan."
    else:
        icons = {"active": "🟢", "sold": "🔴", "deleted": "⚪"}
        lines = ["📋 <b>Oxirgi postlar</b> (🟢 sotuvda, 🔴 sotildi, ⚪ o'chirilgan)", ""]
        for r in rows:
            d = json.loads(r["data"] or "{}")
            sku = esc(r["sku"] or d.get("title") or "?")
            name = '<a href="%s">%s</a>' % (esc(r["link"]), sku) if r["link"] else sku
            price = pf.fmt_money(d.get("price") or 0, d.get("currency") or "USD")
            day = time.strftime("%d.%m", time.gmtime((r["created_at"] or 0) + db.TZ_SHIFT))
            lines.append("%s %s · %s · %s" % (icons.get(r["status"], "•"), name, price, day))
        text = "\n".join(lines)
    await send_or_edit(cb.message.chat.id, cb.message.message_id, text, kb([[("⬅️ Orqaga", "pm:home")]]))


@router.callback_query(F.data == "pm:set")
async def cb_settings(cb: CallbackQuery):
    if not await staff_cb(cb, admin_only=True):
        return
    await cb.answer()
    keys = brand_keys()
    if len(keys) == 1:
        await settings_menu(cb.message.chat.id, keys[0], edit=cb.message.message_id)
    else:
        rows = [[(brand_cfg(k)["name"], "pm:sb:" + k)] for k in keys] + [[("⬅️ Orqaga", "pm:home")]]
        await send_or_edit(cb.message.chat.id, cb.message.message_id, "Qaysi brend?", kb(rows))


@router.callback_query(F.data.startswith("pm:sb:"))
async def cb_settings_brand(cb: CallbackQuery):
    if not await staff_cb(cb, admin_only=True):
        return
    await cb.answer()
    await settings_menu(cb.message.chat.id, cb.data[6:], edit=cb.message.message_id)


@router.callback_query(F.data.startswith("pm:sf:"))
async def cb_settings_field(cb: CallbackQuery):
    if not await staff_cb(cb, admin_only=True):
        return
    _, _, key, field = cb.data.split(":", 3)
    if field not in SETTING_HINTS:
        return await cb.answer()
    setting_wait[cb.from_user.id] = (key, field)
    cur = str(brand_cfg(key).get(field) or "").strip()
    await cb.answer()
    await send(cb.message.chat.id, "%s\n\nHozir: <code>%s</code>\n«-» yuborsangiz tozalanadi."
               % (SETTING_HINTS[field], esc(cur) if cur else "—"))


@router.callback_query(F.data == "pm:acl")
async def cb_acl(cb: CallbackQuery):
    if not await staff_cb(cb, admin_only=True):
        return
    grant_wait.discard(cb.from_user.id)
    await cb.answer()
    await acl_menu(cb.message.chat.id, edit=cb.message.message_id)


@router.callback_query(F.data == "pm:acl:add")
async def cb_acl_add(cb: CallbackQuery):
    if not await staff_cb(cb, admin_only=True):
        return
    grant_wait.add(cb.from_user.id)
    await cb.answer()
    await send(cb.message.chat.id,
               "➕ Ruxsat bermoqchi bo'lgan odamning <b>@username</b> ini yuboring "
               "yoki uning biror xabarini shu yerga <b>forward</b> qiling.\n"
               "U botga /start bosgan bo'lsa, unga xabar boradi.\n\nBekor qilish: «-»")


@router.callback_query(F.data.startswith("pm:acl:del:"))
async def cb_acl_del(cb: CallbackQuery):
    if not await staff_cb(cb, admin_only=True):
        return
    i = int(cb.data.rsplit(":", 1)[1])
    lst = acl()
    if 0 <= i < len(lst):
        e = lst.pop(i)
        save_acl(lst)
        if e.get("id"):
            reset(e["id"])
        await cb.answer("❌ %s — ruxsat olib tashlandi" % entry_name(e), show_alert=True)
    else:
        await cb.answer()
    await acl_menu(cb.message.chat.id, edit=cb.message.message_id)


@router.callback_query(F.data.startswith("pm:pg:") | F.data.startswith("pm:ls:"))
async def cb_list(cb: CallbackQuery):
    dr = await draft_of(cb)
    if not dr:
        return
    if cb.data.startswith("pm:pg:"):
        dr.page = int(cb.data[6:])
    elif cb.data == "pm:ls:all":
        dr.query, dr.page = "", 0
    elif cb.data == "pm:ls:refresh":
        try:
            await stock.products(force=True)
        except Exception:
            pass
    await cb.answer()
    await show_list(cb.message.chat.id, cb.from_user.id, edit=cb.message.message_id)


@router.callback_query(F.data.startswith("pm:p:"))
async def cb_pick(cb: CallbackQuery):
    dr = await draft_of(cb)
    if not dr:
        return
    i = int(cb.data[5:])
    if i >= len(dr.list_ids):
        return await cb.answer("Ro'yxat yangilandi, qaytadan tanlang", show_alert=True)
    pid = dr.list_ids[i]
    x = stock.find(pid)
    if not x:
        try:
            await stock.products(force=True)
        except Exception:
            pass
        x = stock.find(pid)
    if not x:
        return await cb.answer("Bu tovar Billz'da sotuvda emas (sotilgan bo'lishi mumkin).", show_alert=True)
    await cb.answer()
    await choose(cb.message.chat.id, cb.from_user.id, x, list_msg=cb.message.message_id)


@router.callback_query(F.data.startswith("pm:e:"))
async def cb_edit(cb: CallbackQuery):
    dr = await draft_of(cb)
    if not dr or not dr.d:
        return
    chat_id, f, d = cb.message.chat.id, cb.data[5:], dr.d
    if f in CHOICE_FIELDS:
        opts = list(cfg.OPTIONS.get(f, []))
        if f in ("holat", "rang"):
            opts += [v for v in stock.values(f) if v not in opts]
        cur = d.get(f)
        if cur and cur not in opts:
            opts.insert(0, cur)
        dr.opts = opts[:20]
        rows = pairs([(("☑️ " if o == cur else "") + o, "pm:o:%s:%d" % (f, i)) for i, o in enumerate(dr.opts)])
        rows.append([("✍️ Qo'lda yozish", "pm:w:" + f), ("⬅️ Orqaga", "pm:back")])
        await send_or_edit(chat_id, dr.panel, "<b>%s</b> — tanlang:" % pf.LABELS[f], kb(rows))
    elif f == "manager":
        lines = pf.manager_lines(brand_cfg(d["brand"]))
        if not lines:
            return await cb.answer("Menejerlar kiritilmagan: ⚙️ Sozlamalar → 👤 Menejerlar", show_alert=True)
        dr.opts = lines
        rows = [[(("☑️ " if i == d.get("manager") else "") + ln, "pm:o:manager:%d" % i)] for i, ln in enumerate(lines)]
        rows.append([("⬅️ Orqaga", "pm:back")])
        await send_or_edit(chat_id, dr.panel, "<b>Murojaat uchun</b> — kim?", kb(rows))
    elif f == "media":
        dr.awaiting = "media"
        await safe_delete(chat_id, dr.prompt)
        m = await send(chat_id, "🖼 Yangi rasmlarni yuboring (1–10 ta). Eskilari almashtiriladi.")
        dr.prompt = m.message_id
    elif f in PROMPTS:
        await ask_text(chat_id, dr, f)
    await cb.answer()


@router.callback_query(F.data.startswith("pm:w:"))
async def cb_write(cb: CallbackQuery):
    dr = await draft_of(cb)
    if not dr or not dr.d:
        return
    await cb.answer()
    dr.panel = await send_or_edit(cb.message.chat.id, dr.panel, panel_text(dr), panel_kb(dr))
    if cb.data[5:] in PROMPTS:
        await ask_text(cb.message.chat.id, dr, cb.data[5:])


@router.callback_query(F.data.startswith("pm:o:"))
async def cb_option(cb: CallbackQuery):
    dr = await draft_of(cb)
    if not dr or not dr.d:
        return
    _, _, f, i = cb.data.split(":")
    i = int(i)
    if i >= len(dr.opts):
        return await cb.answer("Qaytadan tanlang", show_alert=True)
    if f == "manager":
        dr.d["manager"] = i
    elif f in CHOICE_FIELDS:
        dr.d[f] = dr.opts[i]
    await cb.answer("✅")
    await refresh(cb.message.chat.id, cb.from_user.id)


@router.callback_query(F.data == "pm:back")
async def cb_back(cb: CallbackQuery):
    dr = await draft_of(cb)
    if not dr or not dr.d:
        return
    await cb.answer()
    dr.panel = await send_or_edit(cb.message.chat.id, dr.panel, panel_text(dr), panel_kb(dr))


@router.callback_query(F.data.startswith("pm:t:"))
async def cb_toggle(cb: CallbackQuery):
    dr = await draft_of(cb)
    if not dr or not dr.d:
        return
    if cb.data == "pm:t:inst":
        dr.d["installment"] = not dr.d.get("installment")
    elif cb.data == "pm:t:brand":
        keys = brand_keys()
        i = keys.index(dr.d["brand"]) if dr.d["brand"] in keys else -1
        dr.d["brand"] = keys[(i + 1) % len(keys)]
        dr.d["manager"] = 0
    await cb.answer()
    await refresh(cb.message.chat.id, cb.from_user.id)


@router.callback_query(F.data == "pm:copy")
async def cb_copy(cb: CallbackQuery):
    dr = await draft_of(cb)
    if not dr or not dr.d:
        return
    await cb.answer()
    await send(cb.message.chat.id, render(dr.d))


@router.callback_query(F.data == "pm:x")
async def cb_cancel(cb: CallbackQuery):
    dr = await draft_of(cb)
    if not dr:
        return
    drafts.pop(cb.from_user.id, None)
    await safe_delete(cb.message.chat.id, dr.prompt)
    await cb.answer()
    await send_or_edit(cb.message.chat.id, cb.message.message_id, "❌ Bekor qilindi.",
                       kb([[(HOME_BTN, "pm:home")]]))


def publish_targets():
    return [k for k in brand_keys() if str(brand_cfg(k).get("channel") or "").strip()]


@router.callback_query(F.data == "pm:pub")
async def cb_publish(cb: CallbackQuery):
    dr = await draft_of(cb)
    if not dr or not dr.d:
        return
    d = dr.d
    miss = pf.missing(d)
    if miss:
        return await cb.answer("⚠️ Avval to'ldiring: " + ", ".join(miss), show_alert=True)
    if not dr.media:
        return await cb.answer("⚠️ Rasm yo'q. Avval rasmlarni yuboring.", show_alert=True)
    if pf.visible_len(render(d)) > 1024:
        return await cb.answer("⚠️ Matn 1024 belgidan uzun. Teglar yoki nomni qisqartiring.", show_alert=True)
    targets = publish_targets()
    if not targets:
        who = "⚙️ Sozlamalar → 📢 Kanal" if is_admin(cb.from_user) else "adminga ayting: kanal kiritilmagan"
        return await cb.answer("Kanal kiritilmagan: " + who, show_alert=True)
    lines = ["📢 <b>Joylashni tasdiqlang</b>", "Artikul: <code>%s</code>" % esc(d["sku"])]
    if d["product_id"] in db.posted_product_ids():
        lines.append("⚠️ Bu tovar avval ham joylangan. Baribir joylaymi?")
    if len(targets) == 1:
        rows = [[("✅ Ha, «%s» kanaliga joylash" % brand_cfg(targets[0])["name"], "pm:pk:" + targets[0])]]
    else:
        rows = [[("📢 " + brand_cfg(k)["name"], "pm:pk:" + k)] for k in targets] + [[("📢 Hammasiga", "pm:pk:*")]]
    rows.append([("⬅️ Orqaga", "pm:back")])
    await cb.answer()
    await send_or_edit(cb.message.chat.id, dr.panel, "\n".join(lines), kb(rows))


@router.callback_query(F.data.startswith("pm:pk:"))
async def cb_publish_ok(cb: CallbackQuery):
    dr = await draft_of(cb)
    if not dr or not dr.d:
        return
    if dr.busy:
        return await cb.answer("Joylanyapti...")
    dr.busy = True
    await cb.answer("Joylanyapti...")
    try:
        k = cb.data[6:]
        keys = publish_targets() if k == "*" else [k]
        x = stock.find(dr.d["product_id"])
        billz_price = x["price"] if x else dr.d.get("price")
        results = []
        for key in keys:
            b = brand_cfg(key)
            data = dict(dr.d, brand=key)
            try:
                ids, chat_id = await send_post(str(b["channel"]).strip(), dr.media, render(data, b))
            except Exception as e:
                log.exception("POST: joylashda xato")
                results.append("❌ %s: <code>%s</code>" % (esc(b["name"]), esc(str(e)[:200])))
                continue
            link = await post_link(chat_id, ids[0])
            db.add_channel_post(data["product_id"], data["sku"], key, chat_id, ids[0], link, data,
                                billz_price, cb.from_user.id)
            results.append("✅ %s: %s" % (esc(b["name"]), link or "joylandi"))
        if any(r.startswith("✅") for r in results):
            drafts.pop(cb.from_user.id, None)
            await send_or_edit(cb.message.chat.id, cb.message.message_id,
                               "🎉 <b>Joylandi</b>\n" + "\n".join(results), kb([[(HOME_BTN, "pm:home")]]))
            log.info("POST: %s joyladi: %s", cb.from_user.id, dr.d.get("sku"))
        else:
            await send_or_edit(cb.message.chat.id, cb.message.message_id,
                               "\n".join(results) + "\n\nKanal sozlamasini tekshiring.", panel_kb(dr))
    finally:
        dr.busy = False


# ---------- Sotilganini kuzatish ----------
async def edit_channel_post(r, d, sold):
    try:
        await bot().edit_message_caption(chat_id=r["chat_id"], message_id=r["msg_id"],
                                         caption=render(d, brand_cfg(r["brand"]), sold=sold), parse_mode=H)
        return True
    except TelegramBadRequest as e:
        s = str(e).lower()
        if "not modified" in s:
            return True
        if "not found" in s:
            db.update_channel_post(r["id"], status="deleted")
        log.warning("POST: post %s tahrirlanmadi: %s", r["id"], e)
        return False


async def sync_once():
    rows = db.tracked_channel_posts()
    if not rows:
        return
    prev = stock.last_count
    try:
        items = await stock.products(force=True)
    except Exception:
        log.exception("POST sync: Billz xatosi, bu safar o'tkazib yuborildi")
        return
    if not items or (prev and len(items) < prev * 0.3):
        log.warning("POST sync: Billz %s ta tovar qaytardi (oldin %s) — shubhali, o'tkazildi", len(items), prev)
        return
    by_id = {x["id"]: x for x in items}
    for r in rows:
        d = json.loads(r["data"] or "{}")
        x = by_id.get(r["product_id"])
        sku, link, author = esc(r["sku"]), r["link"] or "", [r.get("author_id")]
        if x and x["qty"] > 0:
            changed = r["status"] == "sold"
            upd = {"status": "active", "miss": 0}
            old_bp = float(r["billz_price"] or 0)
            if cfg.AUTO_PRICE and x["price"] > 0 and abs(x["price"] - old_bp) > 0.009:
                d.update(price=x["price"], old_price=x["old_price"], currency=x["currency"])
                upd.update(data=d, billz_price=x["price"])
                changed = True
                await notify("💵 <code>%s</code> narxi o'zgardi: %s → %s. Post yangilandi: %s" % (
                    sku, pf.fmt_money(old_bp, x["currency"]), pf.fmt_money(x["price"], x["currency"]), link), author)
            if changed and await edit_channel_post(r, d, sold=False) and r["status"] == "sold":
                await notify("♻️ <code>%s</code> yana sotuvda — «SOTILDI» olib tashlandi: %s" % (sku, link), author)
            db.update_channel_post(r["id"], **upd)
        else:
            miss = (r["miss"] or 0) + 1
            if r["status"] == "active" and miss >= 2:     # ikki marta ketma-ket yo'q — sotilgan
                if await edit_channel_post(r, d, sold=True):
                    db.update_channel_post(r["id"], status="sold", miss=miss)
                    await notify("🔴 <code>%s</code> sotildi — kanaldagi postga «SOTILDI» qo'yildi: %s"
                                 % (sku, link), author)
                    continue
            db.update_channel_post(r["id"], miss=miss)


async def sync_loop():
    await asyncio.sleep(60)
    while True:
        try:
            await sync_once()
        except Exception:
            log.exception("POST: sync xatosi")
        await asyncio.sleep(max(2, cfg.SYNC_MINUTES) * 60)


def setup(bot_obj, fetch, plan_fn=None, shop_id=""):
    """shop_bot.py dan chaqiriladi. fetch = billz_products(include_empty, max_pages)."""
    ctx.update(bot=bot_obj, fetch=fetch)
    if plan_fn:
        pf.plan_fn = plan_fn
    pf.set_shop_id(shop_id or os.environ.get("BILLZ_SHOP_ID", ""))


def start():
    asyncio.create_task(sync_loop())
    ids, names = admin_tokens()
    log.info("POST: «Kanalga post» yoqildi. Admin: %s", ", ".join(["@" + n for n in names] + [str(i) for i in ids]))
