"""«📣 Guruhga reklama berish» — guruh himoyasi (Uzmacbook / MagicPro.uz do'kon boti).

- Himoya yoqilgan guruhda cheklangan narsalar (rasm, video, link, boshqa @username) avtomatik
  o'chiriladi va yuborgan odam tag qilinib: «admindan ruxsat oling» deyiladi.
- Ozod: admin (POST_ADMINS, @sherxonjumayev), «Ruxsatlar» ro'yxatidagilar, guruh adminlari,
  anonim admin, guruhga bog'langan kanal, botlar.
- Har bir guruhda himoya alohida yoqiladi (buyurtmalar/xodimlar guruhi tasodifan himoyalanib qolmasin).
- Boshqaruv paneli shaxsiy chatda: /start → «📣 Guruhga reklama berish» (faqat admin va ruxsat berilganlar).
- Guruh xabarlari do'kon botining boshqa qismlariga (salom javobi, post bo'limi, mijozlar bazasi) bormaydi.

Bot guruhda ADMIN bo'lishi va «Xabarlarni o'chirish» huquqiga ega bo'lishi shart."""
import asyncio
import html
import json
import logging
import re
import time
from urllib.parse import urlparse

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import (CallbackQuery, ChatMemberUpdated, InlineKeyboardButton, InlineKeyboardMarkup,
                           LinkPreviewOptions, Message)

import db
import post_bot

log = logging.getLogger("GUARD")
router = Router(name="guard")
ctx = {"bot": None, "me": None}
H = ParseMode.HTML
NO_PREVIEW = LinkPreviewOptions(is_disabled=True)
GROUP_TYPES = ("group", "supergroup")
HOME_BTN = "📣 Guruhga reklama berish"

KINDS = [("photo", "🖼 Rasm"), ("video", "🎬 Video"), ("link", "🔗 Link va silkalar"), ("username", "@ Username'lar")]
KIND_WORDS = {"photo": "rasm", "video": "video", "link": "link", "username": "username"}
WARN_TTL = 60          # ogohlantirish necha soniyadan keyin o'chadi (0 — o'chmaydi)
WARN_GAP = 20          # bir odamga necha soniyada bir marta ogohlantirish (albom/ketma-ket xabar)
ADMIN_CACHE = 600      # guruh adminlari ro'yxati necha soniya eslab qolinadi

LINK_RE = re.compile(r"(?i)(?:https?://|www\.|\bt\.me/|\btelegram\.(?:me|dog)/)[^\s<>\"']+")
# Telegram o'zi aniqlamagan saytlar uchun (MacBook.Pro kabi so'zlar ilinmasligi uchun faqat shu domenlar)
DOMAIN_RE = re.compile(r"(?i)(?<![@\w.])(?:[a-z0-9-]+\.)+(?:uz|com|ru|net|org|io|app|shop|store|link|site|"
                       r"online|xyz|info)\b(?:/[^\s<>\"']*)?")
USER_RE = re.compile(r"(?<![\w@/.])@([A-Za-z][A-Za-z0-9_]{3,31})\b")
TG_HOSTS = ("t.me", "telegram.me", "telegram.dog")

_admin_cache = {}     # (chat_id, user_id) -> (admin_mi, vaqt)
_last_warn = {}       # (chat_id, kim) -> vaqt
_fail_told = {}       # chat_id -> vaqt (o'chirish huquqi yo'qligi haqida admin ogohlantirildi)
grant_wait = set()    # ruxsat beriladigan odamni kutayotgan adminlar
words_wait = set()    # ruxsat etilgan username/saytlar ro'yxatini kutayotgan adminlar


# ---------- Sozlamalar (bazada) ----------
def _json(key, default):
    try:
        v = json.loads(db.get_setting(key) or "null")
    except ValueError:
        v = None
    return v if isinstance(v, type(default)) else default


def restrict():
    """Nima cheklangan: {photo, video, link, username} -> True (o'chiriladi) / False (ruxsat)."""
    r = {k: True for k, _ in KINDS}
    r.update({k: bool(v) for k, v in _json("guard.restrict", {}).items() if k in r})
    return r


def save_restrict(r):
    db.set_setting("guard.restrict", json.dumps(r))


