#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bootstrap_dir="$root_dir/bootstrap"
ui_dir="$root_dir/argocd-ui"
policy="$root_dir/../../../../docs/runbooks/tailscale-policy.hujson"

kubectl kustomize "$bootstrap_dir" >/dev/null
kubectl kustomize "$ui_dir" >/dev/null

grep -q 'projectSlug: aligner-cluster-services' "$bootstrap_dir/secret-store.yaml"
grep -q 'name: operator-oauth' "$bootstrap_dir/tailscale-operator-oauth.yaml"
if grep -Eq 'tskey-|clientSecret: [^ ]|client_id: [^ ]' "$bootstrap_dir"/*.yaml; then
  echo "cluster services manifests must not contain credential values" >&2
  exit 1
fi
grep -q 'kind: ProxyGroup' "$ui_dir/proxy-group.yaml"
grep -q 'replicas: 2' "$ui_dir/proxy-group.yaml"
grep -q 'tag:aligner-argocd' "$ui_dir/proxy-group.yaml"
grep -q 'ingressClassName: tailscale' "$ui_dir/ingress.yaml"
grep -q 'server.insecure: "true"' "$ui_dir/argocd-cmd-params.yaml"
grep -q 'tag:aligner-k8s-operator' "$policy"
grep -q 'tag:aligner-argocd' "$policy"
