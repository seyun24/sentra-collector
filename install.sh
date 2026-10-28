#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
action=${1:-install}
case "$action" in install|update|status|logs|stop|uninstall|check) ;; *) echo 'Usage: bash install.sh [install|update|status|logs|stop|uninstall|check]' >&2; exit 2;; esac
[[ $(uname -s) == Linux ]] || { echo 'Native Linux is required.' >&2; exit 1; }
command -v docker >/dev/null || { echo 'Install Docker Engine and Docker Compose first: https://docs.docker.com/engine/install/ubuntu/' >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo 'Docker is unavailable. Start Docker or run this script with sudo.' >&2; exit 1; }
compose=(docker compose --project-name sentra-collector -f compose.yml)
[[ ! -f compose.override.yml ]] || compose+=(-f compose.override.yml)
# raw env_file support requires Compose >= 2.30.0.
version=$(docker compose version --short)
version=${version#v}
IFS=. read -r major minor patch <<< "$version"
if (( major < 2 || (major == 2 && minor < 30) )); then
  echo 'Docker Compose 2.30.0 or newer is required.' >&2; exit 1
fi
if [[ ! -f collector.env ]]; then
  echo 'Save the Collector settings issued by Sentra to collector.env first (see collector.env.example).' >&2
  exit 1
fi
chmod 600 collector.env
case "$action" in
  install|update|check)
    python3 validate_config.py
    "${compose[@]}" config --quiet
    ;;
esac
case "$action" in
  install|update)
    "${compose[@]}" pull collector
    "${compose[@]}" up -d --no-build collector
    "${compose[@]}" ps
    echo 'Started. Check Collector heartbeat in your Sentra workspace; a running container alone does not prove ingestion succeeds.'
    ;;
  check) echo 'Configuration is valid (no ingestion connection test performed).' ;;
  status) "${compose[@]}" ps ;;
  logs) "${compose[@]}" logs --tail 100 -f collector ;;
  stop) "${compose[@]}" stop collector ;;
  uninstall) "${compose[@]}" down; echo 'Collector removed; state volume and collector.env retained.' ;;
esac