def groups():
    """{chat_id: {"title": ..., "on": bool, "left": bool}}"""
    return _json("guard.groups", {})


def save_groups(g):
    db.set_setting("guard.groups", json.dumps(g, ensure_ascii=False))


def remember_group(chat, left=False):
    g = groups()
    key = str(chat.id)
    cur = g.get(key) or {"on": False}
    title = chat.title or cur.get("title") or key
    if cur.get("title") != title or bool(cur.get("left")) != left or key not in g:
        cur.update(title=title, left=left)
        g[key] = cur
        save_groups(g)
    return cur


def acl():
    return _json("guard.allowed", [])


def save_acl(lst):
    db.set_setting("guard.allowed", json.dumps(lst, ensure_ascii=False) if lst else "")


def extra_words():
    """Admin qo'shgan ruxsat etilgan username va saytlar (har qatorda bittasi)."""
    out = []
    for w in re.split(r"[\s,;]+", db.get_setting("guard.words") or ""):
        w = w.strip().lower()
        w = re.sub(r"^(?:https?://)?(?:www\.)?(?:t\.me/|telegram\.me/)?@?", "", w).strip("/")
        if w and w not in out:
            out.append(w)
    return out


# ---------- Kim ozod ----------
def is_granted(u):
    """«Ruxsatlar» ro'yxatida bormi (ID yoki @username bo'yicha)."""
    if not u:
        return False
    uname = (u.username or "").lower()
    lst = acl()
    for e in lst:
        if e.get("id"):
            if e["id"] == u.id:
                return True
        elif uname and e.get("username") == uname:
            e["id"] = u.id          # @username bilan qo'shilgan edi — endi ID ni eslab qolamiz
            save_acl(lst)
            return True
    return False


def can_open(u):
    return post_bot.is_admin(u) or is_granted(u)


async def is_group_admin(chat_id, uid):
    key = (chat_id, uid)
    c = _admin_cache.get(key)
    if c and time.time() - c[1] < ADMIN_CACHE:
        return c[0]
    try:
        m = await ctx["bot"].get_chat_member(chat_id, uid)
    except TelegramAPIError:
        return False
    ok = m.status in ("creator", "administrator")
    _admin_cache[key] = (ok, time.time())
    return ok


async def is_exempt(m):
    if m.sender_chat is not None:
        if m.sender_chat.id == m.chat.id or m.is_automatic_forward:
            return True                       # anonim admin yoki guruhga bog'langan kanal
        return False                          # boshqa kanal nomidan yozilgan — tekshiriladi
    u = m.from_user
    if u is None or u.is_bot:
        return True
    if post_bot.is_admin(u) or is_granted(u):
        return True
    return await is_group_admin(m.chat.id, u.id)


# ---------- Cheklangan narsalarni topish ----------
async def me():
    if ctx["me"] is None:
        ctx["me"] = await ctx["bot"].get_me()
    return ctx["me"]


async def allowed_names(chat):
    """Tegilsa yoki linki tashlansa bo'ladigan username'lar (kichik harfda)."""
    names = set(post_bot.admin_tokens()[1])
    b = await me()
    if b.username:
        names.add(b.username.lower())
    if getattr(chat, "username", None):
        names.add(chat.username.lower())
    names.update(w for w in extra_words() if "." not in w)
    names.update(e["username"] for e in acl() if e.get("username"))
    return names


