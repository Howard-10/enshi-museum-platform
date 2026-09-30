#!/usr/bin/env bash
set -Eeuo pipefail

# Offline deployment entry point. The image archive, compose file and this
# script must be kept in the same deployment directory structure.
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env. Configure its passwords and public addresses, then run this command again." >&2
  exit 1
fi

ARCHIVE="${IMAGE_ARCHIVE:-./enshi-museum-images-1.0.0.tar}"
REQUIRED_IMAGES=(
  "enshi-museum/backend:1.0.0"
  "enshi-museum/frontend:1.0.0"
  "pgvector/pgvector:pg17"
  "redis:7-alpine"
  "quay.io/minio/minio:latest"
)

if [[ -f "$ARCHIVE" ]]; then
  echo "Loading offline images from $ARCHIVE ..."
  docker load -i "$ARCHIVE"
else
  for image in "${REQUIRED_IMAGES[@]}"; do
    docker image inspect "$image" >/dev/null 2>&1 || {
      echo "Missing $image and no image archive was found at $ARCHIVE" >&2
      exit 1
    }
  done
fi

mkdir -p data volumes/postgres volumes/redis volumes/minio
docker compose --env-file .env -f docker-compose.yml up -d --pull never --remove-orphans
docker compose --env-file .env -f docker-compose.yml ps
