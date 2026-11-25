# -*- coding: utf-8 -*-
"""
«📢 Kanalga post» bo'limi sozlamalari.
Kanal, linklar va menejerlar botning o'zidan o'zgartiriladi: 📢 Kanalga post → ⚙️ Sozlamalar (faqat admin).
Bu yerda turgani - boshlang'ich qiymatlar. Muddatli to'lov foizlari admin paneldagi sozlamalardan olinadi.
"""

# «📢 Kanalga post» admini: Telegram @username yoki ID, vergul bilan. Admin boshqalarga ruxsat bera oladi.
# Serverdagi .env da POST_ADMINS=... yozilsa, o'sha ustun turadi.
ADMINS = "sherxonjumayev"

# ---------- Brendlar (har biriga o'z kanali va linklari) ----------
# Ikkinchi brend kerak bo'lsa, "magicpro" blokini ochib qo'ying (# belgilarini olib tashlang).
BRANDS = {
    "uzmacbook": {
        "name": "Uzmacbook",
        "channel": "",            # @kanal_username yoki -100xxxxxxxxxx (bot kanalda admin bo'lishi shart)
        "loc_text": "A-34 Hovli tomondan kirishda",
        "loc_url": "",            # Google/Yandex xarita linki
        "services_url": "",       # "Xizmatlar" posti linki
        "telegram_url": "",       # Telegram kanal linki
        "instagram_url": "",      # Instagram linki
        "managers": "910130770 | @sherxonjumayev",   # har qatorda bitta: telefon | @username
    },
    # "magicpro": {
    #     "name": "MagicPro",
    #     "channel": "",
    #     "loc_text": "A-34 Hovli tomondan kirishda",
    #     "loc_url": "",
    #     "services_url": "",
    #     "telegram_url": "",
    #     "instagram_url": "",
    #     "managers": "910130770 | @sherxonjumayev",
    # },
}

# ---------- Post matnlari (namunadagidek) ----------
TEXT = {
    "price_label": "Narxi:",
    "no_installment": "Muddatli tòlov yòq",
    # {down} - oldindan to'lov %, {monthly} - oylik to'lov (eng uzun muddat bo'yicha), {months} - eng uzun muddat.
    # Foizlar admin panel → Sozlamalar dagi "Muddatli to'lov" qiymatlaridan olinadi.
    "installment": "Muddatli tòlov bor: {down}% oldindan, oyiga {monthly} dan",
    "services_prefix": "Qoshimcha - ",
    "services_word": "Xizmatlar",
    "contact_title": "Murojaat uchun:",
    "follow_title": "Ijtimoiy tarmoqlarda bizni kuzating:",
    "sold": "🔴 SOTILDI",
}

EMOJI = {
    "location": "📍",
    "contact": "🔗",
    "telegram": "✈️",
    "instagram": "📷",
}

# ---------- Avtomatik to'ldirish qoidalari ----------
WARRANTY_M_CHIP = "90 kun"     # Apple M1/M2/M3/M4...
WARRANTY_INTEL = "30 kun"      # Intel
DEFAULT_KOMPLEKT = "Zaryadka!"
INSTALLMENT_DEFAULT = False    # yangi postda muddatli to'lov yoqilgan bo'lsinmi

# ---------- Tugmalardagi variantlar (Billz'dagi qiymatlar ham avtomatik qo'shiladi) ----------
OPTIONS = {
    "holat": ["A Category", "B Category", "C Category", "D Category"],
    "rang": ["Silver", "Space Gray", "Space Black", "Gold", "Midnight", "Starlight", "Sky Blue"],
    "kafolat": ["90 kun", "30 kun", "60 kun", "6 oy", "1 yil"],
    "komplekt": ["Zaryadka!", "Zaryadka + Quti!", "Faqat noutbuk", "Zaryadka + Quti + Hujjatlar!"],
}

# ---------- Billz maydon nomlari ----------
# Billz'dagi qo'shimcha maydon (custom field) yoki atribut nomida shu so'zlardan biri bo'lsa, o'sha qiymat olinadi.
# Bot noto'g'ri olsa: /maydon 0164 buyrug'i Billz'dagi asl maydonlarni ko'rsatadi, shu ro'yxatga qo'shib qo'yasiz.
BILLZ_FIELDS = {
    "holat": ["holat", "kategor", "category", "состояни", "grade", "sinf"],
    "rang": ["rang", "color", "colour", "цвет"],
    "ram": ["ram", "озу", "operativ", "оператив"],
    "ssd": ["ssd", "xotira", "storage", "накопит", "память", "disk", "hdd"],
    "battery": ["batar", "battery", "akb", "аккум", "health", "sog'lig"],
    "cycles": ["sikl", "cycle", "цикл"],
    "chip": ["protsessor", "processor", "процессор", "chip", "cpu"],
}
SKIP_FIELDS = ("seriya", "serial", "imei")

# Faqat shu kategoriyadagi tovarlar ro'yxatda chiqsin (masalan "Macbook"). Hammasi kerak bo'lsa: ""
CATEGORY_FILTER = ""

# ---------- Sotilganini kuzatish ----------
SYNC_MINUTES = 10      # har necha daqiqada Billz tekshiriladi
AUTO_PRICE = True      # Billz'da narx o'zgarsa, kanaldagi post narxi ham yangilansin
