#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/../../../.." && pwd)
render_dir=$(mktemp -d)
trap 'rm -rf "$render_dir"' EXIT

assert_found() {
  local pattern="$1"
  local file="$2"
  if ! grep -Eq "$pattern" "$file"; then
    echo "Assertion failed: expected match for '$pattern' in $file" >&2
    exit 1
  fi
}

assert_not_found() {
  local pattern="$1"
  local file="$2"
  set +e
  grep -Eq "$pattern" "$file"
  local status=$?
  set -e
  if [ "$status" -eq 0 ]; then
    echo "Assertion failed: unexpected match for '$pattern' in $file" >&2
    exit 1
  elif [ "$status" -ne 1 ]; then
    echo "Grep error (exit code $status) while searching for '$pattern' in $file" >&2
    exit "$status"
  fi
}

# Validate that apps and data are activated in gitops/clusters/prod/kustomization.yaml
assert_found '^[[:space:]]*-[[:space:]]*data\.yaml$' "$repo_root/gitops/clusters/prod/kustomization.yaml"
assert_found '^[[:space:]]*-[[:space:]]*apps\.yaml$' "$repo_root/gitops/clusters/prod/kustomization.yaml"

# Validate that aligner-api and aligner-sandbox are registered in gitops/apps/kustomization.yaml
assert_found 'aligner-api/overlays/normal' "$repo_root/gitops/apps/kustomization.yaml"
assert_found 'aligner-sandbox/base' "$repo_root/gitops/apps/kustomization.yaml"

for overlay in normal degraded maintenance; do
  kubectl kustomize "$repo_root/gitops/apps/aligner-api/overlays/$overlay" > "$render_dir/$overlay.yaml"
  grep -q '^kind: Deployment$' "$render_dir/$overlay.yaml"
  grep -q '^kind: PodDisruptionBudget$' "$render_dir/$overlay.yaml"
  grep -q '^kind: HTTPRoute$' "$render_dir/$overlay.yaml"
  grep -q 'aligner-api-default-deny' "$render_dir/$overlay.yaml"
  grep -q 'readinessProbe:' "$render_dir/$overlay.yaml"
  grep -q 'livenessProbe:' "$render_dir/$overlay.yaml"
  grep -q 'aligner-api-allow-external-https' "$render_dir/$overlay.yaml"
  assert_not_found '^kind: Namespace$' "$render_dir/$overlay.yaml"
done

grep -q 'aligner-postgresql-rw' "$repo_root/gitops/apps/aligner-api/README.md"
grep -q 'aligner-redis' "$repo_root/gitops/apps/aligner-api/README.md"
grep -q 'ghcr.io/nexters/aligner-server:latest' "$render_dir/normal.yaml"
grep -q 'name: aligner-api-secrets' "$render_dir/normal.yaml"
grep -q 'SPRING_PROFILES_ACTIVE' "$render_dir/normal.yaml"
test -f "$repo_root/gitops/apps/aligner-api/runtime-secret.keys"

echo "All active manifest assertions passed successfully."
