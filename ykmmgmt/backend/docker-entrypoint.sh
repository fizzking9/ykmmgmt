#!/bin/sh
# Container startup: guard + run migrations, seed the root account when
# credentials are provided (idempotent), then serve the API.
set -e

python -m scripts.migrate

if [ -n "$ROOT_USERNAME" ]; then
  python -m scripts.seed_root
fi

exec python -m scripts.serve
