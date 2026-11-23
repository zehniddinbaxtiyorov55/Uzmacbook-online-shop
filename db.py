"""SQLite baza: mijozlar, buyurtmalar, sozlamalar, yashirilgan tovarlar, xabar yuborishlar.

Fayl: DB_PATH (standart: data/shop.db). Bitta jarayon ishlatadi, so'rovlar juda tez,
shuning uchun oddiy sqlite3 yetarli."""
import json, os, sqlite3, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.environ.get("DB_PATH") or os.path.join(HERE, "data", "shop.db")
TZ_SHIFT = 5 * 3600  # Toshkent (UTC+5) — "bugun" hisobi uchun

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY,
  username TEXT DEFAULT '', first_name TEXT DEFAULT '', last_name TEXT DEFAULT '',
  phone TEXT DEFAULT '', created_at INTEGER, last_seen INTEGER, blocked INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS orders(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER, name TEXT, username TEXT, phone TEXT,
  items TEXT, totals TEXT, months INTEGER DEFAULT 0, pay TEXT,
  status TEXT DEFAULT 'new', note TEXT DEFAULT '',
  created_at INTEGER, updated_at INTEGER);
CREATE INDEX IF NOT EXISTS orders_created ON orders(created_at);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS hidden(product_id TEXT PRIMARY KEY, name TEXT, at INTEGER);
CREATE TABLE IF NOT EXISTS broadcasts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  text TEXT, photo TEXT DEFAULT '', button INTEGER DEFAULT 0,
  status TEXT DEFAULT 'running', total INTEGER DEFAULT 0, sent INTEGER DEFAULT 0,
  failed INTEGER DEFAULT 0, blocked INTEGER DEFAULT 0, created_at INTEGER, finished_at INTEGER);
"""

STATUSES = ("new", "contacted", "sold", "cancelled")

_lock = threading.Lock()
_conn = None


def conn():
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        c = sqlite3.connect(PATH, check_same_thread=False, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript(SCHEMA)
        _conn = c
    return _conn


def q(sql, args=()):
    with _lock:
        return [dict(r) for r in conn().execute(sql, args).fetchall()]


def one(sql, args=()):
    rows = q(sql, args)
    return rows[0] if rows else None


def run(sql, args=()):
    with _lock:
        cur = conn().execute(sql, args)
        return cur.lastrowid


def now():
    return int(time.time())


def day_start(days_ago=0):
    """Toshkent vaqti bo'yicha kun boshi (unix)."""
    t = now() + TZ_SHIFT
    return t - t % 86400 - TZ_SHIFT - days_ago * 86400


# ---------- Mijozlar ----------
def touch_user(u):
    if not u or getattr(u, "is_bot", False):
        return
    t = now()
    run("""INSERT INTO users(id, username, first_name, last_name, created_at, last_seen, blocked)
           VALUES(?,?,?,?,?,?,0)
           ON CONFLICT(id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name,
             last_name=excluded.last_name, last_seen=excluded.last_seen, blocked=0""",
        (u.id, u.username or "", u.first_name or "", u.last_name or "", t, t))


def set_phone(uid, phone):
    t = now()
    run("""INSERT INTO users(id, phone, created_at, last_seen) VALUES(?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET phone=excluded.phone""", (uid, phone, t, t))


def get_phone(uid):
    r = one("SELECT phone FROM users WHERE id=?", (uid,))
    return (r or {}).get("phone") or ""


def set_blocked(uid, blocked=True):
    run("UPDATE users SET blocked=? WHERE id=?", (1 if blocked else 0, uid))


def audience():
    return [r["id"] for r in q("SELECT id FROM users WHERE blocked=0 ORDER BY id")]


def users(search="", limit=50, offset=0):
    where, args = "", []
    if search:
        s = "%" + search.strip().lstrip("@") + "%"
        where = ("WHERE username LIKE ? OR first_name LIKE ? OR last_name LIKE ? "
                 "OR phone LIKE ? OR CAST(id AS TEXT) LIKE ?")
        args = [s] * 5
    total = one("SELECT COUNT(*) n FROM users " + where, args)["n"]
    rows = q("""SELECT u.*, (SELECT COUNT(*) FROM orders o WHERE o.user_id=u.id) orders
                FROM users u %s ORDER BY last_seen DESC LIMIT ? OFFSET ?""" % where,
             args + [limit, offset])
    return total, rows


# ---------- Buyurtmalar ----------
def add_order(user_id, name, username, phone, items, totals, months, pay):
    t = now()
    return run("""INSERT INTO orders(user_id, name, username, phone, items, totals, months, pay,
                  status, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?, 'new', ?, ?)""",
               (user_id, name, username, phone, json.dumps(items, ensure_ascii=False),
                json.dumps(totals), months, pay, t, t))


def _order_row(r):
    r["items"] = json.loads(r.get("items") or "[]")
    r["totals"] = json.loads(r.get("totals") or "{}")
    return r


