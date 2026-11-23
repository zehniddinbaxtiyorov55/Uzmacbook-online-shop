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