def link_ok(url, names, domains):
    u = url.strip()
    if not re.match(r"(?i)^[a-z][a-z0-9+.-]*://", u):
        u = "http://" + u
    try:
        p = urlparse(u)
    except ValueError:
        return False
    host = (p.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host in TG_HOSTS:
        first = (p.path or "/").strip("/").split("/")[0].lstrip("@").lower()
        return bool(first) and first in names
    return any(host == d or host.endswith("." + d) for d in domains)


def _ent_text(text, e):
    try:
        return e.extract_from(text)
    except Exception:
        return ""


async def violations(m):
    r = restrict()
    text = m.text or m.caption or ""
    ents = list(m.entities or []) + list(m.caption_entities or [])
    mime = (m.document.mime_type or "").lower() if m.document else ""
    found = []
    if r["photo"] and (m.photo or mime.startswith("image/")):
        found.append("photo")
    if r["video"] and (m.video or m.video_note or m.animation or mime.startswith("video/")):
        found.append("video")
    if not (r["link"] or r["username"]):
        return found
    names = await allowed_names(m.chat)
    if r["link"]:
        domains = [w for w in extra_words() if "." in w]
        urls = []
        for e in ents:
            if e.type == "url":
                urls.append(_ent_text(text, e))
            elif e.type == "text_link" and e.url:
                urls.append(e.url)
        urls += LINK_RE.findall(text) + [mt.group(0) for mt in DOMAIN_RE.finditer(text)]
        if m.reply_markup and getattr(m.reply_markup, "inline_keyboard", None):
            urls += [b.url for row in m.reply_markup.inline_keyboard for b in row if b.url]
        if any(url and not link_ok(url, names, domains) for url in urls):
            found.append("link")
    if r["username"]:
        tags = [_ent_text(text, e).lstrip("@") for e in ents if e.type == "mention"]
        tags += USER_RE.findall(text)
        if any(t and t.lower() not in names for t in tags):
            found.append("username")
    return found


# ---------- Guruh xabarini tekshirish ----------
def _who(m):
    if m.sender_chat is not None and m.sender_chat.id != m.chat.id:
        return m.sender_chat.id, "<b>%s</b>" % html.escape(m.sender_chat.title or "Kanal")
    u = m.from_user
    if u.username:
        return u.id, "@" + html.escape(u.username)
    return u.id, '<a href="tg://user?id=%d">%s</a>' % (u.id, html.escape(u.full_name or "Foydalanuvchi"))


def admin_mention():
    names = sorted(post_bot.admin_tokens()[1])
    return ("@" + names[0]) if names else "admin"


async def _delete_later(msg, delay):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except TelegramAPIError:
        pass


async def check(m):
    """Guruh xabari: himoya yoqilgan bo'lsa va cheklangan narsa bo'lsa — o'chiradi va ogohlantiradi."""
    g = remember_group(m.chat)
    if not g.get("on"):
        return
    if await is_exempt(m):
        return
    found = await violations(m)
    if not found:
        return
    try:
        await m.delete()
    except TelegramAPIError as e:
        log.warning("GUARD: %s guruhida xabarni o'chirib bo'lmadi: %s", m.chat.id, e)
        if time.time() - _fail_told.get(m.chat.id, 0) > 3600:
            _fail_told[m.chat.id] = time.time()
            await post_bot.notify("⚠️ «%s» guruhida reklamani o'chira olmadim. Botni guruhda admin qiling "
                                  "va «Xabarlarni o'chirish» huquqini bering." % html.escape(m.chat.title or ""))
        return
    who_id, tag = _who(m)
    key = (m.chat.id, who_id)
    if time.time() - _last_warn.get(key, 0) < WARN_GAP:
        return                                 # albomning qolgan rasmlari — bitta ogohlantirish yetadi
    _last_warn[key] = time.time()
    what = ", ".join(KIND_WORDS[k] for k in found)
    try:
        msg = await ctx["bot"].send_message(
            m.chat.id, "%s, guruhga %s tashlash uchun admindan ruxsat oling: %s" % (tag, what, admin_mention()),
            parse_mode=H, link_preview_options=NO_PREVIEW)
        if WARN_TTL:
            asyncio.create_task(_delete_later(msg, WARN_TTL))
    except TelegramAPIError:
        log.exception("GUARD: ogohlantirish yuborilmadi")


async def group_command(m):
    """Guruhda admin: odamning xabariga reply qilib /ruxsat yoki /ruxsat_ol. True — buyruq edi."""
    t = (m.text or "").strip()
    cmd = re.match(r"^/(ruxsat_ol|ruxsat)(?:@\w+)?\b", t)
    if not cmd:
        return False
    if not post_bot.is_admin(m.from_user):
        return True
    target = m.reply_to_message.from_user if m.reply_to_message else None
    if target is None or target.is_bot:
        await m.reply("Odamning xabariga reply qilib /%s deb yozing." % cmd.group(1))
        return True
    lst = acl()
    name = " ".join(x for x in (target.first_name, target.last_name) if x)
    if cmd.group(1) == "ruxsat":
        if not any(e.get("id") == target.id for e in lst):
            lst.append({"id": target.id, "username": (target.username or "").lower(), "name": name})
            save_acl(lst)
        await m.reply("✅ %s ga guruhga reklama berish ruxsati berildi." % html.escape(name), parse_mode=H)
    else:
        lst = [e for e in lst if e.get("id") != target.id]
        save_acl(lst)
        await m.reply("❌ %s dan ruxsat olib tashlandi." % html.escape(name), parse_mode=H)
    return True


async def mw(handler, event, data):
    """Guruh xabarlari shu yerda tekshiriladi va do'kon botining boshqa qismlariga o'tkazilmaydi."""
    chat = getattr(event, "chat", None)
    if chat is None or chat.type not in GROUP_TYPES:
        return await handler(event, data)
    try:
        if not await group_command(event):
            await check(event)
    except Exception:
        log.exception("GUARD: guruh xabarini tekshirishda xato")
    return None


@router.edited_message(F.chat.type.in_(GROUP_TYPES))
async def on_edited(m: Message):
    """Reklamani keyin tahrirlab qo'shishsa ham ushlanadi."""
    try:
        await check(m)
    except Exception:
        log.exception("GUARD: tahrirlangan xabarni tekshirishda xato")


@router.my_chat_member(F.chat.type.in_(GROUP_TYPES))
async def on_bot_status(u: ChatMemberUpdated):
    """Bot guruhga qo'shildi / admin qilindi / chiqarildi."""
    st = u.new_chat_member.status
    left = st in ("left", "kicked")
    g = remember_group(u.chat, left=left)
    title = html.escape(u.chat.title or "")
    if left:
        await post_bot.notify("ℹ️ Bot «%s» guruhidan chiqarildi." % title)
        return
    if u.old_chat_member.status in ("left", "kicked") or (st == "administrator"
                                                          and u.old_chat_member.status != "administrator"):
        state = "admin" if st == "administrator" else "a'zo (admin emas)"
        tip = "" if st == "administrator" else "\nHimoya ishlashi uchun botni admin qiling («Xabarlarni o'chirish» huquqi)."
        on = "yoqilgan ✅" if g.get("on") else "o'chiq ⏸"
        kb = None if g.get("on") else InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
            text="🛡 Himoyani yoqish", callback_data="gg:tg:%s" % u.chat.id)]])
        for uid in post_bot.admin_ids():
            try:
                await ctx["bot"].send_message(uid, "📣 Bot «%s» guruhida: %s. Himoya: %s.%s" % (title, state, on, tip),
                                              parse_mode=H, reply_markup=kb)
            except TelegramAPIError:
                pass


