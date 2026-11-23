#!/usr/bin/env bash
# Uzmacbook AI chat-bot (Telegram Business + Gemini) — Ubuntu serverga o'rnatish.
#
# Serverda (root) bitta buyruq:
#   curl -fsSL https://raw.githubusercontent.com/zehniddinbaxtiyorov55/Uzmacbook-online-shop/server/deploy/install-ai.sh -o install-ai.sh && bash install-ai.sh
#
# AI bot kodi yopiq (private) GitHub reposida turadi, shuning uchun server unga
# "deploy key" orqali ulanadi: skript kalitni chiqaradi, siz uni GitHub'ga bir marta qo'shasiz.
# Bot polling rejimida ishlaydi — domen ham, SSL ham kerak emas.
#
# Qayta ishga tushirish xavfsiz: kodni yangilaydi, .env ga tegmaydi.
# Yangilash:  bash /opt/aibot-install.sh   (yoki yuqoridagi buyruq)
set -euo pipefail

REPO_SSH="git@github.com:zehniddinbaxtiyorov55/Uzmacbook-chat-bot-uchun-.git"
REPO_WEB="https://github.com/zehniddinbaxtiyorov55/Uzmacbook-chat-bot-uchun-"
BRANCH="${BRANCH:-server}"
DIR=/opt/aibot
SVC=aibot
RUN_USER=aibot
KEY=/root/.ssh/aibot_deploy
SHOP_ENV=/opt/onlineshop/.env

