#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/../../../.." && pwd)
render_dir=$(mktemp -d)
trap 'rm -rf "$render_dir"' EXIT

# This checker validates the intentionally fail-closed pre-production state;
# it is not a runtime readiness or node-failure test.
grep -Eq '^resources: \[\]$' "$repo_root/gitops/apps/kustomization.yaml"
if grep -Eq '^  - (data|apps)\.yaml$' "$repo_root/gitops/clusters/prod/kustomization.yaml"; then
  echo "fail-closed cluster must not include data or apps" >&2
  exit 1
fi

for overlay in normal degraded maintenance; do
  kubectl kustomize "$repo_root/gitops/apps/aligner-api/overlays/$overlay" > "$render_dir/$overlay.yaml"
  grep -Eq '^kind: Deployment$' "$render_dir/$overlay.yaml"
  grep -Eq '^kind: PodDisruptionBudget$' "$render_dir/$overlay.yaml"
  grep -Eq '^kind: HTTPRoute$' "$render_dir/$overlay.yaml"
  grep -Eq 'aligner-api-default-deny' "$render_dir/$overlay.yaml"
  if grep -Eq '^kind: Namespace$|image: .*:latest' "$render_dir/$overlay.yaml"; then
    echo "$overlay contains a forbidden namespace or mutable image" >&2
    exit 1
  fi
  if grep -Eq 'startupProbe:|readinessProbe:|livenessProbe:|port: 443' "$render_dir/$overlay.yaml"; then
    echo "$overlay guesses an unverified probe or TLS port" >&2
    exit 1
  fi
done

grep -Eq 'aligner-postgresql-rw' "$repo_root/gitops/apps/aligner-api/README.md"
grep -Eq 'aligner-redis' "$repo_root/gitops/apps/aligner-api/README.md"
grep -Eq 'Do not guess Actuator paths' "$repo_root/gitops/apps/aligner-api/README.md"
grep -Eq 'ghcr.io/nexters/aligner-server@sha256:[0-9a-f]{64}' "$render_dir/normal.yaml"
grep -Eq 'name: aligner-api-secrets' "$render_dir/normal.yaml"
