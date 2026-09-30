#!/bin/sh
set -eu

# Complete schema and built-in-data initialization before accepting traffic.
python -m alembic upgrade head
python -m app.startup

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="${CCM_FORWARDED_ALLOW_IPS:-127.0.0.1}"
