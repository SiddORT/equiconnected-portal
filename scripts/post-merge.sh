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
cd backend && uv run alembic upgrade head
cd ..

echo "==> Post-merge setup complete."
