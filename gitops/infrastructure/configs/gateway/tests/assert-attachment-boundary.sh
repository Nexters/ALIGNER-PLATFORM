#!/usr/bin/env bash
set -euo pipefail

runtime_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../runtime" && pwd)"
gateway="$runtime_dir/gateway.yaml"

kubectl kustomize "$runtime_dir" >/dev/null

http_listener="$(awk '/- name: http$/,/    - name: https$/' "$gateway")"
https_listener="$(awk '/- name: https$/,/^$/' "$gateway")"

printf '%s\n' "$http_listener" | rg -q 'from: Same'
! printf '%s\n' "$http_listener" | rg -q 'gateway-access:'
printf '%s\n' "$https_listener" | rg -q 'from: Selector'
printf '%s\n' "$https_listener" | rg -q 'gateway-access: "true"'
rg -U -q 'kind: HTTPRoute\nmetadata:\n  name: api-https-redirect\n  namespace: traefik[\s\S]*sectionName: http' "$runtime_dir/https-redirect.yaml"
