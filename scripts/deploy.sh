#!/usr/bin/env bash

set -euo pipefail

APP_DIR="/var/www/nodejs/uat.equiconnected.com"

echo "==> Starting deployment"
cd "$APP_DIR"

echo "==> Updating source"
git fetch origin
git reset --hard origin/main

echo "==> Installing frontend dependencies"
cd "$APP_DIR/frontend"
npm install

echo "==> Building frontend"
npm run build

echo "==> Installing backend dependencies"
cd "$APP_DIR"
source "$APP_DIR/.venv/bin/activate"
pip install -e .

echo "==> Running database migrations"
cd "$APP_DIR/backend"
alembic upgrade head

echo "==> Restarting FastAPI"
cd "$APP_DIR"
pm2 reload ecosystem.config.cjs --only equiconnected-uat --update-env

echo "==> Testing Nginx configuration"
nginx -t

echo "==> Reloading Nginx"
systemctl reload nginx

echo "==> Deployment completed successfully"