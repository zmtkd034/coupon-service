#!/usr/bin/env bash
# Frontend EC2 (Amazon Linux 2023)에서 SSM Session 으로 실행: sudo bash scripts/setup_frontend.sh
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

dnf install -y nginx
rm -f /etc/nginx/conf.d/default.conf
install -m 644 "$REPO_DIR/frontend/nginx.conf" /etc/nginx/conf.d/coupon.conf
rm -rf /usr/share/nginx/html/*
cp "$REPO_DIR"/frontend/{index.html,app.js,style.css} /usr/share/nginx/html/

nginx -t
systemctl enable --now nginx
systemctl reload nginx
curl -fsS -o /dev/null -w "GET / -> %{http_code}\n" http://localhost/
