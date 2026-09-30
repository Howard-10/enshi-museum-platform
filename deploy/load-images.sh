#!/usr/bin/env bash
set -Eeuo pipefail

ARCHIVE="${1:-enshi-museum-images-1.0.0.tar}"
docker load -i "$ARCHIVE"
echo "Loaded image bundle: $ARCHIVE"
