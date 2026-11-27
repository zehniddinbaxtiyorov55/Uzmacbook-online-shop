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
    # Sotilganda narx ustidan chiziladi. Tepaga yozuv ham kerak bo'lsa, masalan: "🔴 SOTILDI"
    "sold": "",
}

# Oddiy emoji. Premium ikonkalar: 📢 Kanalga post → ⚙️ Sozlamalar → 📥 Namuna postdan olish
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
# Partiya (Billz'dagi «Partiya» maydoni) -> teg. Tahrirlashda shu tugmalar chiqadi.
PARTIYA = [("US", "#LLA"), ("UZ", "#UZ"), ("KR", "#KHA")]
INSTALLMENT_DEFAULT = False    # yangi postda muddatli to'lov yoqilgan bo'lsinmi

# ---------- «✏️ Tahrirlash» dagi tugmalar ----------
# (tugmada ko'rinadigan nom, postga yoziladigan qiymat)
KAFOLAT_OPTIONS = [("90 kun", "90 kun"), ("30 kun", "30 kun")]
NOMI_OPTIONS = ["Macbook Pro", "Macbook Air"]
DYUM_OPTIONS = ["13", "13.3", "13.6", "14", "15", "15.3", "16"]
KOMPLEKT_OPTIONS = [("Zaryadka", "Zaryadka!"), ("Full box", "Full box!")]
# Holati — postda 10 ballik baho, Billz'dagi kategoriyaga qarab.
# Tahrirlashda shu baholar tugma bo'lib chiqadi. Birinchisi — standart (Billz kategoriyasidan).
GRADE_SCORES = [
    ("A", ["9/10", "10/10"]),
    ("B", ["7/10", "8/10"]),
    ("C", ["5/10", "6/10", "4/10"]),
    ("D", ["3/10", "2/10", "1/10"]),
]
# Rangi: shu variantlar + Billz'dagi qiymatlar + «✍️ Qo'lda yozish»
OPTIONS = {
    "rang": ["Silver", "Space Gray", "Space Black", "Gold", "Midnight", "Starlight", "Sky Blue"],
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

# ---------- Ro'yxatda qaysi tovarlar chiqadi ----------
# Hozircha faqat MacBooklar. Telefon ham kerak bo'lsa: SHOW = ["macbook", "telefon"]
SHOW = ["macbook"]
# Guruhlar: tovar nomi, Billz kategoriyasi yoki artikulida shu so'zlardan biri bo'lsa — o'sha guruh.
# Aksessuarlar (chexol, zaryadka, plyonka, sumka...) hech qachon chiqmaydi (webapp.ACC_RX).
GROUPS = {
    "macbook": r"macbook|\bmbp\b|\bmba\b",
    "telefon": r"iphone|telefon|телефон|smartfon|смартфон|samsung|galaxy|pixel|redmi|xiaomi",
    "ipad": r"\bipad\b",
}

# ---------- Sotilganini kuzatish ----------
SYNC_MINUTES = 10      # har necha daqiqada Billz tekshiriladi
AUTO_PRICE = True      # Billz'da narx o'zgarsa, kanaldagi post narxi ham yangilansin
