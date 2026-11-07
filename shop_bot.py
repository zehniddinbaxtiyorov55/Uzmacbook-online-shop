"""Do'kon boti: Mini App (Billz tovarlari), /start, /id, /kanal, /hisobot (kunlik savdo hisoboti).
Javob beruvchi AI bot (bot.py) dan alohida ishlaydi."""
import asyncio, hashlib, logging, os, re
import aiohttp
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
                           ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, WebAppInfo)
import report
import webapp

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("BOT")

BOT_TOKEN = os.environ["BOT_TOKEN"]
BILLZ_SECRET = os.environ["BILLZ_SECRET_KEY"]
BILLZ_URL = os.environ.get("BILLZ_URL", "https://api-admin.billz.ai")
BILLZ_PLATFORM = os.environ.get(
    "BILLZ_PLATFORM_ID", "7d4a4c38-dd84-4902-b744-0488b80a4c01")

# Cashback balansi: cashback Apps Script'ning /exec manzili (?phone=...&key=... -> {"text": ...})
CASHBACK_API = os.environ.get("CASHBACK_API", "").strip()
CASHBACK_KEY = os.environ.get("CASHBACK_KEY", "").strip()
# "Savollar va takliflar" tugmasi shu lichkaga olib boradi
QUESTIONS_CONTACT = os.environ.get("QUESTIONS_CONTACT", "sherxonjumayev").lstrip("@")

BOT_NAME = "Uzmacbook / MagicPro.uz"

WELCOME = (
    "Assalomu alaykum! \U0001F44B\n"
    "%s rasmiy botiga xush kelibsiz.\n\n"
    "Bu bot orqali:\n"
    "• MacBooklarni ko'rish va buyurtma berish\n"
    "• Muddatli to'lov shartlarini bilish\n"
    "• Garantiya shartlari\n"
    "• 24/7 servis\n"
    "• Cashback hisobingizni tekshirish\n"
    "• Savol va takliflaringizni yuborish\n\n"
    "Kerakli bo'limni tanlang \U0001F447" % BOT_NAME)

INSTALL_TEXT = (
    "\U0001F4B3 Muddatli to'lov shartlari\n\n"
    "Muddatli to'lov hozircha faqat MacBooklar uchun.\n\n"
    "• Mahsulot narxining 50% i oldindan to'lanadi.\n"
    "• Qolgan summa 3 oydan 8 oygacha teng bo'lib to'lanadi.\n"
    "• Har bir oy uchun mahsulot narxining 6% i ustama qo'shiladi.\n\n"
    "Misol — $2000 lik MacBook, 3 oyga:\n"
    "• Oldindan (50%): $1000\n"
    "• Ustama: har oy 6% × 3 oy = narxning 18% i = $360\n"
    "• Bo'lib to'lanadigan qism: $1000 + $360 = $1360\n"
    "• Oyiga: $1360 ÷ 3 ≈ $453\n"
    "• Umumiy: $2360\n\n"
    "Har bir muddat uchun aniq oylik to'lovni \U0001F6CD Online do'kondan ko'rishingiz mumkin.")

WARRANTY_TEXT = (
    "\U0001F6E1 Garantiya va savdo kelishuvi\n\n"
    "• Kafolat muddati — 3 oy.\n"
    "• Agar 3 kun ichida mahsulotda yoki uning ishida muammo chiqsa, "
    "pulingiz to'liq (tiyinigacha) qaytariladi.\n\n"
    "Qo'shimcha savollar bo'lsa, ✍ Savollar va takliflar orqali menejerga yozing.")

# 24/7 servis matnini Render > Environment > SERVICE_TEXT orqali qo'yish mumkin
SERVICE_TEXT = os.environ.get("SERVICE_TEXT", "").strip() or (
    "\U0001F527 24/7 Servis\n\n"
    "Bizdan MacBook olgan bo'lsangiz, servis (ta'mirlash) xarajatlarini do'kon "
    "o'z zimmasiga oladi. Qoplanadigan summa MacBook narxiga bog'liq:\n\n"
    "\U0001F4BB 600$ gacha — 600 000 so'mgacha\n"
    "\U0001F4BB 601–1000$ — 1 000 000 so'mgacha\n"
    "\U0001F4BB 1001–1500$ — 1 500 000 so'mgacha\n"
    "\U0001F4BB 1500$ dan yuqori — 1 800 000 so'mgacha\n\n"
    "✅ Nosozlik kimning aybi bilan chiqqanidan qat'i nazar qoplanadi — "
    "hatto o'zingizning aybingiz bilan bo'lsa ham.\n"
    "☝ Qoplash bir marta amalga oshiriladi.\n\n"
    "Muammo chiqsa, kunning istalgan vaqtida ✍ Savollar va takliflar orqali "
    "yozing — yordam beramiz.")

