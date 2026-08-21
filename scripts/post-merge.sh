#!/bin/bash
# Post-merge setup script — runs automatically after every task merge.
# Requirements: idempotent, non-interactive (stdin is closed), fail-fast.
set -e

echo "==> Installing frontend dependencies..."
cd frontend && npm install --no-audit --no-fund
cd ..

echo "==> Syncing Python dependencies..."
uv sync

echo "==> Running database migrations..."
cd backend && uv run alembic upgrade heads
cd ..

# Do not run credential recovery from post-merge automation. The bootstrap
# command is an operator action and is non-destructive unless explicitly confirmed.
echo "==> Post-merge setup complete."
