#!/usr/bin/env bash
set -euo pipefail

runtime_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../runtime" && pwd)"
gateway_dir="$(cd "$runtime_dir/.." && pwd)"
gateway="$runtime_dir/gateway.yaml"
redirect="$runtime_dir/https-redirect.yaml"
parent_kustomization="$gateway_dir/kustomization.yaml"

# 1. Kustomize build checks
kubectl kustomize "$runtime_dir" >/dev/null
kubectl kustomize "$gateway_dir" >/dev/null

# 2. Parent kustomization must include runtime
grep -Eq '^[[:space:]]*-[[:space:]]*runtime[[:space:]]*$' "$parent_kustomization"

# 3. Gateway metadata & spec assertions
grep -q '^  name: platform-gateway$' "$gateway"
grep -q '^  namespace: traefik$' "$gateway"
grep -q '^  gatewayClassName: platform-traefik$' "$gateway"

# 4. Listener attachment assertions
http_listener="$(awk '/- name: http$/,/    - name: https$/' "$gateway")"
https_listener="$(awk '/- name: https$/,/^$/' "$gateway")"

printf '%s\n' "$http_listener" | grep -q 'from: Same'
if printf '%s\n' "$http_listener" | grep -q 'gateway-access:'; then
  echo "HTTP listener must not select gateway-access namespaces" >&2
  exit 1
fi

printf '%s\n' "$https_listener" | grep -q 'from: Selector'
printf '%s\n' "$https_listener" | grep -q 'gateway-access: "true"'
printf '%s\n' "$https_listener" | grep -q 'name: aligner-api-tls'

# 5. HTTPS redirect HTTPRoute assertions
grep -q '^kind: HTTPRoute$' "$redirect"
grep -q '^  name: api-https-redirect$' "$redirect"
grep -q '^  namespace: traefik$' "$redirect"
grep -q 'name: platform-gateway' "$redirect"
grep -q 'sectionName: http' "$redirect"
grep -q 'statusCode: 308' "$redirect"
grep -q 'scheme: https' "$redirect"
grep -q 'api.aligneryoga.com' "$redirect"
grep -q 'aligneryoga.com' "$redirect"
grep -q 'dev-api.aligneryoga.com' "$redirect"

# 6. No .invalid placeholder hostnames in manifests
if grep -Eq '\.invalid' "$runtime_dir"/*.yaml "$gateway_dir"/*.yaml; then
  echo ".invalid hostnames must not exist in runtime or gateway manifests" >&2
  exit 1
fi

echo "All Gateway and attachment boundary assertions passed."

