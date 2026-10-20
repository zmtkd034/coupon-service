#!/usr/bin/env bash
# Backend EC2 (Amazon Linux 2023, Private)에서 SSM Session 으로 실행:
#   sudo bash scripts/setup_backend.sh
# 실행 전 /etc/coupon/backend.env 를 만든다 (scripts/backend.env.example 참고).
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR=/opt/coupon

dnf install -y python3.11 python3.11-pip postgresql15   # psql 은 스키마 적용/검증용
id coupon &>/dev/null || useradd --system --home "$APP_DIR" --shell /sbin/nologin coupon

mkdir -p "$APP_DIR"
rm -rf "$APP_DIR/backend" && cp -r "$REPO_DIR/backend" "$APP_DIR/backend"
python3.11 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/backend/requirements.txt"
chown -R coupon:coupon "$APP_DIR"

[ -f /etc/coupon/backend.env ] || { echo "ERROR: /etc/coupon/backend.env 가 없습니다."; exit 1; }
chmod 600 /etc/coupon/backend.env

cat > /etc/systemd/system/coupon-api.service <<'EOF'
[Unit]
Description=Coupon API (FastAPI)
After=network-online.target

[Service]
User=coupon
WorkingDirectory=/opt/coupon/backend
EnvironmentFile=/etc/coupon/backend.env
ExecStart=/opt/coupon/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable coupon-api
systemctl restart coupon-api
sleep 3
curl -fsS -w "\nGET /healthz -> %{http_code}\n" http://localhost:8000/healthz
