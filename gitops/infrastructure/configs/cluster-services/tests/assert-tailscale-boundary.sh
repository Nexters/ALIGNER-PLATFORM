#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ui_dir="$root_dir/argocd-ui"
policy="$root_dir/../../../../docs/runbooks/tailscale-policy.hujson"
controllers="$root_dir/../../controllers"

kubectl kustomize "$ui_dir" >/dev/null

grep -q 'chart: tailscale-operator' "$controllers/tailscale-operator.application.yaml"
if grep -Eq 'tskey-|clientSecret: [^ ]|client_id: [^ ]' \
  "$controllers/tailscale-operator.application.yaml" \
  "$controllers/tailscale-argocd-ui.application.yaml" \
  "$ui_dir"/*.yaml; then
  echo "Tailscale manifests must not contain credential values" >&2
  exit 1
fi
if grep -Eq 'aligner-cluster-services|tailscale-external-secrets|tailscale-bootstrap' \
  "$controllers/kustomization.yaml"; then
  echo "obsolete Tailscale bootstrap controllers must not be enabled" >&2
  exit 1
fi
grep -q 'kind: ProxyGroup' "$ui_dir/proxy-group.yaml"
grep -q 'replicas: 2' "$ui_dir/proxy-group.yaml"
grep -q 'tag:aligner-argocd' "$ui_dir/proxy-group.yaml"
grep -q 'ingressClassName: tailscale' "$ui_dir/ingress.yaml"
grep -q 'server.insecure: "true"' "$ui_dir/argocd-cmd-params.yaml"
grep -q 'tag:aligner-k8s-operator' "$policy"
grep -q 'tag:aligner-argocd' "$policy"
