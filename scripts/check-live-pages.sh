#!/usr/bin/env bash
set -euo pipefail

check_page() {
  local url=$1 expected=$2 actual
  actual=$(curl --fail --silent --show-error --location --connect-timeout 8 --max-time 20 \
    "$url?download-sync=${GITHUB_RUN_ID:-local}-$(date +%s)" | sha256sum)
  if [[ "${actual%% *}" != "$expected" ]]; then
    echo "The deployed page differs from this build: $url" >&2
    return 1
  fi
  echo "Verified $url"
}

check_page 'https://deepernetwork.github.io/' "$1"
check_page 'https://deepernetwork.github.io/ru/' "$2"
