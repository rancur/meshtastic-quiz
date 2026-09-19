#!/usr/bin/env bash
# Idempotent installer for Meshtastic Quiz via Docker Compose.
#
# Safe to re-run: it (re)builds the image and brings the single container up. It is
# ADDITIVE — it does not touch MeshMonitor or any other container. To stop the game
# service without affecting anything else:
#     cd deploy && docker compose down
#
# Prereqs:
#   - Docker + docker compose plugin
#   - deploy/.env created from ../.env.example with your real values
#
# WHY THIS SCRIPT cd's INTO deploy/ INSTEAD OF PASSING `-f docker-compose.yml`
# ---------------------------------------------------------------------------
# It used to run `docker compose -f "$HERE/docker-compose.yml" up -d --build`. An explicit
# `-f` SUPPRESSES override auto-loading, so `deploy/docker-compose.override.yml` was
# silently ignored. On a host whose override bind-mounts the state directory (the base
# file declares a *named volume* instead), that swap starts the bot on an EMPTY state
# store: leaderboard, monthly champion history and the 365-day no-repeat ask-history all
# gone, with the container reporting healthy. Running compose from this directory with no
# `-f` lets it discover docker-compose.yml + docker-compose.override.yml the same way the
# running container was created, and keeps the project name ("deploy") identical.
#
# Belt and braces: before touching a container that already exists, we compare where its
# /app/data actually comes from against where the resolved config says it should come
# from, and ABORT on a mismatch rather than recreate the container onto a different store.
# Set ALLOW_STATE_MOUNT_CHANGE=1 to proceed anyway (a deliberate migration).
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
ENV_FILE="$HERE/.env"
SERVICE="meshtastic-quiz"
STATE_DIR="/app/data"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found. Copy $ROOT/.env.example to $ENV_FILE and fill it in." >&2
  exit 1
fi

# Run compose from the project directory so overrides auto-load. Do NOT reintroduce `-f`.
cd "$HERE"
compose() { docker compose --env-file "$ENV_FILE" "$@"; }

# Validate the question bank before deploying. This also runs the single-answer gate, so a
# category question with no recorded adjudication stops the deploy (see meshquiz/questions.py).
echo "==> Validating question bank..."
python3 "$ROOT/scripts/build_questions.py"

echo "==> Compose files in effect:"
compose config --format json \
  | python3 -c 'import json,sys; print("    project:", json.load(sys.stdin).get("name"))'
for f in docker-compose.yml docker-compose.override.yml compose.override.yaml; do
  [[ -f "$HERE/$f" ]] && echo "    $f"
done

# --- state-store guard -----------------------------------------------------------------
# Where the resolved config says $STATE_DIR comes from. A named volume is reported by
# compose WITHOUT the project prefix that docker applies, so add it to compare like for like.
desired_state="$(compose config --format json | STATE_DIR="$STATE_DIR" python3 -c '
import json, os, sys
cfg = json.load(sys.stdin)
project = cfg.get("name") or ""
svc = cfg["services"]["'"$SERVICE"'"]
for v in svc.get("volumes", []) or []:
    if v.get("target") != os.environ["STATE_DIR"]:
        continue
    src = str(v.get("source", ""))
    if v.get("type") == "bind":
        print("bind:" + src)
    else:
        print("volume:" + (src if src.startswith(project + "_") else project + "_" + src))
    break
else:
    print("NONE")
')"

# Where the RUNNING container actually gets it from (empty if there is no container yet).
running_state="$(docker inspect "$SERVICE" \
  --format '{{range .Mounts}}{{if eq .Destination "'"$STATE_DIR"'"}}{{if eq .Type "bind"}}bind:{{.Source}}{{else}}volume:{{.Name}}{{end}}{{end}}{{end}}' \
  2>/dev/null || true)"

echo "==> State store ($STATE_DIR):"
echo "    resolved config: ${desired_state:-NONE}"
echo "    running now:     ${running_state:-<no existing container>}"

if [[ -n "$running_state" && "$running_state" != "$desired_state" ]]; then
  if [[ "${ALLOW_STATE_MOUNT_CHANGE:-0}" == "1" ]]; then
    echo "!!! State store CHANGING (ALLOW_STATE_MOUNT_CHANGE=1). The leaderboard, monthly" >&2
    echo "!!! board and no-repeat history in the old store will NOT follow. Continuing." >&2
  else
    cat >&2 <<EOF

ABORTED: recreating $SERVICE would move its state store.

  running now:     $running_state
  resolved config: ${desired_state:-NONE}

The leaderboard, monthly champion history and the 365-day no-repeat ask-history live in
that store. Recreating the container onto a different one would start the bot from empty
and look perfectly healthy while doing it. Nothing has been changed.

Usual cause: an override file that is present on this host is not being loaded (check the
list printed above), or it was edited. Reconcile it, then re-run.
If you really mean to migrate the state store, re-run with ALLOW_STATE_MOUNT_CHANGE=1.
EOF
    exit 1
  fi
fi

echo "==> Building + starting $SERVICE (idempotent)..."
compose up -d --build

# Read back what actually got mounted, rather than trusting that the plan held.
final_state="$(docker inspect "$SERVICE" \
  --format '{{range .Mounts}}{{if eq .Destination "'"$STATE_DIR"'"}}{{if eq .Type "bind"}}bind:{{.Source}}{{else}}volume:{{.Name}}{{end}}{{end}}{{end}}')"
echo "==> State store after start: $final_state"
if [[ -n "$desired_state" && "$desired_state" != "NONE" && "$final_state" != "$desired_state" ]]; then
  echo "ERROR: started with state store '$final_state', expected '$desired_state'." >&2
  exit 1
fi

echo "==> Done. Recent logs:"
compose logs --tail 20 "$SERVICE" || true

cat <<'EOF'

Next steps:
  - In your trivia channel, send: !starttrivia
  - Answer with tapback reactions 1️⃣2️⃣3️⃣4️⃣
  - !leaderboard  / !stoptrivia
  - Logs:  cd deploy && docker compose logs -f meshtastic-quiz
  - Stop:  cd deploy && docker compose down

  Always run compose from deploy/ with no -f, so docker-compose.override.yml is applied.
EOF
