#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")/.."

TAG="${1:-1.0.0}"
REGISTRY="${REGISTRY:-}"
PREFIX="${REGISTRY:+$REGISTRY/}"
BACKEND_IMAGE="${PREFIX}enshi-museum/backend:${TAG}"
FRONTEND_IMAGE="${PREFIX}enshi-museum/frontend:${TAG}"

docker build -t "$BACKEND_IMAGE" ./backend
docker build --build-arg VITE_API_BASE_URL=/api/v1 -t "$FRONTEND_IMAGE" ./frontend

if [[ "${PUSH:-false}" == "true" ]]; then
  [[ -n "$REGISTRY" ]] || { echo "PUSH=true requires REGISTRY" >&2; exit 1; }
  docker push "$BACKEND_IMAGE"
  docker push "$FRONTEND_IMAGE"
fi

echo "Images ready: $BACKEND_IMAGE and $FRONTEND_IMAGE"