INFO = {"install": INSTALL_TEXT, "warranty": WARRANTY_TEXT, "service": SERVICE_TEXT}

cashback_pending = set()  # cashback uchun raqam kutilayotgan user_id lar
cashback_info = {}        # user_id -> oxirgi balans ma'lumoti ("Nega cashback yo'q?" uchun)

CASHBACK_HOW = (
    "\U0001F4B0 Cashback qanday ishlaydi?\n\n"
    "1️⃣ Bizdan MacBook olganingizda sizga shaxsiy promokod beriladi.\n"
    "2️⃣ Do'stingiz shu promokod bilan MacBook olsa, ikkalangizga ham cashback yoziladi.\n"
    "3️⃣ Promokod 3 oy amal qiladi va 2 ta do'st uchun ishlaydi.\n"
    "4️⃣ To'plangan cashbackni keyingi xaridingizda ishlatasiz.\n\n"
    "Hisobingizni ko'rish uchun pastdagi tugma orqali raqamingizni yuboring \U0001F447")

NOT_BOUGHT = (
    "Siz hali bizdan MacBook olmagansiz — demak eng foydali qismi hali oldinda \U0001F642\n\n"
    "\U0001F381 Bizdan MacBook olsangiz:\n"
    "• shaxsiy promokodingiz bo'ladi;\n"
    "• do'stingiz shu kod bilan MacBook olsa, sizga ham, unga ham cashback yoziladi "
    "(2 ta do'stgacha);\n"
    "• to'plangan cashback bilan keyingi xaridingiz arzonroq tushadi.\n\n"
    "Ya'ni MacBookni bir marta olasiz, foydasi esa keyin ham kelaveradi.\n\n"
    "\U0001F6E1 3 oy kafolat, \U0001F527 24/7 servis va \U0001F4B3 bo'lib to'lash ham bor.\n\n"
    "\U0001F447 O'zingizga mos MacBookni \U0001F6CD Online do'kondan tanlang.\n\n"
    "(Agar bizdan xarid qilgan bo'lsangiz, xaridda boshqa raqam yozilgan bo'lishi mumkin — "
    "✍ Savollar va takliflar orqali yozing.)")


def parse_cashback(text):
    """Apps Script javob matnidan kerakli ma'lumotlarni ajratadi."""
    t = text or ""
    if "topilmadi" in t:
        return {"found": False}

    def money(rx):
        mm = re.search(rx, t)
        return float(mm.group(1)) if mm else 0.0
    friends = [int(x) for x in re.findall(r"do'stlar:\s*(\d+)", t)]
    return {
        "found": True,
        "left": money(r"Hisobingizdagi cashback:\s*\$([\d.]+)"),
        "used": money(r"ishlatilgan:\s*\$([\d.]+)"),
        "codes": re.findall(r"Promokod:\s*(\S+)", t),
        "statuses": [s.strip() for s in re.findall(r"Holati:\s*([^\n(]+)", t)],
        "friends": sum(friends),
    }


def why_no_cashback(info):
    lines = ["❓ Nega cashback yo'q?\n",
             "Cashback o'zingizning xaridingiz uchun berilmaydi. U faqat do'stingiz "
             "sizning promokodingiz bilan MacBook olganda yoziladi."]
    codes = info.get("codes") or []
    active = any(s.lower().startswith("faol") for s in info.get("statuses") or [])
    code = codes[0] if codes else ""
    if info.get("used", 0) > 0:
        lines.append("• Avval yozilgan cashbackingiz ($%s) keyingi xaridingizda ishlatilgan."
                     % ("%g" % info["used"]))
    if info.get("friends", 0) == 0:
        if code and active:
            lines.append("• Hozircha promokodingiz (%s) bilan hech kim xarid qilmagan. "
                         "Uni do'stlaringizga yuboring." % code)
        elif code:
            lines.append("• Promokodingiz (%s) muddati tugagan yoki faol emas." % code)
        else:
            lines.append("• Promokodingiz hali berilmagan.")
    else:
        lines.append("• Do'stingiz yaqinda xarid qilgan bo'lsa, cashback hisobga biroz "
                     "kechroq tushishi mumkin.")
    if not active and info.get("friends", 0) >= 2:
        lines.append("• Promokod 2 ta do'st uchun ishlatib bo'lingan.")
    lines.append("\n\U0001F4A1 Muhim: do'stingiz xarid paytida promokodni sotuvchiga aytishi shart, "
                 "aks holda cashback yozilmaydi.")
    lines.append("Savol bo'lsa: ✍ Savollar va takliflar.")
    return "\n".join(lines)

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
dp.message.outer_middleware(report.remember_mw)  # hisobot @username orqali topilishi uchun
billz = {"token": ""}