# ---------- Boshqaruv paneli (shaxsiy chat) ----------
def menu_row(user):
    if user is not None and can_open(user):
        return [InlineKeyboardButton(text=HOME_BTN, callback_data="gg:home")]
    return None


def reset(uid):
    grant_wait.discard(uid)
    words_wait.discard(uid)


def kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=c) for t, c in row] for row in rows])


async def bot_rights(chat_id):
    """Botning guruhdagi holati: '✅' / '⚠️ admin emas' / '⚠️ o'chirish huquqi yo'q' / '⚠️ guruhda yo'q'."""
    try:
        m = await ctx["bot"].get_chat_member(int(chat_id), (await me()).id)
    except TelegramAPIError:
        return "⚠️ bot guruhda yo'q"
    if m.status == "creator":
        return ""
    if m.status != "administrator":
        return "⚠️ bot admin emas"
    if getattr(m, "can_delete_messages", True) is False:
        return "⚠️ o'chirish huquqi yo'q"
    return ""


async def home_view(user):
    if not post_bot.is_admin(user):
        r = restrict()
        lim = [KIND_WORDS[k] for k, _ in KINDS if r[k]]
        return ("📣 <b>Guruhga reklama berish</b>\n\n"
                "✅ Sizga guruhga reklama berish ruxsati berilgan. "
                "Guruhda %s bo'lgan xabarlaringiz o'chirilmaydi." % (", ".join(lim) or "hech narsa cheklanmagan, barcha")
                ), [[("⬅️ Menyu", "menu")]]
    g = groups()
    r = restrict()
    lines = ["📣 <b>Guruhga reklama berish</b>", ""]
    rows = []
    live = [(k, v) for k, v in g.items() if not v.get("left")]
    if not live:
        lines.append("Bot hali birorta guruhda emas. Botni guruhga qo'shing va admin qiling "
                     "(«Xabarlarni o'chirish» huquqi bilan) — guruh shu yerda chiqadi.")
    else:
        lines.append("<b>Guruhlar</b> (himoyani yoqish/o'chirish uchun bosing):")
        for k, v in live:
            warn = await bot_rights(k)
            lines.append("%s %s%s" % ("🛡" if v.get("on") else "⏸", html.escape(v.get("title") or k),
                                      (" — " + warn) if warn else ""))
            rows.append([("%s %s" % ("✅" if v.get("on") else "⏸", (v.get("title") or k)[:30]), "gg:tg:%s" % k)])
    lim = [KIND_WORDS[k] for k, _ in KINDS if r[k]]
    lines += ["", "Cheklangan: %s" % (", ".join(lim) or "hech narsa"),
              "Ruxsat berilganlar: %d kishi" % len(acl())]
    rows += [[("👥 Ruxsatlar", "gg:acl"), ("⚙️ Sozlamalar", "gg:set")], [("⬅️ Menyu", "menu")]]
    return "\n".join(lines), rows


