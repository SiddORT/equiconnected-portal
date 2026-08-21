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

# Always use the public npm registry on the VPS.
npm config set registry https://registry.npmjs.org/

# Replit can generate dependency metadata pointing at its internal
# package firewall. That URL is unreachable from the VPS.
if grep -Rqs "package-firewall.replit.local" package.json package-lock.json 2>/dev/null; then
  echo "==> Replit package-firewall URL detected; regenerating npm lockfile"
  rm -f package-lock.json
fi

npm install --registry=https://registry.npmjs.org/

echo "==> Building frontend"
npm run build

echo "==> Installing backend dependencies"
cd "$APP_DIR"
source "$APP_DIR/.venv/bin/activate"

python -m pip install \
  "alembic>=1.19.1" \
  "argon2-cffi>=25.1.0" \
  "fastapi>=0.141.1" \
  "httpx>=0.28.1" \
  "psycopg2-binary>=2.9.12" \
  "pydantic-settings>=2.15.0" \
  "pydantic[email]>=2.13.4" \
  "python-jose[cryptography]>=3.5.0" \
  "python-multipart>=0.0.32" \
  "sqlalchemy>=2.0.52" \
  "structlog>=26.1.0" \
  "uvicorn[standard]>=0.52.3"

echo "==> Running database migrations"
cd "$APP_DIR/backend"
alembic upgrade head

# Bootstrap credentials are intentionally not reset during deployment. Run the
# seed command separately for its non-destructive verification, and use its
# explicit recovery confirmation only when a credential rotation is intended.
echo "==> Restarting FastAPI"
cd "$APP_DIR"
pm2 reload ecosystem.config.cjs --only equiconnected-uat --update-env

echo "==> Testing Nginx configuration"
nginx -t

echo "==> Reloading Nginx"
systemctl reload nginx

echo "==> Deployment completed successfully"