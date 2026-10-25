"""Billz'da rasmi yo'q tovarlar uchun Apple'ning rasmiy namunaviy rasmi.
Hamma manzillar Apple Support "Identify your ..." sahifalaridan olingan (taxmin emas)."""
import re

APPLE = "https://cdsassets.apple.com/live/7WUAS350/images/"
MA = APPLE + "macbook-air/"
MP = APPLE + "macbook-pro/"

# iPhone / Watch / iPad / AirPods — support.apple.com 108044, 108056, 108043, 109525
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
    (re.compile(r"(watch|\baw\b).*ultra\s*4\b(?!\d|\s*mm)"), APPLE + "apple-watch/apple-watch-ultra-4.png"),
    (re.compile(r"(watch|\baw\b).*ultra\s*3\b(?!\d|\s*mm)"), APPLE + "apple-watch/apple-watch-ultra-3-colors.png"),
    (re.compile(r"(watch|\baw\b).*ultra\s*2\b(?!\d|\s*mm)"), APPLE + "apple-watch/apple-watch-ultra-2-colors.png"),
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
    (re.compile(r"(watch|\baw)\s*(series\s*|s)?3\b(?!\d|\s*mm)"), APPLE + "apple-watch/series4-apple-watch-aluminum-gps.png"),
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



def _size(t):
    """Ekran o'lchami: 13/14/15/16. "16/512" kabi xotira yozuvlarini e'tiborsiz qoldiradi."""
    m = re.search(r"\b(13|14|15|16)(?:[.,]\d)?\s*(?:\"|”|''|-?inch|dyuym|дюйм)", t)
    if m:
        return m.group(1)
    m = re.search(r"\b(13[.,][36]|14[.,]2|15[.,][34]|16[.,]2)\b", t)
    if m:
        return m.group(1)[:2]
    for m in re.finditer(r"(?<![/\d.,])\b(13|14|15|16)\b(?!\s*/|\s*(?:gb|tb|gen|core|ta)\b|[.,]\d)", t):
        return m.group(1)
    return ""


def _mac(t, n=""):
    # Air yoki Pro — avval nomidan, bo'lmasa xususiyatlardan
    if re.search(r"\bair\b|\bmba\b", n):
        air = True
    elif re.search(r"\bmbp\b|\bpro\b|\bmax\b", n):
        air = False
    else:
        air = bool(re.search(r"\bair\b|\bmba\b", t))
    m = re.search(r"\bm([1-5])(?:\s*(pro|max))?\b", n) or re.search(r"\bm([1-5])(?:\s*(pro|max))?\b", t)
    chip, tier = (m.group(1), m.group(2)) if m else ("", None)
    size = _size(n) or _size(t)
    if air:
        big = size == "15"
        if chip == "5": return MA + ("macbook-air-15in-m5-colors.png" if big else "macbook-air-13in-m5-colors.png")
        if chip == "4": return MA + ("2025-macbook-air-15in-colors.png" if big else "2025-macbook-air-13in-colors.png")
        if chip == "3": return MA + ("2024-macbook-air-15in-m3-colors.png" if big else "2024-macbook-air-13in-m3-colors.png")
        if chip == "2": return MA + ("2023-macbook-air-15in-m2-colors.png" if big else "2022-macbook-air-m2-colors.png")
        if chip == "1": return MA + "macbook-air-2020-late-device.jpg"
        if "2020" in t: return MA + "macbook-air-2020-device.jpg"
        if re.search(r"2018|2019", t): return MA + "macbook-air-2018-device.jpg"
        return MA + "macbook-air-2020-late-device.jpg"
    big = size == "16"
    if chip == "5":
        if tier: return MP + ("macbook-pro-16in-m5-pro-m5-max.png" if big else "macbook-pro-14in-m5-pro-m5-max.png")
        return MP + "macbook-pro-14in-m5-colors.png"
    if chip == "4":
        if tier or big: return MP + ("macbook-pro-16in-2024-colors.png" if big else "macbook-pro-14in-2024-m4-pro-m4-max-colors.png")
        return MP + "macbook-pro-14in-2024-m4-colors.png"
    if chip == "3":
        if tier or big: return MP + ("macbook-pro-16in-m3-pro-m3-max-nov-2023-silver-space-black.png" if big
                                     else "macbook-pro-14in-m3-pro-m3-max-nov-2023-silver-space-black.png")
        return MP + "macbook-pro-14in-m3-nov-2023-silver-space-gray.png"
    if chip == "2":
        if tier or size in ("14", "16"): return MP + ("macbook-pro-16in-2023.png" if big else "macbook-pro-14in-2023.png")
        return MP + "macbook-pro-13-in-M2-2022.png"
    if chip == "1":
        if tier or size in ("14", "16"): return MP + ("macbook-pro-2021-16in.png" if big else "macbook-pro-2021-14in.png")
        return MP + "macbook-pro-2020-late-13in-device.jpg"
    if big: return MP + "macbook-pro-16in-2019.jpg"
    if size == "15": return MP + "macbook-pro-2018-15in-device-2.jpg"
    if "2020" in t: return MP + "macbook-pro-2020-13in-device-3.jpg"
    return MP + "macbook-pro-2018-13in-device.jpg"