async def acl_view():
    lst = acl()
    lines = ["👥 <b>Ruxsatlar</b> — guruhga reklama bera oladiganlar", "",
             "Admin: %s (har doim ozod)" % html.escape(admin_mention()), ""]
    if lst:
        lines += ["%d. %s" % (i + 1, html.escape(post_bot.entry_name(e))) for i, e in enumerate(lst)]
    else:
        lines.append("Hozircha hech kimga ruxsat berilmagan.")
    lines += ["", "Olib tashlash uchun ismini bosing.",
              "Guruhda odamning xabariga reply qilib /ruxsat (yoki /ruxsat_ol) yozsangiz ham bo'ladi."]
    rows = [[("❌ " + post_bot.entry_name(e)[:40], "gg:del:%d" % i)] for i, e in enumerate(lst)]
    rows += [[("➕ Ruxsat berish", "gg:add")], [("⬅️ Orqaga", "gg:home")]]
    return "\n".join(lines), rows


async def set_view():
    r = restrict()
    b = await me()
    always = [admin_mention()] + (["@" + b.username] if b.username else [])
    words = extra_words()
    lines = ["⚙️ <b>Sozlamalar</b> — guruhda nimani cheklash", "",
             "❌ cheklangan — guruhda o'chiriladi va odam tag qilinadi",
             "✅ ruxsat — tegilmaydi", "",
             "<b>Har doim ruxsat:</b> %s" % html.escape(", ".join(always)),
             "<b>Qo'shimcha ruxsat etilgan username va saytlar:</b> %s"
             % (html.escape(", ".join(words)) if words else "— <i>(yo'q)</i>")]
    rows = [[("%s: %s" % (label, "❌ cheklangan" if r[k] else "✅ ruxsat"), "gg:k:%s" % k)] for k, label in KINDS]
    rows += [[("✏️ Ruxsat etilgan username va saytlar", "gg:words")], [("⬅️ Orqaga", "gg:home")]]
    return "\n".join(lines), rows


async def show(c, view):
    text, rows = view
    try:
        await c.message.edit_text(text, parse_mode=H, reply_markup=kb(rows), link_preview_options=NO_PREVIEW)
    except TelegramBadRequest as e:
        if "not modified" not in str(e):
            await c.message.answer(text, parse_mode=H, reply_markup=kb(rows), link_preview_options=NO_PREVIEW)


