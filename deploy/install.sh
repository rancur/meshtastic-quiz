#!/usr/bin/env bash
# Idempotent installer for Meshtastic Quiz via Docker Compose.
#
# Safe to re-run: it (re)builds the image and brings the single container up. It is
# ADDITIVE — it does not touch MeshMonitor or any other container. To stop the game
# service without affecting anything else: `docker compose -f deploy/docker-compose.yml down`.
#
# Prereqs:
#   - Docker + docker compose plugin
#   - deploy/.env created from ../.env.example with your real values
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
COMPOSE="$HERE/docker-compose.yml"
ENV_FILE="$HERE/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found. Copy $ROOT/.env.example to $ENV_FILE and fill it in." >&2
  exit 1
fi

# Validate the question bank before deploying (fails loudly if any question is oversize).
echo "==> Validating question bank..."
python3 "$ROOT/scripts/build_questions.py"

echo "==> Building + starting meshtastic-quiz (idempotent)..."
docker compose -f "$COMPOSE" --env-file "$ENV_FILE" up -d --build

echo "==> Done. Recent logs:"
docker compose -f "$COMPOSE" logs --tail 20 meshtastic-quiz || true

cat <<'EOF'

Next steps:
  - In your trivia channel, send: !starttrivia
  - Answer with tapback reactions 1️⃣2️⃣3️⃣4️⃣
  - !leaderboard  / !stoptrivia
  - Logs:  docker compose -f deploy/docker-compose.yml logs -f meshtastic-quiz
  - Stop:  docker compose -f deploy/docker-compose.yml down
EOF
