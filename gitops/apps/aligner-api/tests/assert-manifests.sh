#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/../../../.." && pwd)
render_dir=$(mktemp -d)
trap 'rm -rf "$render_dir"' EXIT

assert_found() {
  local pattern="$1"
  local file="$2"
  if ! rg -q "$pattern" "$file"; then
    echo "Assertion failed: expected match for '$pattern' in $file" >&2
    exit 1
  fi
}

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

# Validate that apps and data are activated in gitops/clusters/prod/kustomization.yaml
assert_found '^  - data\.yaml$' "$repo_root/gitops/clusters/prod/kustomization.yaml"
assert_found '^  - apps\.yaml$' "$repo_root/gitops/clusters/prod/kustomization.yaml"

# Validate that aligner-api and aligner-sandbox are registered in gitops/apps/kustomization.yaml
assert_found 'aligner-api/overlays/normal' "$repo_root/gitops/apps/kustomization.yaml"
assert_found 'aligner-sandbox/base' "$repo_root/gitops/apps/kustomization.yaml"

for overlay in normal degraded maintenance; do
  kubectl kustomize "$repo_root/gitops/apps/aligner-api/overlays/$overlay" > "$render_dir/$overlay.yaml"
  rg -q '^kind: Deployment$' "$render_dir/$overlay.yaml"
  rg -q '^kind: PodDisruptionBudget$' "$render_dir/$overlay.yaml"
  rg -q '^kind: HTTPRoute$' "$render_dir/$overlay.yaml"
  rg -q 'aligner-api-default-deny' "$render_dir/$overlay.yaml"
  rg -q 'readinessProbe:' "$render_dir/$overlay.yaml"
  rg -q 'livenessProbe:' "$render_dir/$overlay.yaml"
  rg -q 'aligner-api-allow-external-https' "$render_dir/$overlay.yaml"
  assert_not_found '^kind: Namespace$' "$render_dir/$overlay.yaml"
done

rg -q 'aligner-postgresql-rw' "$repo_root/gitops/apps/aligner-api/README.md"
rg -q 'aligner-redis' "$repo_root/gitops/apps/aligner-api/README.md"
rg -q 'ghcr.io/nexters/aligner-server:latest' "$render_dir/normal.yaml"
rg -q 'name: aligner-api-secrets' "$render_dir/normal.yaml"
rg -q 'SPRING_PROFILES_ACTIVE' "$render_dir/normal.yaml"
test -f "$repo_root/gitops/apps/aligner-api/runtime-secret.keys"

echo "All active manifest assertions passed successfully."
