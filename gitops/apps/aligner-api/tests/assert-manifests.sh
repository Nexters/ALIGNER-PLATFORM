#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/../../../.." && pwd)
render_dir=$(mktemp -d)
trap 'rm -rf "$render_dir"' EXIT

# This checker validates the intentionally fail-closed pre-production state;
# it is not a runtime readiness or node-failure test.
rg -q '^resources: \[\]$' "$repo_root/gitops/apps/kustomization.yaml"
assert_not_found() {
  local pattern="$1"
  local file="$2"
  set +e
  rg -q "$pattern" "$file"
  local status=$?
  set -e
  if [ "$status" -eq 0 ]; then
    echo "Assertion failed: unexpected match for '$pattern' in $file" >&2
    exit 1
  elif [ "$status" -ne 1 ]; then
    echo "Ripgrep error (exit code $status) while searching for '$pattern' in $file" >&2
    exit "$status"
  fi
}

assert_not_found '^  - (data|apps)\.yaml$' "$repo_root/gitops/clusters/prod/kustomization.yaml"

for overlay in normal degraded maintenance; do
  kubectl kustomize "$repo_root/gitops/apps/aligner-api/overlays/$overlay" > "$render_dir/$overlay.yaml"
  rg -q '^kind: Deployment$' "$render_dir/$overlay.yaml"
  rg -q '^kind: PodDisruptionBudget$' "$render_dir/$overlay.yaml"
  rg -q '^kind: HTTPRoute$' "$render_dir/$overlay.yaml"
  rg -q 'aligner-api-default-deny' "$render_dir/$overlay.yaml"
  assert_not_found '^kind: Namespace$' "$render_dir/$overlay.yaml"
  assert_not_found 'startupProbe:|readinessProbe:|livenessProbe:|port: 443' "$render_dir/$overlay.yaml"
done

rg -q 'aligner-postgresql-rw' "$repo_root/gitops/apps/aligner-api/README.md"
rg -q 'aligner-redis' "$repo_root/gitops/apps/aligner-api/README.md"
rg -q 'Do not guess Actuator paths' "$repo_root/gitops/apps/aligner-api/README.md"
rg -q 'ghcr.io/nexters/aligner-server:latest' "$render_dir/normal.yaml"
rg -q 'name: aligner-api-secrets' "$render_dir/normal.yaml"
rg -q 'SPRING_PROFILES_ACTIVE' "$render_dir/normal.yaml"
test -f "$repo_root/gitops/apps/aligner-api/runtime-secret.keys"