# ---------- Billz ----------
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


async def billz_login(session):
    async with session.post(BILLZ_URL + "/v1/auth/login",
                            json={"secret_token": BILLZ_SECRET},
                            headers={"platform-id": BILLZ_PLATFORM}) as r:
        body = await r.json(content_type=None)
        if r.status != 200:
            raise RuntimeError("login status=%s body=%s" % (r.status, str(body)[:200]))
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    token = data.get("access_token") or data.get("token")
    if not token:
        raise RuntimeError("login javobida token yo'q")
    billz["token"] = token


async def billz_get(session, params):
    for attempt in (1, 2):
        if not billz["token"]:
            await billz_login(session)
        headers = {"Authorization": "Bearer " + billz["token"], "platform-id": BILLZ_PLATFORM}
        async with session.get(BILLZ_URL + "/v2/products", params=params, headers=headers) as r:
            if r.status == 401 and attempt == 1:
                billz["token"] = ""
                continue
            body = await r.json(content_type=None)
            if r.status != 200:
                raise RuntimeError("products status=%s body=%s" % (r.status, str(body)[:200]))
            return body


async def billz_products(include_empty, max_pages):
    out = []
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
        for page in range(1, max_pages + 1):
            body = await billz_get(session, {
                "page": page, "limit": 100,
                "include_empty_stocks": "true" if include_empty else "false"})
            items = body.get("products") or []
            out.extend(items)
            if len(items) < 100:
                break
    return out


# ---------- Telegram ----------
def main_menu():
    rows = []
    if webapp.URL:
        rows.append([InlineKeyboardButton(
            text="🛍 Online do'kon", web_app=WebAppInfo(url=webapp.URL))])
    rows.append([
        InlineKeyboardButton(text="💳 Muddatli to'lov", callback_data="info:install"),
        InlineKeyboardButton(text="🛡 Garantiya", callback_data="info:warranty"),
    ])
    rows.append([
        InlineKeyboardButton(text="🔧 24/7 Servis", callback_data="info:service"),
        InlineKeyboardButton(text="💰 Cashbackim", callback_data="cash:start"),
    ])
    rows.append([InlineKeyboardButton(
        text="✍️ Savollar va takliflar", url="https://t.me/%s" % QUESTIONS_CONTACT)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text="⬅️ Menyu", callback_data="menu")]])


async def fetch_cashback(phone):
    """Cashback Apps Script'dan balans matnini oladi. Ulanmasa yoki xato bo'lsa None."""
    if not CASHBACK_API:
        return None
    params = {"phone": phone}
    if CASHBACK_KEY:
        params["key"] = CASHBACK_KEY
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as s:
            async with s.get(CASHBACK_API, params=params) as r:
                data = await r.json(content_type=None)
        if isinstance(data, dict):
            return data.get("text")
    except Exception:
        log.exception("BOT: cashback API xatosi")
    return None


@dp.message(CommandStart())
async def on_start(m: Message):
    await m.answer(WELCOME, reply_markup=main_menu())


@dp.callback_query(F.data.startswith("info:"))
async def on_info(c: CallbackQuery):
    text = INFO.get(c.data.split(":", 1)[1])
    if text:
        try:
            await c.message.edit_text(text, reply_markup=back_kb())
        except Exception:
            await c.message.answer(text, reply_markup=back_kb())
    await c.answer()


@dp.callback_query(F.data == "menu")
async def on_menu(c: CallbackQuery):
    try:
        await c.message.edit_text(WELCOME, reply_markup=main_menu())
    except Exception:
        await c.message.answer(WELCOME, reply_markup=main_menu())
    await c.answer()


@dp.callback_query(F.data == "cash:start")
async def on_cash(c: CallbackQuery):
    cashback_pending.add(c.from_user.id)
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Raqamni yuborish", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True)
    await c.message.answer(CASHBACK_HOW, reply_markup=kb)
    await c.answer()


@dp.callback_query(F.data == "cash:why")
async def on_cash_why(c: CallbackQuery):
    info = cashback_info.get(c.from_user.id)
    if not info:
        await c.message.answer("Avval 💰 Cashbackim orqali raqamingizni yuboring.",
                               reply_markup=main_menu())
    else:
        await c.message.answer(why_no_cashback(info), reply_markup=main_menu())
    await c.answer()


@dp.message(Command("id"))
async def on_id(m: Message):
    await m.answer("Chat ID: %s" % m.chat.id)


