#!/usr/bin/env bash
# @Onlineshopaibot (Mini App do'kon) + admin panel — Ubuntu serverga o'rnatish.
#
# Serverda (root) bitta buyruq:
#   curl -fsSL https://raw.githubusercontent.com/zehniddinbaxtiyorov55/Uzmacbook-online-shop/server/deploy/install.sh -o install.sh && bash install.sh
#
# Qayta ishga tushirish xavfsiz: kodni yangilaydi, .env va bazaga tegmaydi.
# Kodni yangilash uchun keyinchalik:  bash /opt/onlineshop/deploy/install.sh
set -euo pipefail

REPO="${REPO:-https://github.com/zehniddinbaxtiyorov55/Uzmacbook-online-shop.git}"
BRANCH="${BRANCH:-server}"
SHOP_DOMAIN="${SHOP_DOMAIN:-shop.magicpro.uz}"
ADMIN_DOMAIN="${ADMIN_DOMAIN:-admin.magicpro.uz}"
DIR=/opt/onlineshop
DATA=/var/lib/onlineshop
SVC=onlineshop
RUN_USER=shopbot

say()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m  ✓ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m  ! %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m  ✗ %s\033[0m\n' "$*"; exit 1; }

ask() {  # ask O'ZGARUVCHI "Savol" [standart] [req]
  local v=""
  while :; do
    read -r -p "  $2${3:+ [$3]}: " v </dev/tty || true
    v="${v:-${3:-}}"
    if [ -n "$v" ] || [ "${4:-}" != req ]; then break; fi
    echo "    Bu maydon majburiy."
  done
  printf -v "$1" '%s' "$v"
}

main() {
  [ "$(id -u)" -eq 0 ] || die "Root bo'lib ishga tushiring:  sudo bash install.sh"
  . /etc/os-release
  [ "${ID:-}" = ubuntu ] || [ "${ID:-}" = debian ] || warn "Skript Ubuntu uchun yozilgan (sizda: ${PRETTY_NAME:-?})"
  export DEBIAN_FRONTEND=noninteractive

  # ---------- 1. Dasturlar ----------
  say "1/7 Kerakli dasturlar o'rnatilmoqda (1-3 daqiqa)"
  apt-get update -qq
  apt-get install -y -qq git curl ca-certificates gnupg sqlite3 python3 python3-venv python3-pip >/dev/null
  PY=python3
  if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'; then
    warn "Tizimdagi Python eski — Python 3.11 o'rnatilmoqda"
    apt-get install -y -qq software-properties-common >/dev/null
    add-apt-repository -y ppa:deadsnakes/ppa >/dev/null
    apt-get update -qq
    apt-get install -y -qq python3.11 python3.11-venv >/dev/null
    PY=python3.11
  fi
  ok "$($PY --version)"

  # ---------- 2. Caddy (HTTPS) ----------
  say "2/7 Caddy (avtomatik HTTPS/SSL) o'rnatilmoqda"
  if ! command -v caddy >/dev/null; then
    apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https >/dev/null 2>&1 || true
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
      | gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
      > /etc/apt/sources.list.d/caddy-stable.list
    chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -qq
    apt-get install -y -qq caddy >/dev/null
  fi
  for s in apache2 nginx; do  # 80/443 portlarni band qilib turmasin
    if systemctl is-active --quiet "$s" 2>/dev/null; then
      warn "$s 80-portni band qilgan — to'xtatildi (Caddy ishlashi uchun)"
      systemctl disable --now "$s" >/dev/null 2>&1 || true
    fi
  done
  ok "$(caddy version | cut -d' ' -f1)"

  # ---------- 3. Kod ----------
  say "3/7 Bot kodi GitHub'dan olinmoqda ($BRANCH)"
  id -u "$RUN_USER" >/dev/null 2>&1 || useradd --system --home "$DATA" --shell /usr/sbin/nologin "$RUN_USER"
  if [ -d "$DIR/.git" ]; then
    git -C "$DIR" fetch -q origin "$BRANCH"
    git -C "$DIR" checkout -q "$BRANCH" 2>/dev/null || git -C "$DIR" checkout -q -b "$BRANCH" "origin/$BRANCH"
    git -C "$DIR" reset -q --hard "origin/$BRANCH"
  else
    git clone -q -b "$BRANCH" "$REPO" "$DIR"
  fi
  mkdir -p "$DATA"
  chown -R "$RUN_USER:$RUN_USER" "$DATA"
  chmod 750 "$DATA"
  ok "$(git -C "$DIR" log -1 --format='%h %s')"

  say "4/7 Python kutubxonalari"
  [ -x "$DIR/venv/bin/python" ] || $PY -m venv "$DIR/venv"
  "$DIR/venv/bin/pip" install -q --upgrade pip >/dev/null
  "$DIR/venv/bin/pip" install -q -r "$DIR/requirements.txt"
  ok "aiogram $("$DIR/venv/bin/python" -c 'import aiogram; print(aiogram.__version__)')"

  # ---------- 5. Sozlamalar (.env) ----------
  ENVF="$DIR/.env"
  NEWPASS=""
  if [ ! -f "$ENVF" ]; then
    say "5/7 Bot sozlamalari"
    echo "  Qiymatlarni Render → servis → Environment bo'limidan nusxalab qo'ying."
    echo "  (Terminalga qo'yish: Cmd+V, keyin Enter)"
    ask BOT_TOKEN "BOT_TOKEN" "" req
    ask BILLZ_SECRET_KEY "BILLZ_SECRET_KEY" "" req
    ask ADMIN_CHAT_ID "ADMIN_CHAT_ID (buyurtmalar keladigan chat ID)" "" req
    ask CASHBACK_API "CASHBACK_API (yo'q bo'lsa Enter)" ""
    ask CASHBACK_KEY "CASHBACK_KEY (yo'q bo'lsa Enter)" ""
    ask REPORT_TO "REPORT_TO (kunlik hisobot kimga)" "@baxtiyorov_zz"
    ask QUESTIONS_CONTACT "Savollar uchun Telegram username" "sherxonjumayev"
    NEWPASS="$($PY -c 'import secrets; print(secrets.token_urlsafe(10))')"
    umask 027
    cat > "$ENVF" <<EOF
# @Onlineshopaibot sozlamalari. O'zgartirgandan keyin:  systemctl restart $SVC
BOT_TOKEN=$BOT_TOKEN
BILLZ_SECRET_KEY=$BILLZ_SECRET_KEY
ADMIN_CHAT_ID=$ADMIN_CHAT_ID
CASHBACK_API=$CASHBACK_API
CASHBACK_KEY=$CASHBACK_KEY
REPORT_TO=$REPORT_TO
QUESTIONS_CONTACT=$QUESTIONS_CONTACT

# Manzillar
WEBAPP_URL=https://$SHOP_DOMAIN/
ADMIN_HOST=$ADMIN_DOMAIN

# Admin panel kirish
ADMIN_USER=admin
ADMIN_PASSWORD=$NEWPASS

# Server
HOST=127.0.0.1
PORT=8080
DB_PATH=$DATA/shop.db
KEEP_AWAKE=0
EOF
    umask 022
  else
    say "5/7 Sozlamalar: $ENVF allaqachon bor — tegilmadi"
  fi
  chown "root:$RUN_USER" "$ENVF"
  chmod 640 "$ENVF"
  TOKEN="$(grep -m1 '^BOT_TOKEN=' "$ENVF" | cut -d= -f2-)"
  BOTNAME="$(curl -s --max-time 10 "https://api.telegram.org/bot${TOKEN}/getMe" \
    | $PY -c 'import json,sys; d=json.load(sys.stdin); print(d["result"]["username"] if d.get("ok") else "")' 2>/dev/null || true)"
  if [ -n "$BOTNAME" ]; then ok "Token to'g'ri: @$BOTNAME"; else warn "BOT_TOKEN ni Telegram qabul qilmadi — $ENVF ni tekshiring"; fi

  # ---------- 6. Xizmatlar ----------
  say "6/7 Bot xizmati va HTTPS sozlanmoqda"
  cat > "/etc/systemd/system/$SVC.service" <<EOF
[Unit]
Description=Onlineshop bot (@Onlineshopaibot) + admin panel
After=network-online.target
Wants=network-online.target

[Service]
User=$RUN_USER
Group=$RUN_USER
WorkingDirectory=$DIR
EnvironmentFile=$ENVF
ExecStart=$DIR/venv/bin/python -u shop_bot.py
Restart=always
RestartSec=5
NoNewPrivileges=true
ProtectSystem=full
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

  if [ -f /etc/caddy/Caddyfile ] && ! grep -q "onlineshop" /etc/caddy/Caddyfile; then
    cp /etc/caddy/Caddyfile "/etc/caddy/Caddyfile.bak.$(date +%s)"
  fi
  cat > /etc/caddy/Caddyfile <<EOF
# onlineshop — @Onlineshopaibot (install.sh yozgan)
$SHOP_DOMAIN {
	encode gzip
	@admin path /admin /admin/*
	respond @admin 404
	reverse_proxy 127.0.0.1:8080
}

$ADMIN_DOMAIN {
	encode gzip
	redir / /admin
	@other not path /admin /admin/* /logo.png
	respond @other 404
	reverse_proxy 127.0.0.1:8080
}
EOF
  caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null 2>&1 || die "Caddyfile xato"

  if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
    ufw allow OpenSSH >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null
    ok "Firewall: 22, 80, 443 ochildi"
  fi

  systemctl daemon-reload
  systemctl enable -q "$SVC"
  systemctl restart "$SVC"
  systemctl enable -q caddy
  systemctl restart caddy

  for _ in $(seq 1 20); do
    curl -fs --max-time 2 http://127.0.0.1:8080/api/alive >/dev/null 2>&1 && break
    sleep 1
  done
  if curl -fs --max-time 2 http://127.0.0.1:8080/api/alive >/dev/null 2>&1; then
    ok "Bot ishga tushdi"
  else
    journalctl -u "$SVC" -n 30 --no-pager || true
    die "Bot ishga tushmadi — yuqoridagi xatoni Claude'ga yuboring"
  fi

  # ---------- 7. Domen tekshiruvi ----------
  say "7/7 Domen (DNS) tekshiruvi"
  IP="$(curl -4 -s --max-time 5 https://api.ipify.org || true)"
  [ -n "$IP" ] || IP="$(hostname -I | awk '{print $1}')"
  DNS_OK=1
  for d in "$SHOP_DOMAIN" "$ADMIN_DOMAIN"; do
    r="$(getent ahostsv4 "$d" 2>/dev/null | awk '{print $1; exit}' || true)"
    if [ "$r" = "$IP" ]; then
      ok "$d → $IP"
    else
      warn "$d hali bu serverga ulanmagan (hozir: ${r:-topilmadi})"
      DNS_OK=0
    fi
  done

  printf '\n\033[1;32m================ TAYYOR ================\033[0m\n'
  echo "  Admin panel:  https://$ADMIN_DOMAIN"
  echo "  Login:        admin"
  if [ -n "$NEWPASS" ]; then
    echo "  Parol:        $NEWPASS     <-- yozib oling!"
  else
    echo "  Parol:        $ENVF faylida (ADMIN_PASSWORD)"
  fi
  echo "  Mini App:     https://$SHOP_DOMAIN"
  echo
  if [ "$DNS_OK" -eq 0 ]; then
    echo "  KEYINGI QADAM: domen DNS'iga 2 ta A yozuv qo'shing:"
    echo "      shop   →  $IP"
    echo "      admin  →  $IP"
    echo "  DNS ishlagach bot o'zi HTTPS oladi va Telegram'ni shu serverga o'tkazadi."
    echo "  Ungacha eski server (Render) ishlashda davom etadi."
  else
    echo "  Bot 1-2 daqiqada Telegram'ni shu serverga o'tkazadi. Tekshirish:"
    echo "      journalctl -u $SVC | grep webhook"
  fi
  echo
  echo "  Loglar:     journalctl -u $SVC -f"
  echo "  Qayta yoq:  systemctl restart $SVC"
  echo "  Yangilash:  bash $DIR/deploy/install.sh"
}

main "$@"
