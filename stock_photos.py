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


# Apple qo'llab-quvvatlash sahifalaridagi rasmlar (support.apple.com: 108044, 108056, 108043, 109525)
APPLE = "https://cdsassets.apple.com/live/7WUAS350/images/"
DEVICES = [
    (re.compile(r"iphone\s*18\s*pro\s*max"), APPLE + "iphone/iphone-18-pro-max-colors.png"),
    (re.compile(r"iphone\s*18\s*pro"), APPLE + "iphone/iphone-18-pro-colors.png"),
    (re.compile(r"iphone\s*duo"), APPLE + "iphone/iphone-duo/iphone-duo-colors.png"),
    (re.compile(r"iphone\s*17\s*e\b|iphone\s*17e"), APPLE + "iphone/iphone-17e/iphone-17e-colors.png"),
    (re.compile(r"iphone\s*17\s*pro\s*max"), APPLE + "iphone/iphone-17-pro-max-colors.png"),
    (re.compile(r"iphone\s*17\s*pro"), APPLE + "iphone/iphone-17-pro-colors.png"),
    (re.compile(r"iphone\s*air"), APPLE + "iphone/iphone-air-colors.png"),
    (re.compile(r"iphone\s*17"), APPLE + "iphone/iphone-17-colors.png"),
    (re.compile(r"iphone\s*16\s*e\b|iphone\s*16e"), APPLE + "iphone/iphone-16e/iphone-16e-colors.png"),
    (re.compile(r"iphone\s*16\s*pro\s*max"), APPLE + "iphone/iphone-16-pro-max-colors.png"),
    (re.compile(r"iphone\s*16\s*pro"), APPLE + "iphone/iphone-16-pro-colors.png"),
    (re.compile(r"iphone\s*16\s*plus"), APPLE + "iphone/iphone-16-plus-colors.png"),
    (re.compile(r"iphone\s*16"), APPLE + "iphone/iphone-16-colors.png"),
    (re.compile(r"iphone\s*15\s*pro\s*max"), APPLE + "iphone/fall-2023-iphone-colors-iphone-15-pro-max.png"),
    (re.compile(r"iphone\s*15\s*pro"), APPLE + "iphone/fall-2023-iphone-colors-iphone-15-pro.png"),
    (re.compile(r"iphone\s*15\s*plus"), APPLE + "iphone/fall-2023-iphone-colors-iphone-15-plus.png"),
    (re.compile(r"iphone\s*15"), APPLE + "iphone/fall-2023-iphone-colors-iphone-15.png"),
    (re.compile(r"iphone\s*14\s*pro\s*max"), APPLE + "iphone/iphone-14-pro-max-colors.png"),
    (re.compile(r"iphone\s*14\s*pro"), APPLE + "iphone/iphone-14-pro-colors.png"),
    (re.compile(r"iphone\s*14\s*plus"), APPLE + "iphone/iphone-14-plus-colors-spring-2023.png"),
    (re.compile(r"iphone\s*14"), APPLE + "iphone/iphone-14-colors-spring-2023.png"),
    (re.compile(r"iphone\s*13\s*pro\s*max"), APPLE + "iphone/2022-spring-iphone13-pro-max-colors.png"),
    (re.compile(r"iphone\s*13\s*pro"), APPLE + "iphone/2022-spring-iphone13-pro-colors.png"),
    (re.compile(r"iphone\s*13\s*mini"), APPLE + "iphone/2022-iphone13-mini-colors.png"),
    (re.compile(r"iphone\s*13"), APPLE + "iphone/2022-spring-iphone13-colors.png"),
    (re.compile(r"iphone\s*12\s*pro\s*max"), APPLE + "iphone/iphone-12-pro-max/iphone12-pro-max-colors.jpg"),
    (re.compile(r"iphone\s*12\s*pro"), APPLE + "iphone/iphone-12-pro/iphone12-pro-colors.jpg"),
    (re.compile(r"iphone\s*12\s*mini"), APPLE + "iphone/2021-iphone12-mini-colors.png"),
    (re.compile(r"iphone\s*12"), APPLE + "iphone/2021-iphone12-colors.png"),
    (re.compile(r"iphone\s*11\s*pro\s*max"), APPLE + "iphone/identify-iphone-11pro-max.jpg"),
    (re.compile(r"iphone\s*11\s*pro"), APPLE + "iphone/identify-iphone-11pro.jpg"),
    (re.compile(r"iphone\s*11"), APPLE + "iphone/identify-iphone-11-colors.jpg"),
    (re.compile(r"iphone\s*se.*(3|2022)"), APPLE + "iphone/iphone-se-3rd-gen-colors.png"),
    (re.compile(r"iphone\s*se"), APPLE + "iphone/iphone-se/iphone-se-2nd-gen-colors.jpg"),
    (re.compile(r"ultra\s*4"), APPLE + "apple-watch/apple-watch-ultra-4.png"),
    (re.compile(r"ultra\s*3"), APPLE + "apple-watch/apple-watch-ultra-3-colors.png"),
    (re.compile(r"ultra\s*2"), APPLE + "apple-watch/apple-watch-ultra-2-colors.png"),
    (re.compile(r"watch.*ultra|ultra.*watch|\baw\s*ultra"), APPLE + "apple-watch/fall-2022-apple-watch-ultra.png"),
    (re.compile(r"(watch|\baw)\s*(series\s*|s)?12\b"), APPLE + "apple-watch/apple-watch-series-12-aluminum-gps.png"),
    (re.compile(r"(watch|\baw)\s*(series\s*|s)?11\b"), APPLE + "apple-watch/apple-watch-series-11-aluminum-gps.png"),
    (re.compile(r"(watch|\baw)\s*(series\s*|s)?10\b"), APPLE + "apple-watch/apple-watch-series-10-aluminum-gps.png"),
    (re.compile(r"(watch|\baw)\s*(series\s*|s)?9\b"), APPLE + "apple-watch/apple-watch-series-9-gps.png"),
    (re.compile(r"(watch|\baw)\s*(series\s*|s)?8\b"), APPLE + "apple-watch/fall-2022-watch-series8-aluminum-gps.png"),
    (re.compile(r"(watch|\baw)\s*(series\s*|s)?7\b"), APPLE + "apple-watch/2021-apple-watch-series7-aluminum-gps.png"),
    (re.compile(r"(watch|\baw)\s*(series\s*|s)?6\b"), APPLE + "apple-watch/apple-watch-series6-aluminum-gps-colors.png"),
    (re.compile(r"(watch|\baw)\s*(series\s*|s)?5\b"), APPLE + "apple-watch/series5-apple-watch-aluminum-gps.png"),
    (re.compile(r"(watch|\baw)\s*(series\s*|s)?4\b"), APPLE + "apple-watch/series4-apple-watch-aluminum-gps.png"),
    (re.compile(r"(watch|\baw)\s*se\s*3"), APPLE + "apple-watch/apple-watch-se-3.png"),
    (re.compile(r"(watch|\baw)\s*se\s*(2|2022)"), APPLE + "apple-watch/fall-2022-watch-series8-se-gps.png"),
    (re.compile(r"(watch|\baw)\s*se"), APPLE + "apple-watch/apple-watch-series6-000-aluminum-gps-colors.png"),
    (re.compile(r"apple\s*watch"), APPLE + "apple-watch/apple-watch-series-10-aluminum-gps.png"),
    (re.compile(r"ipad\s*air.*13.*m4|ipad\s*air.*m4.*13"), APPLE + "ipad/spring-2026-ipad-air-13.png"),
    (re.compile(r"ipad\s*air.*m4"), APPLE + "ipad/spring-2026-ipad-air-11.png"),
    (re.compile(r"ipad\s*pro.*13.*m5|ipad\s*pro.*m5.*13"), APPLE + "ipad/fall-2025-ipad-pro-m5-13in.png"),
    (re.compile(r"ipad\s*pro.*m5"), APPLE + "ipad/fall-2025-ipad-pro-m5-11in.png"),
    (re.compile(r"ipad\s*air.*13.*m3|ipad\s*air.*m3.*13"), APPLE + "ipad/spring-2025-ipad-air-13.png"),
    (re.compile(r"ipad\s*air.*m3"), APPLE + "ipad/spring-2025-ipad-air-11.png"),
    (re.compile(r"ipad\s*pro.*13.*m4|ipad\s*pro.*m4.*13"), APPLE + "ipad/spring-2024-1.png"),
    (re.compile(r"ipad\s*pro.*m4"), APPLE + "ipad/spring-2024-2.png"),
    (re.compile(r"ipad\s*air.*13.*m2|ipad\s*air.*m2.*13"), APPLE + "ipad/spring-2024-3.png"),
    (re.compile(r"ipad\s*air.*m2"), APPLE + "ipad/spring-2024-4.png"),
    (re.compile(r"ipad\s*mini.*(a17|7|2024)"), APPLE + "ipad/ipad-mini/ipad-mini-2024-colors.png"),
    (re.compile(r"ipad\s*mini"), APPLE + "ipad/ipad/ipad-mini-2021-colors.png"),
    (re.compile(r"ipad\s*pro.*12[.,]9.*(m2|6)"), APPLE + "ipad/ipad/fall-2022-12-9-inch-6gen-ipad-pro.png"),
    (re.compile(r"ipad\s*pro.*11.*(m2|4)"), APPLE + "ipad/ipad/fall-2022-11-inch-4gen-ipad-pro.png"),
    (re.compile(r"ipad\s*pro.*12[.,]9"), APPLE + "ipad/ipad/2021-ipad-pro-12-9-colors.png"),
    (re.compile(r"ipad\s*pro"), APPLE + "ipad/ipad/2021-ipad-pro-11-colors.png"),
    (re.compile(r"ipad\s*air.*(5|m1)"), APPLE + "ipad/ipad-air-5th-gen-colors.png"),
    (re.compile(r"ipad\s*air"), APPLE + "ipad/ipad/ipad-air-4th-gen-colors.png"),
    (re.compile(r"ipad.*(a16|11)"), APPLE + "ipad/spring-2025-ipad.png"),
    (re.compile(r"ipad.*10"), APPLE + "ipad/ipad/fall-2022-10-gen-ipad.png"),
    (re.compile(r"ipad.*9"), APPLE + "ipad/ipad/ipad-2021-colors.png"),
    (re.compile(r"ipad"), APPLE + "ipad/spring-2025-ipad.png"),
    (re.compile(r"airpods\s*pro\s*3"), APPLE + "airpods/charging-case-for-airpods-pro-3.png"),
    (re.compile(r"airpods\s*pro\s*2|airpods\s*pro.*usb"), APPLE + "airpods/airpods-pro-magsafe-charging-case-usb-c.png"),
    (re.compile(r"airpods\s*pro"), APPLE + "airpods/airpods-pro-charging-case-magsafe-charging-case.png"),
    (re.compile(r"airpods\s*5"), APPLE + "airpods/charging-case-for-airpods-5.png"),
    (re.compile(r"airpods\s*4.*(anc|noise|shovq)"), APPLE + "airpods/wireless-charging-case-for-airpods-4.png"),
    (re.compile(r"airpods\s*4"), APPLE + "airpods/charging-case-for-airpods-4.png"),
    (re.compile(r"airpods\s*3"), APPLE + "airpods/airpods-lightning-charging-case-magsafe-charging-case-3rd-generation.png"),
    (re.compile(r"airpods\s*(2|1)?\b(?!\s*max)"), APPLE + "airpods/airpods-wireless-charging-case.png"),
]