@dp.message(Command("kanal"))
async def on_kanal(m: Message, command: CommandObject):
    if not webapp.ADMIN:
        await m.answer("Avval Render → Environment ga ADMIN_CHAT_ID = %s qo'shing." % m.chat.id)
        return
    if str(m.chat.id) != webapp.ADMIN.strip():
        await m.answer("Bu buyruq faqat do'kon egasi uchun.")
        return
    ch = (command.args or "").strip()
    if not ch:
        await m.answer("Shunday yozing: /kanal @kanal_username")
        return
    try:
        me = await bot.get_me()
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
            text="🛍 Do'kon", url="https://t.me/%s?startapp" % me.username)]])
        msg = await bot.send_message(ch, "Do'konimizdan xarid qiling 👇", reply_markup=kb)
        await bot.pin_chat_message(ch, msg.message_id, disable_notification=True)
        await m.answer("Tayyor! Kanalga joylandi va qadaldi.")
    except Exception as e:
        await m.answer("Xato: %s\nBot kanalda adminmi?" % e)


@dp.message(F.contact)
async def on_contact(m: Message):
    """Kontakt: Mini App buyurtmasi uchun raqam saqlanadi; cashback so'ralgan bo'lsa balans ko'rsatiladi."""
    c = m.contact
    if not (m.from_user and c.user_id == m.from_user.id):
        await m.answer("Iltimos, faqat o'zingizning raqamingizni yuboring.")
        return
    phone = "+" + "".join(ch for ch in c.phone_number if ch.isdigit())
    webapp.PHONES[m.from_user.id] = phone
    log.info("BOT: telefon qabul qilindi: user %s", m.from_user.id)
    if m.from_user.id in cashback_pending:
        cashback_pending.discard(m.from_user.id)
        text = await fetch_cashback(phone)
        if not text:
            await m.answer("Hozircha cashback xizmatiga ulana olmadim. Birozdan keyin qayta "
                           "urinib ko'ring yoki ✍️ Savollar va takliflar orqali yozing.",
                           reply_markup=ReplyKeyboardRemove())
            await m.answer("Yana nimadir kerakmi?", reply_markup=main_menu())
            return
        info = parse_cashback(text)
        if not info["found"]:
            await m.answer("Tekshirdim 👌", reply_markup=ReplyKeyboardRemove())
            await m.answer(NOT_BOUGHT, reply_markup=main_menu())
            return
        cashback_info[m.from_user.id] = info
        await m.answer(text, reply_markup=ReplyKeyboardRemove())
        kb = main_menu()
        if info["left"] <= 0:
            kb.inline_keyboard.insert(0, [InlineKeyboardButton(
                text="❓ Nega cashback yo'q?", callback_data="cash:why")])
            await m.answer("Hisobingizda hozircha cashback yo'q. Sababini bilish uchun "
                           "pastdagi tugmani bosing 👇", reply_markup=kb)
        else:
            await m.answer("Yana nimadir kerakmi?", reply_markup=kb)


@dp.message(Command("hisobot"))
async def on_hisobot(m: Message, command: CommandObject):
    """Kunlik savdo hisoboti (report.py). Faqat REPORT_TO dagilar va ADMIN uchun."""
    if not await report.on_command(m, command.args or ""):
        await on_any(m)


@dp.message()
async def on_any(m: Message):
    await m.answer(WELCOME, reply_markup=main_menu())


async def main():
    app = webapp.make_app(bot, billz_products, num)
    try:
        report.setup(app, bot, billz_login, billz, BILLZ_URL, BILLZ_PLATFORM, num, webapp.URL, webapp.ADMIN)
    except Exception:
        log.exception("BOT: kunlik hisobotni ulab bo'lmadi")
    secret = hashlib.sha256(BOT_TOKEN.encode()).hexdigest()[:32]
    if webapp.URL:
        # Webhook: Telegram xabari kelganda server o'zi uyg'onadi (Render bepul tarifi uchun)
        SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=secret).register(
            app, path="/tg/" + secret)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", "8080"))
    await web.TCPSite(runner, "0.0.0.0", port).start()
    log.info("BOT: server port %s da ishga tushdi", port)
    await webapp.set_menu(bot)
    try:
        report.start()  # har kuni 22:00 hisobot + server uxlab qolmasligi
    except Exception:
        log.exception("BOT: kunlik hisobot jadvalini ishga tushirib bo'lmadi")
    if webapp.URL:
        await bot.set_webhook(webapp.URL + "tg/" + secret, secret_token=secret,
                              allowed_updates=dp.resolve_used_update_types())
        log.info("BOT: webhook rejimi: %s", webapp.URL)
        asyncio.create_task(webapp.load())
        webapp.usd_rate()  # kursni orqa fonda yuklashni boshlaydi
        await asyncio.Event().wait()
    else:
        await bot.delete_webhook()
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
