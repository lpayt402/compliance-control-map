#!/usr/bin/env sh
set -eu

MODE="start"
DEPLOYMENT="local"
REFRESH="false"
ASSUME_YES="false"
ARCHIVE=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    start|status|down|export|restore) MODE="$1" ;;
    --server) DEPLOYMENT="server" ;;
    --local) DEPLOYMENT="local" ;;
    --refresh) REFRESH="true" ;;
    --yes) ASSUME_YES="true" ;;
    --archive) shift; ARCHIVE="${1:-}" ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
  shift
done

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_ROOT"

if [ ! -f .env ]; then
  cp .env.example .env
  printf '%s\n' 'Created .env from the safe local defaults.'
fi

compose() {
  if [ "$DEPLOYMENT" = "server" ]; then
    docker compose --env-file .env -f docker-compose.yml -f docker-compose.server.yml "$@"
  else
    docker compose --env-file .env -f docker-compose.yml "$@"
  fi
}

env_value() {
  key="$1"
  fallback="$2"
  value=$(sed -n "s/^${key}=//p" .env | tail -n 1)
  if [ -n "$value" ]; then printf '%s' "$value"; else printf '%s' "$fallback"; fi
}

check_server_configuration() {
  [ "$DEPLOYMENT" = "server" ] && [ "$MODE" = "start" ] || return 0
  postgres_password=$(env_value CCM_POSTGRES_PASSWORD "")
  bootstrap_email=$(env_value CCM_BOOTSTRAP_ADMIN_EMAIL "")
  bootstrap_password=$(env_value CCM_BOOTSTRAP_ADMIN_PASSWORD "")
  allowed_origins=$(env_value CCM_ALLOWED_ORIGINS "")
  allowed_hosts=$(env_value CCM_ALLOWED_HOSTS "")

  if [ -z "$postgres_password" ] || [ -z "$allowed_origins" ] || [ -z "$allowed_hosts" ]; then
    printf '%s\n' 'Server mode requires CCM_POSTGRES_PASSWORD, CCM_ALLOWED_ORIGINS, and CCM_ALLOWED_HOSTS in .env.' >&2
    exit 2
  fi
  case "$postgres_password$bootstrap_password$allowed_origins$allowed_hosts" in
    *CHANGE_ME*) printf '%s\n' 'Replace every CHANGE_ME value in .env before starting server mode.' >&2; exit 2 ;;
  esac
  case "$allowed_origins$allowed_hosts" in
    *example.com*) printf '%s\n' 'Replace the example.com origin and host with the real browser-facing hostname.' >&2; exit 2 ;;
  esac
  if { [ -z "$bootstrap_email" ] && [ -n "$bootstrap_password" ]; } || { [ -n "$bootstrap_email" ] && [ -z "$bootstrap_password" ]; }; then
    printf '%s\n' 'Set both bootstrap Admin values for a fresh server, or clear both after the first Admin can sign in.' >&2
    exit 2
  fi
  if [ -n "$bootstrap_password" ] && [ "${#bootstrap_password}" -lt 15 ]; then
    printf '%s\n' 'The bootstrap Admin password must contain at least 15 characters.' >&2
    exit 2
  fi
  if [ -z "$bootstrap_email" ]; then
    printf '%s\n' 'WARNING: Bootstrap Admin credentials are cleared. This start will succeed only if an active Admin already exists.' >&2
  fi
}

print_server_login_hint() {
  [ "$DEPLOYMENT" = "server" ] || return 0
  bootstrap_email=$(env_value CCM_BOOTSTRAP_ADMIN_EMAIL "")
  if [ -n "$bootstrap_email" ]; then
    printf 'Login email: %s\n' "$bootstrap_email"
    printf '%s\n' 'Initial password: use the value in .env (not displayed).'
  else
    printf '%s\n' 'Login email: use an existing Admin account.'
  fi
}

