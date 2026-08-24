#!/usr/bin/env bash
set -eo pipefail

PORT=${PORT:-8088}

case "${1}" in
  app)
    echo "Starting Superset web app..."
    flask run -p "$PORT" --host=0.0.0.0
    ;;
  *)
    echo "Unknown operation: ${1}"
    exit 1
    ;;
esac
