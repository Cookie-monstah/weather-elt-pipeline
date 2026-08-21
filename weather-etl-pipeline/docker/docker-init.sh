#!/usr/bin/env bash
set -e

ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"

echo "Applying Superset DB migrations..."
superset db upgrade

echo "Creating admin user (admin / $ADMIN_PASSWORD)..."
superset fab create-admin \
    --username admin \
    --email admin@superset.com \
    --password "$ADMIN_PASSWORD" \
    --firstname Superset \
    --lastname Admin || true

echo "Setting up roles and permissions..."
superset init

if [ "$SUPERSET_LOAD_EXAMPLES" = "yes" ]; then
    echo "Loading examples..."
    superset load_examples
fi
