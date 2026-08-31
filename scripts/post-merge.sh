#!/bin/bash
# Post-merge setup script — runs automatically after every task merge.
# Requirements: idempotent, non-interactive (stdin is closed), fail-fast.
set -e

echo "==> Installing frontend dependencies..."
cd frontend

frontend_install_succeeded=false
for attempt in 1 2 3; do
  if npm install \
    --no-audit \
    --no-fund \
    --prefer-online \
    --fetch-retries=5 \
    --fetch-retry-factor=2 \
    --fetch-retry-mintimeout=1000 \
    --fetch-retry-maxtimeout=10000; then
    frontend_install_succeeded=true
    break
  fi

  if [ "$attempt" -lt 3 ]; then
    echo "==> Frontend install attempt ${attempt} failed; refreshing npm cache before retry..."
    npm cache clean --force >/dev/null 2>&1 || true
    sleep "$((attempt * 2))"
  fi
done

if [ "$frontend_install_succeeded" != true ]; then
  echo "==> Frontend dependency installation failed after 3 attempts." >&2
  exit 1
fi

cd ..

echo "==> Syncing Python dependencies..."
uv sync

echo "==> Running database migrations..."
cd backend && uv run alembic upgrade heads
cd ..

# Do not run credential recovery from post-merge automation. The bootstrap
# command is an operator action and is non-destructive unless explicitly confirmed.
echo "==> Post-merge setup complete."
