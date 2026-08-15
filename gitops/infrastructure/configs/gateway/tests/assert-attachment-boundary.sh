#!/usr/bin/env bash
set -euo pipefail

runtime_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../runtime" && pwd)"
gateway="$runtime_dir/gateway.yaml"

kubectl kustomize "$runtime_dir" >/dev/null

http_listener="$(awk '/- name: http$/,/    - name: https$/' "$gateway")"
https_listener="$(awk '/- name: https$/,/^$/' "$gateway")"

printf '%s\n' "$http_listener" | grep -q 'from: Same'
! printf '%s\n' "$http_listener" | grep -q 'gateway-access:'
printf '%s\n' "$https_listener" | grep -q 'from: Selector'
printf '%s\n' "$https_listener" | grep -q 'gateway-access: "true"'
grep -q '^kind: HTTPRoute$' "$runtime_dir/https-redirect.yaml"
grep -q '^  name: api-https-redirect$' "$runtime_dir/https-redirect.yaml"
grep -q '^  namespace: traefik$' "$runtime_dir/https-redirect.yaml"
grep -q '^      sectionName: http$' "$runtime_dir/https-redirect.yaml"