def _color(text):
    for rx, c in COLORS:
        if re.search(rx, text):
            return c
    return ""


def stock_photos(name, details):
    text = (name + " " + " ".join(v for _, v in details)).lower()
    if "macbook" not in text and not re.search(r"\b(mba|mbp)\b", text):
        if re.search(r"ipad|airpods|watch|\baw\b", text) or re.search(r"iphone", text):
            for rx, url in DEVICES:
                if rx.search(text):
                    return [url]
        if not re.search(r"\b(air|pro)\b.*\bm[1-5]\b", text):
            return []
    size = "16" if re.search(r"\b16\b|16[\"”']|16 ?inch|16 ?dyuym", name.lower()) else \
        ("15" if re.search(r"\b15\b|15[\"”']", name.lower()) else "14" if "pro" in text else "13")
    text = re.sub(r"\bmbp\b", "macbook pro", re.sub(r"\bmba\b", "macbook air", text))
    want = _color(text)
    for rx, tpl, colors in MODELS:
        if re.search(rx, text):
            pick = want.replace("space-gray", "spacegray") if "mbp" in tpl else want.replace("spacegray", "space-gray")
            if pick == "spaceblack" and "spaceblack" not in colors:
                pick = "spacegray"
            order = ([pick] if pick in colors else []) + [c for c in colors if c != pick]
            return [BASE + tpl.format(size=size, c=c) + Q for c in order[:3]]
    return []
