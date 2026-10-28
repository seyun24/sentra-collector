#!/usr/bin/env bash
set -euo pipefail
# This file can be downloaded alone; the helper is fetched from the same release.
cd "$(dirname "${BASH_SOURCE[0]}")"
action=${1:-install}
case "$action" in install|update|status|logs|stop|uninstall|check) ;; *) echo 'Usage: bash install.sh [install|update|status|logs|stop|uninstall|check]' >&2; exit 2;; esac
[[ $(uname -s) == Linux ]] || { echo 'Native Linux is required.' >&2; exit 1; }
command -v python3 >/dev/null || { echo 'Python 3 is required.' >&2; exit 1; }
command -v docker >/dev/null || { echo 'Install Docker Engine and Compose: https://docs.docker.com/engine/install/ubuntu/' >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo 'Start Docker or run this script with sudo.' >&2; exit 1; }
version=$(docker compose version --short)
version=${version#v}
IFS=. read -r major minor patch <<< "$version"
if (( major < 2 || (major == 2 && minor < 30) )); then
  echo 'Docker Compose 2.30.0 or newer is required.' >&2; exit 1
fi
case "$action" in
  install|update|check)
    [[ -f collector.env ]] || { echo 'Save issued settings as collector.env beside install.sh first.' >&2; exit 1; }
    chmod 600 collector.env
    if [[ ! -f validate_config.py ]]; then
      command -v curl >/dev/null || { echo 'curl is required to download the helper.' >&2; exit 1; }
      helper_tmp=$(mktemp ./validate_config.XXXXXX)
      trap 'rm -f "$helper_tmp"' EXIT
      curl --fail --silent --show-error --location \
        https://raw.githubusercontent.com/seyun24/sentra-collector/v0.2.0/validate_config.py -o "$helper_tmp"
      mv "$helper_tmp" validate_config.py
      trap - EXIT
    fi
    python3 validate_config.py
    ;;
esac
[[ -f compose.generated.json ]] || { echo 'Run install.sh check/install first to generate configuration.' >&2; exit 1; }
compose=(docker compose --project-name sentra-collector -f compose.generated.json)
case "$action" in
  install|update)
    "${compose[@]}" config --quiet
    "${compose[@]}" pull collector
    "${compose[@]}" up -d --no-build collector
    "${compose[@]}" ps
    echo 'Check heartbeat and received data in Sentra; running does not prove ingestion succeeds.'
    ;;
  check) "${compose[@]}" config --quiet; echo 'Configuration valid; network delivery not tested.' ;;
  status) "${compose[@]}" ps ;;
  logs) "${compose[@]}" logs --tail 100 -f collector ;;
  stop) "${compose[@]}" stop collector ;;
  uninstall) "${compose[@]}" down; echo 'State volume and settings retained.' ;;
esac