refresh_local() {
  if [ "$DEPLOYMENT" = "server" ]; then
    printf '%s\n' 'server mode cannot be refreshed; use a reviewed PostgreSQL backup/restore procedure' >&2
    exit 2
  fi
  project=$(env_value COMPOSE_PROJECT_NAME "$(basename "$PROJECT_ROOT" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9_-')")
  targets=""
  for key in ccm_sqlite_data ccm_file_data; do
    for name in $(docker volume ls --quiet --filter "label=com.docker.compose.project=$project" --filter "label=com.docker.compose.volume=$key"); do
      label=$(docker volume inspect --format '{{ index .Labels "com.docker.compose.volume" }}' "$name")
      [ "$label" = "$key" ] || { printf 'Refusing unverified volume: %s\n' "$name" >&2; exit 2; }
      targets="$targets $name"
    done
  done
  printf '%s\n' 'Refresh targets (and nothing else):'
  if [ -n "$(printf '%s' "$targets" | tr -d ' ')" ]; then
    for target in $targets; do printf '  %s\n' "$target"; done
  else
    printf '%s\n' '  No existing local data volumes found.'
  fi
  printf '%s\n' 'WARNING: This permanently removes local test data from ccm_sqlite_data and ccm_file_data.'
  if [ "$ASSUME_YES" != "true" ]; then
    printf '%s' 'Type REFRESH to continue: '
    read -r answer
    [ "$answer" = "REFRESH" ] || { printf '%s\n' 'Refresh cancelled.' >&2; exit 2; }
  fi
  compose down --remove-orphans
  for target in $targets; do docker volume rm "$target"; done
}

wait_ready() {
  port=$(env_value CCM_WEB_PORT 3000)
  attempt=1
  while [ "$attempt" -le 60 ]; do
    if curl --fail --silent "http://127.0.0.1:$port/api/v1/health/ready" >/dev/null 2>&1; then
      printf 'Ready: http://localhost:%s\n' "$port"
      return 0
    fi
    sleep 1
    attempt=$((attempt + 1))
  done
  compose ps
  printf '%s\n' 'The application did not become ready within 60 seconds.' >&2
  return 1
}

local_api() {
  action="$1"
  port=$(env_value CCM_WEB_PORT 3000)
  base="http://127.0.0.1:$port"
  cookie_file=$(mktemp)
  trap 'rm -f "$cookie_file"' EXIT HUP INT TERM
  csrf=$(curl --fail --silent --cookie-jar "$cookie_file" "$base/api/v1/auth/csrf" | sed -n 's/.*"csrf_token":"\([^"]*\)".*/\1/p')
  [ -n "$csrf" ] || { printf '%s\n' 'Could not obtain a local CSRF token.' >&2; exit 1; }
  if [ "$action" = "export" ]; then
    target=${ARCHIVE:-"$PROJECT_ROOT/compliance-control-backup.zip"}
    mkdir -p "$(dirname -- "$target")"
    curl --fail --silent --show-error --cookie "$cookie_file" -H "Origin: $base" -H "X-CSRF-Token: $csrf" -X POST -o "$target" "$base/api/v1/exports"
    printf 'Backup written to %s\n' "$target"
  else
    [ -n "$ARCHIVE" ] && [ -f "$ARCHIVE" ] || { printf '%s\n' 'Restore requires --archive <path>.' >&2; exit 2; }
    curl --fail --silent --show-error --cookie "$cookie_file" -H "Origin: $base" -H "X-CSRF-Token: $csrf" -F "file=@$ARCHIVE" -X POST "$base/api/v1/exports/restore"
    printf '%s\n' 'Backup restored.'
  fi
  rm -f "$cookie_file"
  trap - EXIT HUP INT TERM
}

check_server_configuration
[ "$REFRESH" = "true" ] && refresh_local

case "$MODE" in
  start) compose up -d --build; wait_ready; print_server_login_hint ;;
  status) compose ps ;;
  down) compose down --remove-orphans ;;
  export) local_api export ;;
  restore) local_api restore ;;
esac
