# Serverga o'rnatish (Airnet VDS, Ubuntu)

1. Domen DNS'iga 2 ta A yozuv: `shop.magicpro.uz` va `admin.magicpro.uz` → server IP.
2. Serverga kiring (`ssh root@SERVER_IP`) va:

```bash
curl -fsSL https://raw.githubusercontent.com/zehniddinbaxtiyorov55/Uzmacbook-online-shop/server/deploy/install.sh -o install.sh && bash install.sh
```

Skript so'raydi: BOT_TOKEN, BILLZ_SECRET_KEY, ADMIN_CHAT_ID, CASHBACK_API/KEY, REPORT_TO
(Render → Environment dan nusxa). Oxirida admin panel paroli chiqadi.

- Admin panel: https://admin.magicpro.uz (login: admin)
- Mini App: https://shop.magicpro.uz
- Sozlamalar: `/opt/onlineshop/.env` → o'zgartirgach `systemctl restart onlineshop`
- Baza (buyurtmalar, mijozlar): `/var/lib/onlineshop/shop.db`
- Loglar: `journalctl -u onlineshop -f`
- Yangilash: `bash /opt/onlineshop/deploy/install.sh` (manzillar `.env` dagi `WEBAPP_URL`/`ADMIN_HOST` dan olinadi)
- Manzilni almashtirish: `SHOP_DOMAIN=bot.magicpro.uz ADMIN_DOMAIN=admin.magicpro.uz bash /opt/onlineshop/deploy/install.sh`,
  keyin BotFather'da Mini App URL ni ham yangilang (`/myapps` → Edit Web App URL)
- Model rasmlari (admin panel → 📸 Model rasmlari): `/var/lib/onlineshop/model_photos/`

Bot Telegram webhook'ini faqat `https://shop.magicpro.uz` haqiqatan ishlaganda o'ziga o'tkazadi,
shuning uchun DNS tayyor bo'lguncha eski server ishlashda davom etadi. O'tgandan keyin Render'dagi
eski servisni **Suspend** qiling, aks holda u qayta yonganda webhook'ni o'ziga qaytarib oladi.

## AI chat-bot (Telegram Business + Gemini)

Kod yopiq repoda (`Uzmacbook-chat-bot-uchun-`, `server` branch). Serverda (root):

```bash
curl -fsSL https://raw.githubusercontent.com/zehniddinbaxtiyorov55/Uzmacbook-online-shop/server/deploy/install-ai.sh -o install-ai.sh && bash install-ai.sh
```

Skript GitHub uchun "deploy key" chiqaradi — uni repo → Settings → Deploy keys ga bir marta qo'shasiz.
So'ng BOT_TOKEN, GEMINI_API_KEY (Render → uzmacbook-ai-bot → Environment) so'raladi. Polling rejimi — domen kerak emas.
O'rnatgach Render'dagi `uzmacbook-ai-bot` ni **Suspend** qiling.

- Sozlamalar: `/opt/aibot/.env` → `systemctl restart aibot`
- Loglar: `journalctl -u aibot -f`
- Yangilash: `bash /opt/aibot-install.sh`

## 📢 Kanalga post (xodimlar uchun)

Botda `/start` → **📢 Kanalga post** tugmasi faqat admin va ruxsat berilganlarga ko'rinadi, mijozlar ko'rmaydi.

- Admin: `@sherxonjumayev` (`post_config.py` → `ADMINS`, yoki `.env` da `POST_ADMINS=user1,user2`)
- Admin **👥 Ruxsatlar** orqali boshqalarga ruxsat beradi: @username yuboradi yoki o'sha odamning xabarini forward qiladi.
- Birinchi marta: **⚙️ Sozlamalar** → kanal (bot kanalda admin bo'lishi shart), manzil, Xizmatlar, Telegram, Instagram linklari, menejerlar.
- Ishlatish: rasmlarni yuborish → artikulni tanlash yoki yozish (`0164`) → tayyor post chatga chiqadi →
  **✅ Tasdiqlash** (kanalga joylanadi) yoki **✏️ Tahrirlash** (sarlavha, holati, rangi, battery sikl/yomkost,
  xotira RAM/SSD, kafolat 90/30 kun, komplekt Zaryadka/Full box, narx, muddatli to'lov) → **✅ Tamom** → post qayta chiqadi.
- Tovar Billz'da sotilsa, kanaldagi postda narx ustidan o'zi chiziladi; Billz'da narx o'zgarsa post narxi ham yangilanadi.
- Billz maydonlarini tekshirish: `/maydon 0164`.
- Kod: `post_bot.py` (tugmalar va oqim), `post_format.py` (post matni), `post_config.py` (matnlar, variantlar).

## 📣 Guruhga reklama berish (guruh himoyasi)

Botni guruhga qo'shing va **admin** qiling («Xabarlarni o'chirish» va «Foydalanuvchilarni bloklash» huquqlari bilan). Bot adminga xabar yuboradi — **🛡 Himoyani yoqish** ni bosing.
Har bir guruhda himoya alohida yoqiladi (buyurtmalar/xodimlar guruhi tasodifan himoyalanib qolmaydi).

- Himoya yoqilgan guruhda cheklangan narsalar (rasm, video, link, boshqa @username) o'chiriladi va yuborgan odam tag qilinadi: «@username iltimos admindan ruxsat so'rang. Agar yana bir bor qaytarilsa ban beraman.» Ogohlantirish 1 daqiqadan keyin o'zi o'chadi.
- 30 kun ichida yana tashlasa — **ban** va uning guruhdagi barcha xabarlari o'chiriladi. Adminga xabar keladi, «♻️ Bandan chiqarish» tugmasi bilan. Albom (bir nechta rasm) va ogohlantirishdan keyingi 20 soniyadagi xabarlar bitta urinish hisoblanadi.
- Ban'ni Sozlamalarda o'chirib qo'ysa bo'ladi («🚫 Qayta tashlasa ban»).
- Ozod: admin, «Ruxsatlar» ro'yxati, guruh adminlari, anonim admin, guruhga bog'langan kanal, botlar.
- Panel: `/start` → **📣 Guruhga reklama berish** (faqat admin va ruxsat berilganlarga ko'rinadi) → guruhlar (himoyani yoqish/o'chirish), **👥 Ruxsatlar**, **⚙️ Sozlamalar** (nimani cheklash, ruxsat etilgan username va saytlar).
- Guruhda tezkor: odamning xabariga reply qilib `/ruxsat` yoki `/ruxsat_ol` (faqat admin).
- **Forward:** boshqa kanal/guruhdan forward qilingan xabarlar o'chiriladi. Faqat «👥 Ruxsatlar»ga qo'shilgan kanallar (Uzmacbook, MagicPro, reklama beruvchilar), post bo'limida ulangan kanal va guruhga bog'langan kanaldan forward qoladi.
- Kanalni ruxsatga qo'shish: Ruxsatlar → ➕ → kanaldan biror postni forward qiling yoki kanal @username / t.me linkini yuboring.
- Odamning xabarini forward qilsa — ichidagi rasm/link/username odatdagidek tekshiriladi.
- Guruh xabarlari do'kon botining boshqa qismlariga (salom javobi, post bo'limi, mijozlar bazasi) bormaydi.
- Kod: `group_guard.py`.
