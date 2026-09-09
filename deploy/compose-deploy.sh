#!/usr/bin/env bash
# Run on the deploy host (invoked by GitLab CI or manually).
# Requires: docker, docker compose, HUB_IMAGE, docker-compose.yml, .env in DEPLOY_PATH.

set -euo pipefail

: "${HUB_IMAGE:?Set HUB_IMAGE to the registry image tag (e.g. registry.example.com/group/idigest-hub:sha)}"

COMPOSE="${COMPOSE:-docker compose}"
PROFILE_ARGS=()
if [[ -n "${COMPOSE_PROFILES:-}" ]]; then
  PROFILE_ARGS=(--profile "$COMPOSE_PROFILES")
fi

echo "Pulling ${HUB_IMAGE} ..."
export HUB_IMAGE
$COMPOSE "${PROFILE_ARGS[@]}" pull idigest-hub

echo "Starting idigest-hub ..."
$COMPOSE "${PROFILE_ARGS[@]}" up -d idigest-hub

echo "Done. Running:"
$COMPOSE "${PROFILE_ARGS[@]}" ps idigest-hub
