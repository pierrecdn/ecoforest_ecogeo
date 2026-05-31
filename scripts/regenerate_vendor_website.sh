#!/usr/bin/env bash
set -euo pipefail

out="${VENDOR_WEBSITE_DIR:-custom_components/ecoforest_ecogeoair/api/vendor_website}"

if [[ $# -lt 1 ]]; then
  cat >&2 <<'EOF'
Usage: scripts/regenerate_vendor_website.sh AUTHENTICATED_URL [wget options...]

Example:
  scripts/regenerate_vendor_website.sh http://192.168.1.50/webpages/gama/fr/webpages/Principal.html --user admin --password secret
EOF
  exit 2
fi

url="$1"
shift

rm -rf "$out"
mkdir -p "$out"

wget \
  --recursive \
  --level=inf \
  --page-requisites \
  --convert-links \
  --adjust-extension \
  --no-parent \
  --no-host-directories \
  --directory-prefix="$out" \
  --execute robots=off \
  "$@" \
  "$url"
