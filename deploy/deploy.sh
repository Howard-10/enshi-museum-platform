#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env. Fill in passwords and public addresses, then run deploy.sh again." >&2
  exit 1
fi

mkdir -p data volumes/postgres volumes/redis volumes/minio

if [[ "${BUILD:-false}" == "true" ]]; then
  ./build-images.sh "${IMAGE_TAG:-1.0.0}"
fi

docker compose --env-file .env -f docker-compose.yml up -d --remove-orphans
docker compose --env-file .env -f docker-compose.yml ps