# Apple bo'lmagan mahsulotlar — Wikimedia Commons (erkin litsenziya, manbasi sahifada yoziladi)
WM = "https://commons.wikimedia.org/wiki/Special:FilePath/%s?width=900"
OTHER = [
    (re.compile(r"\bquest\b"), ["Meta_Quest_3_front_View.jpg", "Meta_Quest_3_display_unit.jpg"]),
    (re.compile(r"ray-?ban|rayban"), ["Ray-Ban_Meta_Gen_1_smart_glasses_with_charging_case.jpg",
                                     "Ray_Ban_Meta_at_the_2025_Bild_Expo_Presented_by_B%26H_Photo.jpg"]),
    (re.compile(r"airpods\s*max"), ["Apple_airpods_max_3.jpg", "Apple_AirPods_Max_6.jpg", "Apple_airpods_max_with_case.jpg"]),
    (re.compile(r"playstation\s*5|\bps5\b"), ["PlayStation_5_and_DualSense_with_transparent_background.png",
                                              "PlayStation_5_and_DualSense.jpg"]),
    (re.compile(r"vision\s*pro"), ["Apple_Vision_Pro_with_charger_(cropped).jpg", "Apple_Vision_Pro_on_display.jpg"]),
    (re.compile(r"s22\s*ultra"), ["SAMSUNG_Galaxy_S22_Ultra_BLACK.jpg", "Back_of_the_Samsung_Galaxy_S22_Ultra.jpg"]),
    (re.compile(r"s25\s*ultra"), ["Samsung_Galaxy_S25_Ultra.jpg", "Samsung_Galaxy_S25_Ultra_2025.jpg"]),
    (re.compile(r"magic\s*keyboard.*ipad|ipad.*magic\s*keyboard"), ["Magic_Keyboard_for_iPad_Pro_-_2.jpg"]),
]

NOT_APPLE = re.compile(r"galaxy|samsung|xiaomi|redmi|poco|honor|huawei|pixel|oneplus|meta\b|oakley|ray-?ban|quest|playstation|\bps[45]\b|sony|garmin|amazfit")
ACCESSORY = re.compile(r"keyboard|klaviatura|pencil|qalam|chexol|case\b|plyonka|himoya|maxfiy|shaffof|\bmat\b|matoviy|zaryad|kabel|cable|adapter|"
                       r"charger|\b\d{2,3}\s*w\b|mouse|sichqon|trackpad|stand|sumka|bag\b|hub\b")


def stock_photos(name, details, category=""):
    n = name.lower().replace("”", '"')
    t = (n + " " + " ".join(v for _, v in details).lower()).replace("”", '"')
    c = category.lower()
    for rx, files in OTHER:
        if rx.search(n):
            return [WM % f for f in files]
    if NOT_APPLE.search(n) or ACCESSORY.search(n) or ACCESSORY.search(c):
        return []
    is_mac = "macbook" in t or "macbook" in c or re.search(r"\b(mba|mbp)\b", t)
    if not is_mac:
        for rx, url in DEVICES:
            if rx.search(t):
                return [url]
        if not re.search(r"\b(air|pro)\b.*\bm[1-5]\b", t):
            return []
    return [_mac(t, n)]
