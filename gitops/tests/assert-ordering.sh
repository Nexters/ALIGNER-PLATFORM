#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/../.." && pwd)
render_dir=$(mktemp -d)
trap 'rm -rf "$render_dir"' EXIT

argocd_cm="$repo_root/ansible/roles/argocd_bootstrap/templates/argocd-cm-kustomize.yaml.j2"

# multiline assertions — perl -0 is portable across macOS and Linux
perl -0 -ne 'exit 1 unless /resource\.customizations\.health\.argoproj\.io_Application: \|\n    hs = \{\}\n    hs\.status = "Progressing".*hs\.status = obj\.status\.health\.status.*hs\.message = obj\.status\.health\.message/s' "$argocd_cm"

kubectl kustomize "$repo_root/gitops/clusters/prod" > "$render_dir/prod.yaml"
perl -0 -ne 'exit 1 unless /argocd\.argoproj\.io\/sync-wave: "0"\n  name: aligner-prod-controllers/s' "$render_dir/prod.yaml"
perl -0 -ne 'exit 1 unless /argocd\.argoproj\.io\/sync-wave: "1"\n  name: aligner-prod-configs/s' "$render_dir/prod.yaml"