def orders(status="", search="", limit=50, offset=0):
    cond, args = [], []
    if status in STATUSES:
        cond.append("status=?")
        args.append(status)
    if search:
        s = "%" + search.strip().lstrip("@#") + "%"
        cond.append("(name LIKE ? OR username LIKE ? OR phone LIKE ? OR items LIKE ? "
                    "OR CAST(id AS TEXT) LIKE ? OR note LIKE ?)")
        args += [s] * 6
    where = ("WHERE " + " AND ".join(cond)) if cond else ""
    total = one("SELECT COUNT(*) n FROM orders " + where, args)["n"]
    rows = q("SELECT * FROM orders %s ORDER BY id DESC LIMIT ? OFFSET ?" % where,
             args + [limit, offset])
    return total, [_order_row(r) for r in rows]


def update_order(oid, status=None, note=None):
    if status is not None and status not in STATUSES:
        raise ValueError("status")
    if status is not None:
        run("UPDATE orders SET status=?, updated_at=? WHERE id=?", (status, now(), oid))
    if note is not None:
        run("UPDATE orders SET note=?, updated_at=? WHERE id=?", (note[:1000], now(), oid))
    r = one("SELECT * FROM orders WHERE id=?", (oid,))
    return _order_row(r) if r else None


def _sum_totals(rows):
    out = {}
    for r in rows:
        for cur, v in json.loads(r["totals"] or "{}").items():
            key = "USD" if (not cur or cur.upper() in ("USD", "$")) else cur.upper()
            out[key] = round(out.get(key, 0) + float(v or 0), 2)
    return out


def stats():
    d0, d7, d30 = day_start(0), day_start(6), day_start(29)
    cnt = lambda sql, *a: one(sql, a)["n"]
    by_status = {s: 0 for s in STATUSES}
    for r in q("SELECT status, COUNT(*) n FROM orders GROUP BY status"):
        by_status[r["status"]] = r["n"]
    return {
        "users": {
            "total": cnt("SELECT COUNT(*) n FROM users"),
            "active": cnt("SELECT COUNT(*) n FROM users WHERE blocked=0"),
            "today": cnt("SELECT COUNT(*) n FROM users WHERE created_at>=?", d0),
            "week": cnt("SELECT COUNT(*) n FROM users WHERE created_at>=?", d7),
            "phones": cnt("SELECT COUNT(*) n FROM users WHERE phone<>''"),
        },
        "orders": {
            "today": cnt("SELECT COUNT(*) n FROM orders WHERE created_at>=?", d0),
            "week": cnt("SELECT COUNT(*) n FROM orders WHERE created_at>=?", d7),
            "month": cnt("SELECT COUNT(*) n FROM orders WHERE created_at>=?", d30),
            "total": cnt("SELECT COUNT(*) n FROM orders"),
            "by_status": by_status,
            "sold_month": _sum_totals(q(
                "SELECT totals FROM orders WHERE status='sold' AND created_at>=?", (d30,))),
        },
        "days": [{"day": day_start(i), "orders": cnt(
            "SELECT COUNT(*) n FROM orders WHERE created_at>=? AND created_at<?",
            day_start(i), day_start(i) + 86400)} for i in range(13, -1, -1)],
    }


# ---------- Sozlamalar ----------
_settings = {}


def load_settings():
    _settings.clear()
    for r in q("SELECT key, value FROM settings"):
        _settings[r["key"]] = r["value"]
    return _settings


def get_setting(key):
    if not _settings:
        load_settings()
    return _settings.get(key)


def set_setting(key, value):
    if value is None or value == "":
        run("DELETE FROM settings WHERE key=?", (key,))
        _settings.pop(key, None)
    else:
        run("INSERT INTO settings(key, value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)))
        _settings[key] = str(value)


# ---------- Yashirilgan tovarlar ----------
def hidden_ids():
    return {r["product_id"] for r in q("SELECT product_id FROM hidden")}


def hidden_cats():
    """Mini App'da butunlay ko'rinmaydigan kategoriyalar (sozlamalarda JSON ro'yxat)."""
    try:
        return set(json.loads(get_setting("hidden_cats") or "[]"))
    except ValueError:
        return set()


def set_hidden_cat(name, hidden):
    cats = hidden_cats()
    (cats.add if hidden else cats.discard)(name)
    set_setting("hidden_cats", json.dumps(sorted(cats), ensure_ascii=False) if cats else "")


def set_hidden(pid, name, hidden):
    if hidden:
        run("INSERT OR REPLACE INTO hidden(product_id, name, at) VALUES(?,?,?)", (pid, name, now()))
    else:
        run("DELETE FROM hidden WHERE product_id=?", (pid,))


# ---------- Xabar yuborish ----------
def add_broadcast(text, photo, button, total):
    return run("""INSERT INTO broadcasts(text, photo, button, status, total, created_at)
                  VALUES(?,?,?, 'running', ?, ?)""", (text, photo, 1 if button else 0, total, now()))


def update_broadcast(bid, **kw):
    if not kw:
        return
    cols = ", ".join("%s=?" % k for k in kw)
    run("UPDATE broadcasts SET %s WHERE id=?" % cols, list(kw.values()) + [bid])


def broadcasts(limit=20):
    return q("SELECT * FROM broadcasts ORDER BY id DESC LIMIT ?", (limit,))


def mark_stuck_broadcasts():
    """Server qayta yonganda chala qolgan yuborishlarni 'to'xtatildi' deb belgilaydi."""
    run("UPDATE broadcasts SET status='stopped', finished_at=? WHERE status='running'", (now(),))
