#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/../../../.." && pwd)
render_dir=$(mktemp -d)
trap 'rm -rf "$render_dir"' EXIT

# This checker validates the intentionally fail-closed pre-production state;
# it is not a runtime readiness or node-failure test.
rg -q '^resources: \[\]$' "$repo_root/gitops/apps/kustomization.yaml"
! rg -q '^  - (data|apps)\.yaml$' "$repo_root/gitops/clusters/prod/kustomization.yaml"

for overlay in normal degraded maintenance; do
  kubectl kustomize "$repo_root/gitops/apps/aligner-api/overlays/$overlay" > "$render_dir/$overlay.yaml"
  rg -q '^kind: Deployment$' "$render_dir/$overlay.yaml"
  rg -q '^kind: PodDisruptionBudget$' "$render_dir/$overlay.yaml"
  rg -q '^kind: HTTPRoute$' "$render_dir/$overlay.yaml"
  rg -q 'aligner-api-default-deny' "$render_dir/$overlay.yaml"
  ! rg -q '^kind: Namespace$' "$render_dir/$overlay.yaml"
  ! rg -q 'startupProbe:|readinessProbe:|livenessProbe:|port: 443' "$render_dir/$overlay.yaml"
done

rg -q 'aligner-postgresql-rw' "$repo_root/gitops/apps/aligner-api/README.md"
rg -q 'aligner-redis' "$repo_root/gitops/apps/aligner-api/README.md"
rg -q 'Do not guess Actuator paths' "$repo_root/gitops/apps/aligner-api/README.md"
rg -q 'ghcr.io/nexters/aligner-server:latest' "$render_dir/normal.yaml"
rg -q 'name: aligner-api-secrets' "$render_dir/normal.yaml"
rg -q 'SPRING_PROFILES_ACTIVE' "$render_dir/normal.yaml"
test -f "$repo_root/gitops/apps/aligner-api/runtime-secret.keys"

