"""Tovarning o'z rasmlari: «📢 Kanalga post» kanalga joylanganda post rasmlari shu yerga tushadi.

Har bir b/u MacBook alohida (holati, izlari boshqa), shuning uchun rasm model guruhiga emas,
aynan o'sha Billz tovariga yoziladi. Mini App'da birinchi o'rinda turadi:
post rasmi > Billz'dagi rasm > model rasmi > Apple namunaviy rasmi.
Qayta joylansa — eski rasmlar almashtiriladi.
Fayllar: <DB papkasi>/item_photos/<Billz tovar ID>/<vaqt><tasodifiy>.jpg"""
import os
import re
import shutil
import threading
import time

import db
from model_photos import FILE_RX, _new_name, _sniff

DIR = os.path.join(os.path.dirname(db.PATH), "item_photos")
MAX = 8                        # bitta tovarga ko'pi bilan nechta rasm
MAX_BYTES = 10 * 1024 * 1024   # bitta rasm hajmi
KEY_RX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,90}$")

_lock = threading.Lock()
_index = {}   # kalit -> [fayl, ...] (tartib bo'yicha, birinchisi — asosiy)


def key_of(pid):
    return re.sub(r"[^A-Za-z0-9_-]", "", str(pid or ""))[:91]


def _dir(key):
    return os.path.join(DIR, key)


def load():
    """Diskdagi rasmlarni xotiraga o'qiydi (ishga tushganda bir marta)."""
    idx = {}
    if os.path.isdir(DIR):
        for k in os.listdir(DIR):
            p = _dir(k)
            if not (KEY_RX.match(k) and os.path.isdir(p)):
                continue
            files = sorted(f for f in os.listdir(p) if FILE_RX.match(f))
            if files:
                idx[k] = files
    with _lock:
        _index.clear()
        _index.update(idx)


def urls(pid, base=""):
    """Rasm manzillari. base="" — nisbiy (Mini App uchun)."""
    k = key_of(pid)
    return [base + "ip/%s/%s" % (k, f) for f in _index.get(k) or []]


def path(key, name):
    if not (KEY_RX.match(key or "") and FILE_RX.match(name or "")):
        return ""
    p = os.path.join(_dir(key), name)
    return p if os.path.isfile(p) else ""


def replace(pid, blobs):
    """Tovar rasmlarini yangilari bilan almashtiradi. Qaytaradi: saqlangan rasmlar soni.
    Yaroqsiz (rasm emas yoki juda katta) fayllar tashlab ketiladi."""
    key = key_of(pid)
    if not KEY_RX.match(key):
        raise ValueError("Noto'g'ri tovar ID")
    good = []
    for data in blobs:
        ext = _sniff(data or b"")
        if ext and len(data) <= MAX_BYTES:
            good.append((data, ext))
        if len(good) >= MAX:
            break
    if not good:
        return 0
    with _lock:
        d = _dir(key)
        tmp = d + ".new"
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp)
        ms = int(time.time() * 1000)
        names = []
        for i, (data, ext) in enumerate(good):
            name = _new_name(ext, ms + i)          # vaqt tartibi = post tartibi
            with open(os.path.join(tmp, name), "wb") as f:
                f.write(data)
            names.append(name)
        old = d + ".old"
        shutil.rmtree(old, ignore_errors=True)
        if os.path.isdir(d):
            os.replace(d, old)
        os.replace(tmp, d)
        shutil.rmtree(old, ignore_errors=True)
        _index[key] = sorted(names)
    return len(names)


def clear(pid):
    key = key_of(pid)
    with _lock:
        shutil.rmtree(_dir(key), ignore_errors=True)
        _index.pop(key, None)


load()
