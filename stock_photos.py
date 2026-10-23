"""Billz'da rasmi yo'q tovarlar uchun Apple saytidagi namunaviy rasm.
Model va rangni nomidan/xususiyatlaridan topadi. Bir nechta variant beradi:
birinchisi ochilmasa, brauzer keyingisini oladi."""
import re

BASE = "https://store.storeimages.cdn-apple.com/4982/as-images.apple.com/is/"
Q = "?wid=904&hei=840&fmt=jpeg&qlt=90"

# rang so'zlari -> Apple fayl nomidagi rang
COLORS = [
    (r"space\s*black|qora", "spaceblack"),
    (r"space\s*gr[ae]y|kulrang|grey|gray|seriy", "space-gray"),
    (r"midnight|to'q ko'k|tungi", "midnight"),
    (r"starlight|oq-tilla|zvezd", "starlight"),
    (r"sky\s*blue|havorang", "skyblue"),
    (r"silver|kumush|oq\b|white", "silver"),
    (r"gold|tilla|oltin|zoloto", "gold"),
]

# (nomga mos regex, fayl nomi shabloni, mavjud ranglar)
MODELS = [
    (r"air.*(m4)", "mba{size}-{c}-select-202503", ["skyblue", "silver", "starlight", "midnight"]),
    (r"air.*15.*m3|air.*m3.*15", "mba15-{c}-select-202402", ["midnight", "starlight", "space-gray", "silver"]),
    (r"air.*m3", "mba13-{c}-select-202402", ["midnight", "starlight", "space-gray", "silver"]),
    (r"air.*15.*m2|air.*m2.*15", "mba15-{c}-select-202306", ["midnight", "starlight", "space-gray", "silver"]),
    (r"air.*m2", "macbook-air-{c}-select-20220606", ["midnight", "starlight", "space-gray", "silver"]),
    (r"air", "macbook-air-{c}-select-201810", ["space-gray", "silver", "gold"]),
    (r"pro.*m4", "mbp{size}-{c}-select-202410", ["spaceblack", "silver"]),
    (r"pro.*m3\s*(pro|max)", "mbp{size}-{c}-select-202310", ["spaceblack", "silver"]),
    (r"pro.*m3", "mbp14-{c}-select-202310", ["spacegray", "silver"]),
    (r"pro.*m2\s*(pro|max)", "mbp{size}-{c}-select-202301", ["spacegray", "silver"]),
    (r"pro.*(m1\s*(pro|max))", "mbp{size}-{c}-select-202110", ["spacegray", "silver"]),
    (r"pro.*m2", "mbp-{c}-select-202206", ["spacegray", "silver"]),
    (r"pro.*m1", "mbp-{c}-select-202011", ["spacegray", "silver"]),
    (r"pro", "mbp14-{c}-select-202110", ["spacegray", "silver"]),
]


def _color(text):
    for rx, c in COLORS:
        if re.search(rx, text):
            return c
    return ""


def stock_photos(name, details):
    text = (name + " " + " ".join(v for _, v in details)).lower()
    if "macbook" not in text and not re.search(r"\b(air|pro)\b.*\bm[1-4]\b", text):
        return []
    size = "16" if re.search(r"\b16\b|16[\"”']|16 ?inch|16 ?dyuym", name.lower()) else \
        ("15" if re.search(r"\b15\b|15[\"”']", name.lower()) else "14" if "pro" in text else "13")
    want = _color(text)
    for rx, tpl, colors in MODELS:
        if re.search(rx, text):
            pick = want.replace("space-gray", "spacegray") if "mbp" in tpl else want.replace("spacegray", "space-gray")
            if pick == "spaceblack" and "spaceblack" not in colors:
                pick = "spacegray"
            order = ([pick] if pick in colors else []) + [c for c in colors if c != pick]
            return [BASE + tpl.format(size=size, c=c) + Q for c in order[:3]]
    return []