say()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m  ✓ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m  ! %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m  ✗ %s\033[0m\n' "$*"; exit 1; }

ask() {  # ask O'ZGARUVCHI "Savol" [standart] [req]
  local v=""
  while :; do
    read -r -p "  $2${3:+ [Enter = mavjudini ishlatish]}: " v </dev/tty || true
    v="${v:-${3:-}}"
    if [ -n "$v" ] || [ "${4:-}" != req ]; then break; fi
    echo "    Bu maydon majburiy."
  done
  printf -v "$1" '%s' "$v"
}

setenv() {  # setenv FAYL KALIT QIYMAT — bor bo'lsa almashtiradi, yo'q bo'lsa qo'shadi
  if grep -q "^$2=" "$1"; then sed -i "s#^$2=.*#$2=$3#" "$1"; else echo "$2=$3" >> "$1"; fi
}

git_ssh() { GIT_SSH_COMMAND="ssh -i $KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new" git "$@"; }

main() {
  [ "$(id -u)" -eq 0 ] || die "Root bo'lib ishga tushiring:  sudo -i  so'ng  bash install-ai.sh"
  export DEBIAN_FRONTEND=noninteractive

  # ---------- 1. Dasturlar ----------
  say "1/5 Kerakli dasturlar"
  apt-get update -qq
  apt-get install -y -qq git curl ca-certificates openssh-client python3 python3-venv python3-pip >/dev/null
  ok "$(python3 --version)"

  # ---------- 2. GitHub kaliti (deploy key) ----------
  say "2/5 GitHub'ga ulanish (yopiq repo)"
  mkdir -p /root/.ssh && chmod 700 /root/.ssh
  [ -f "$KEY" ] || ssh-keygen -q -t ed25519 -N "" -C "aibot@airnet-server" -f "$KEY"
  until git_ssh ls-remote -q "$REPO_SSH" "$BRANCH" >/dev/null 2>&1; do
    echo
    echo "  Server GitHub'dagi AI bot kodini o'qishi uchun kalitni bir marta qo'shing:"
    echo
    echo "  1) Brauzerda oching:  $REPO_WEB/settings/keys/new"
    echo "  2) Title:  airnet server"
    echo "  3) Key:    pastdagi qatorni TO'LIQ nusxalab qo'ying"
    echo
    printf '\033[1;36m%s\033[0m\n' "$(cat "$KEY.pub")"
    echo
    echo "  4) \"Allow write access\" ni BELGILAMANG  →  Add key"
    echo
    read -r -p "  Qo'shib bo'lgach Enter bosing... " _ </dev/tty || true
  done
  ok "GitHub'ga ulandi"

  # ---------- 3. Kod ----------
  say "3/5 AI bot kodi ($BRANCH)"
  id -u "$RUN_USER" >/dev/null 2>&1 || useradd --system --home "$DIR" --shell /usr/sbin/nologin "$RUN_USER"
  if [ -d "$DIR/.git" ]; then
    git_ssh -C "$DIR" fetch -q origin "$BRANCH"
    git -C "$DIR" checkout -q "$BRANCH" 2>/dev/null || git -C "$DIR" checkout -q -b "$BRANCH" "origin/$BRANCH"
    git -C "$DIR" reset -q --hard "origin/$BRANCH"
  else
    git_ssh clone -q -b "$BRANCH" "$REPO_SSH" "$DIR"
  fi
  git -C "$DIR" config core.sshCommand "ssh -i $KEY -o IdentitiesOnly=yes"
  ok "$(git -C "$DIR" log -1 --format='%h %s')"
  [ -x "$DIR/venv/bin/python" ] || python3 -m venv "$DIR/venv"
  "$DIR/venv/bin/pip" install -q --upgrade pip >/dev/null
  "$DIR/venv/bin/pip" install -q -r "$DIR/requirements.txt"
  ok "kutubxonalar o'rnatildi"
  mkdir -p /var/lib/aibot && chown "$RUN_USER:$RUN_USER" /var/lib/aibot && chmod 750 /var/lib/aibot
  cp -f "$0" /opt/aibot-install.sh 2>/dev/null || true

  # ---------- 4. Sozlamalar ----------
  ENVF="$DIR/.env"
  if [ ! -f "$ENVF" ]; then
    say "4/5 AI bot sozlamalari"
    echo "  Qiymatlarni Render → uzmacbook-ai-bot → Environment bo'limidan nusxalab qo'ying (Cmd+V, Enter)."
    local shop_billz="" shop_token=""
    if [ -f "$SHOP_ENV" ]; then
      shop_billz="$(grep -m1 '^BILLZ_SECRET_KEY=' "$SHOP_ENV" | cut -d= -f2- || true)"
      shop_token="$(grep -m1 '^BOT_TOKEN=' "$SHOP_ENV" | cut -d= -f2- || true)"
    fi
    ask BOT_TOKEN "BOT_TOKEN (AI botniki, do'kon botiniki EMAS)" "" req
    if [ -n "$shop_token" ] && [ "$BOT_TOKEN" = "$shop_token" ]; then
      die "Bu do'kon botining (@Onlineshopaibot) tokeni. AI botning tokeni boshqa — Render'dagi uzmacbook-ai-bot dan oling."
    fi
    ask GEMINI_API_KEY "GEMINI_API_KEY" "" req
    if [ -n "$shop_billz" ]; then
      ask BILLZ_SECRET_KEY "BILLZ_SECRET_KEY (do'kon botidagisi bilan bir xil)" "$shop_billz"
    else
      ask BILLZ_SECRET_KEY "BILLZ_SECRET_KEY" "" req
    fi
    umask 027
    cat > "$ENVF" <<EOF
# AI chat-bot sozlamalari. O'zgartirgandan keyin:  systemctl restart $SVC
BOT_TOKEN=$BOT_TOKEN
GEMINI_API_KEY=$GEMINI_API_KEY
BILLZ_SECRET_KEY=$BILLZ_SECRET_KEY
SHOP_BOT_USERNAME=Onlineshopaibot

# O'z serverda: polling rejimi (domen kerak emas)
ALLOW_POLLING=1

# Ixtiyoriy (Render'da bo'lgan bo'lsa shu yerga ham yozing):
# NUDGE_MINUTES=60
# GEMINI_MODEL=
# TRADEIN_QUOTE=0
EOF
    umask 022
  else
    say "4/5 Sozlamalar: $ENVF allaqachon bor — tegilmadi"
  fi
  # Admin panel ("🤖 AI bot" bo'limi) uchun ichki API: suhbatlar, ko'rsatmalar, yoqish/o'chirish
  local secret shop_restart=0
  secret="$(grep -m1 '^AI_ADMIN_SECRET=' "$ENVF" | cut -d= -f2- || true)"
  [ -n "$secret" ] || secret="$(python3 -c 'import secrets; print(secrets.token_hex(24))')"
  setenv "$ENVF" AI_ADMIN_SECRET "$secret"
  grep -q '^AI_API_PORT=' "$ENVF" || setenv "$ENVF" AI_API_PORT 8091
  grep -q '^AI_DB_PATH=' "$ENVF" || setenv "$ENVF" AI_DB_PATH /var/lib/aibot/ai.db
  local ai_port; ai_port="$(grep -m1 '^AI_API_PORT=' "$ENVF" | cut -d= -f2-)"
  if [ -f "$SHOP_ENV" ]; then
    setenv "$SHOP_ENV" AI_API_URL "http://127.0.0.1:$ai_port"
    setenv "$SHOP_ENV" AI_ADMIN_SECRET "$secret"
    shop_restart=1
  fi
  chown "root:$RUN_USER" "$ENVF"
  chmod 640 "$ENVF"
  chown -R "root:$RUN_USER" "$DIR"
  TOKEN="$(grep -m1 '^BOT_TOKEN=' "$ENVF" | cut -d= -f2-)"
  ME="$(curl -s --max-time 10 "https://api.telegram.org/bot${TOKEN}/getMe" || true)"
  BOTNAME="$(printf '%s' "$ME" | python3 -c 'import json,sys
d = json.load(sys.stdin)
print((d.get("result") or {}).get("username", "") if d.get("ok") else "")' 2>/dev/null || true)"
  BIZ="$(printf '%s' "$ME" | python3 -c 'import json,sys
print(1 if (json.load(sys.stdin).get("result") or {}).get("can_connect_to_business") else 0)' 2>/dev/null || echo 0)"
  if [ -n "$BOTNAME" ]; then
    ok "Token to'g'ri: @$BOTNAME"
    [ "$BIZ" = 1 ] || warn "BotFather'da @$BOTNAME uchun Business Mode yoqilmagan (Bot Settings → Business Mode)"
  else
    warn "BOT_TOKEN ni Telegram qabul qilmadi — $ENVF ni tekshiring"
  fi

  # ---------- 5. Xizmat ----------
  say "5/5 AI bot xizmati"
  cat > "/etc/systemd/system/$SVC.service" <<EOF
[Unit]
Description=Uzmacbook AI chat-bot (Telegram Business + Gemini)
After=network-online.target
Wants=network-online.target

[Service]
User=$RUN_USER
Group=$RUN_USER
WorkingDirectory=$DIR
EnvironmentFile=$ENVF
ExecStart=$DIR/venv/bin/python -u bot.py
Restart=always
RestartSec=5
NoNewPrivileges=true
ProtectSystem=full
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable -q "$SVC"
  local since; since="$(date '+%Y-%m-%d %H:%M:%S')"
  systemctl restart "$SVC"

  echo "  Ishga tushmoqda (Billz va Gemini tekshirilyapti, 1-2 daqiqa)..."
  local up=0
  for _ in $(seq 1 120); do
    if journalctl -u "$SVC" --since "$since" --no-pager 2>/dev/null | grep -q "polling rejimi"; then up=1; break; fi
    systemctl is-active --quiet "$SVC" || break
    sleep 1
  done
  if [ "$up" = 1 ]; then
    ok "AI bot ishga tushdi"
    if [ "$shop_restart" = 1 ] && systemctl list-unit-files onlineshop.service >/dev/null 2>&1; then
      systemctl restart onlineshop && ok "Admin panelga ulandi: 🤖 AI bot bo'limi"
    fi
    journalctl -u "$SVC" --since "$since" --no-pager | grep -E "tanlangan modellar|xato|Error" | tail -4 | sed 's/^/    /' || true
  else
    journalctl -u "$SVC" --since "$since" -n 40 --no-pager || true
    die "AI bot ishga tushmadi — yuqoridagi yozuvlarni rasmga olib Claude'ga yuboring"
  fi

  printf '\n\033[1;32m================ TAYYOR ================\033[0m\n'
  echo "  AI bot: ${BOTNAME:+@$BOTNAME} — Telegram Business orqali do'kon akkauntiga javob beradi"
  echo "  Boshqaruv: admin panel → 🤖 AI bot (suhbatlar, tahlil, ko'rsatmalar, yoqish/o'chirish)"
  echo
  echo "  MUHIM: Render'dagi eski uzmacbook-ai-bot servisini hozir Suspend qiling,"
  echo "  aks holda u qayta yonganda botni o'ziga tortib oladi."
  echo
  echo "  Loglar:     journalctl -u $SVC -f"
  echo "  Qayta yoq:  systemctl restart $SVC"
  echo "  Yangilash:  bash /opt/aibot-install.sh"
}

main "$@"