@router.callback_query(F.data.startswith("gg:"))
async def on_panel(c: CallbackQuery):
    u = c.from_user
    if not can_open(u):
        return await c.answer("Bu bo'lim faqat admin va ruxsat berilganlar uchun.", show_alert=True)
    data = c.data
    admin = post_bot.is_admin(u)
    if not admin and data != "gg:home":
        return await c.answer("Bu bo'lim faqat admin uchun.", show_alert=True)
    reset(u.id)
    if data == "gg:home":
        await c.answer()
        return await show(c, await home_view(u))
    if data.startswith("gg:tg:"):
        g = groups()
        key = data[6:]
        if key not in g:
            return await c.answer("Guruh topilmadi", show_alert=True)
        g[key]["on"] = not g[key].get("on")
        save_groups(g)
        await c.answer("🛡 Himoya yoqildi" if g[key]["on"] else "⏸ Himoya o'chirildi")
        if c.message and "Guruhlar" not in (c.message.text or ""):   # bot qo'shilgandagi xabardan bosildi
            return await c.message.edit_reply_markup(reply_markup=None)
        return await show(c, await home_view(u))
    if data == "gg:acl":
        await c.answer()
        return await show(c, await acl_view())
    if data.startswith("gg:del:"):
        i = int(data[7:])
        lst = acl()
        if 0 <= i < len(lst):
            e = lst.pop(i)
            save_acl(lst)
            await c.answer("❌ %s — ruxsat olib tashlandi" % post_bot.entry_name(e), show_alert=True)
        else:
            await c.answer()
        return await show(c, await acl_view())
    if data == "gg:add":
        grant_wait.add(u.id)
        await c.answer()
        return await c.message.answer(
            "➕ Ruxsat bermoqchi bo'lgan odamning <b>@username</b> ini yuboring yoki uning biror xabarini shu yerga "
            "<b>forward</b> qiling.\n\nBekor qilish: «-»", parse_mode=H)
    if data == "gg:set":
        await c.answer()
        return await show(c, await set_view())
    if data.startswith("gg:k:"):
        k = data[5:]
        r = restrict()
        if k in r:
            r[k] = not r[k]
            save_restrict(r)
        await c.answer()
        return await show(c, await set_view())
    if data == "gg:words":
        words_wait.add(u.id)
        await c.answer()
        cur = "\n".join(extra_words())
        return await c.message.answer(
            "✏️ Guruhda tegilsa yoki linki tashlansa bo'ladigan username va saytlarni yuboring, "
            "har qatorda bittasi. Masalan:\n<code>uzmacbook\nmagicpro.uz</code>\n\n"
            "Hozir: <code>%s</code>\nTozalash: «-»" % (html.escape(cur) or "—"), parse_mode=H)
    await c.answer()


@router.message(F.chat.type == "private",
                F.from_user.func(lambda u: u is not None and (u.id in grant_wait or u.id in words_wait)))
async def on_input(m: Message):
    """Admin ruxsat beriladigan odamni yoki ruxsat etilgan username/saytlarni yubordi."""
    uid = m.from_user.id
    if not post_bot.is_admin(m.from_user):
        reset(uid)
        return
    text = (m.text or "").strip()
    if uid in words_wait:
        words_wait.discard(uid)
        db.set_setting("guard.words", "" if text == "-" else text)
        await m.answer("✅ Saqlandi.")
        v = await set_view()
        return await m.answer(v[0], parse_mode=H, reply_markup=kb(v[1]), link_preview_options=NO_PREVIEW)
    if text == "-":
        grant_wait.discard(uid)
    else:
        e, err = post_bot.target_from(m)
        if err:
            return await m.answer("⚠️ " + err + "\nBekor qilish: «-»")
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
                    await ctx["bot"].send_message(
                        e["id"], "✅ Sizga guruhga reklama berish ruxsati berildi. Guruhdagi rasm, video va "
                                 "link cheklovlari sizga taalluqli emas.")
                    note = " Unga xabar yuborildi."
                except TelegramAPIError:
                    note = " (Unga xabar bora olmadi — botga /start bosmagan.)"
            await m.answer("✅ %s ga ruxsat berildi.%s" % (post_bot.entry_name(e), note))
    v = await acl_view()
    await m.answer(v[0], parse_mode=H, reply_markup=kb(v[1]), link_preview_options=NO_PREVIEW)


def setup(bot):
    ctx["bot"] = bot
    on = [v.get("title") for v in groups().values() if v.get("on") and not v.get("left")]
    log.info("GUARD: guruh himoyasi tayyor. Yoqilgan guruhlar: %s", ", ".join(on) or "yo'q")
