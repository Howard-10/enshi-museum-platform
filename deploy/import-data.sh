#!/usr/bin/env bash
set -Eeuo pipefail

TYPE="${1:-docs}"
PATH_IN_CONTAINER="${2:-/data}"
cd "$(dirname "$0")"
COMPOSE=(docker compose --env-file .env -f docker-compose.yml exec -T backend)

case "$TYPE" in
  docs)
    "${COMPOSE[@]}" python -m app.cli.import_docx "$PATH_IN_CONTAINER" --infer-artifact-from-path
    ;;
  catalog)
    "${COMPOSE[@]}" python -m app.cli.import_artifact_catalog "$PATH_IN_CONTAINER" --knowledge-root /data
    ;;
  media)
    "${COMPOSE[@]}" python -m app.cli.import_media "$PATH_IN_CONTAINER" --types image audio video --report /data/media-import-report.json
    ;;
  xlsx-images)
    "${COMPOSE[@]}" python -m app.cli.import_xlsx_images "$PATH_IN_CONTAINER" --report /data/xlsx-image-import-report.json
    ;;
  *)
    echo "Usage: $0 {docs|catalog|media|xlsx-images} [container-path]" >&2
    exit 2
    ;;
esac
