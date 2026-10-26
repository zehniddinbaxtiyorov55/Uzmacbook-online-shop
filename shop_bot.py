"""Do'kon boti: faqat Mini App (Billz tovarlari), /start, /id, /kanal.
Javob beruvchi AI bot (bot.py) dan alohida ishlaydi."""
import asyncio, hashlib, logging, os, re
import aiohttp
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import webapp

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("BOT")

BOT_TOKEN = os.environ["BOT_TOKEN"]
BILLZ_SECRET = os.environ["BILLZ_SECRET_KEY"]
BILLZ_URL = os.environ.get("BILLZ_URL", "https://api-admin.billz.ai")
BILLZ_PLATFORM = os.environ.get(
    "BILLZ_PLATFORM_ID", "7d4a4c38-dd84-4902-b744-0488b80a4c01")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
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
def shop_kb(text="🛍 Do'konni ochish"):
    if not webapp.URL:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text=text, web_app=WebAppInfo(url=webapp.URL))]])


@dp.message(CommandStart())
async def on_start(m: Message):
    await m.answer("Assalomu alaykum! Magic Pro do'koniga xush kelibsiz. "
                   "Barcha MacBooklar, rasmlar va narxlar shu yerda 👇",
                   reply_markup=shop_kb())


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
    """Mini App'dagi "Raqamni ulashish" tugmasidan kelgan kontakt — faqat o'z raqami qabul qilinadi."""
    c = m.contact
    if m.from_user and c.user_id == m.from_user.id:
        digits = "".join(ch for ch in c.phone_number if ch.isdigit())
        webapp.PHONES[m.from_user.id] = "+" + digits
        log.info("BOT: telefon qabul qilindi: user %s", m.from_user.id)
    else:
        await m.answer("Iltimos, faqat o'zingizning raqamingizni yuboring.")


@dp.message()
async def on_any(m: Message):
    await m.answer("Do'konni ochish uchun pastdagi tugmani bosing 👇", reply_markup=shop_kb())


async def main():
    app = webapp.make_app(bot, billz_products, num)
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
