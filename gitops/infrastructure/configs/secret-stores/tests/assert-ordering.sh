#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/../../../../.." && pwd)
render_dir=$(mktemp -d)
trap 'rm -rf "$render_dir"' EXIT

argocd_cm="$repo_root/ansible/roles/argocd_bootstrap/templates/argocd-cm-kustomize.yaml.j2"
external_secrets="$repo_root/gitops/infrastructure/controllers/external-secrets/application.yaml"
secret_stores="$repo_root/gitops/infrastructure/configs/secret-stores"

# multiline assertions — perl -0 is portable across macOS and Linux
perl -0 -ne 'exit 1 unless /resource\.customizations\.health\.argoproj\.io_Application: \|\n    hs = \{\}\n    hs\.status = "Progressing".*hs\.status = obj\.status\.health\.status.*hs\.message = obj\.status\.health\.message/s' "$argocd_cm"
perl -0 -ne 'exit 1 unless /managedNamespaceMetadata:\n      labels:\n        pod-security\.kubernetes\.io\/enforce: restricted\n        pod-security\.kubernetes\.io\/enforce-version: latest/s' "$external_secrets"
grep -q 'CreateNamespace=true' "$external_secrets"
if test -e "$secret_stores/namespace.yaml"; then exit 1; fi
if grep -q 'namespace\.yaml' "$secret_stores/kustomization.yaml"; then exit 1; fi

kubectl kustomize "$repo_root/gitops/clusters/prod" > "$render_dir/prod.yaml"
kubectl kustomize "$secret_stores" > "$render_dir/secret-stores.yaml"
perl -0 -ne 'exit 1 unless /argocd\.argoproj\.io\/sync-wave: "0"\n  name: aligner-prod-controllers/s' "$render_dir/prod.yaml"
perl -0 -ne 'exit 1 unless /argocd\.argoproj\.io\/sync-wave: "1"\n  name: aligner-prod-configs/s' "$render_dir/prod.yaml"
if grep -q '^kind: Namespace$' "$render_dir/secret-stores.yaml"; then exit 1; fi
