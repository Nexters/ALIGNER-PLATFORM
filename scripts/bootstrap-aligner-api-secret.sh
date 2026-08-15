#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 2 ]]; then
  echo "사용법: $0 <kubectl-context> <application-secret.properties>" >&2
  exit 2
fi

context=$1
secret_file=$2
repo_root=$(cd "$(dirname "$0")/.." && pwd)
contract="$repo_root/gitops/apps/aligner-api/runtime-secret.keys"

if [[ ! -f "$secret_file" ]]; then
  echo "시크릿 파일을 찾을 수 없습니다: $secret_file" >&2
  exit 1
fi

expected=$(sort "$contract")
if ! actual=$(awk -F= '
  /^[[:space:]]*($|#)/ { next }
  !/^[A-Z][A-Z0-9_]*=/ { invalid = 1; next }
  { print $1 }
  END { exit invalid }
' "$secret_file" | sort); then
  echo "시크릿 파일은 KEY=VALUE 형식만 사용할 수 있습니다." >&2
  exit 1
fi
if [[ "$actual" != "$expected" ]]; then
  echo "시크릿 파일의 key가 runtime-secret.keys와 정확히 일치해야 합니다." >&2
  exit 1
fi

if grep -Eq '^[A-Z][A-Z0-9_]*=$' "$secret_file"; then
  echo "빈 환경변수 값이 있습니다." >&2
  exit 1
fi

kubectl --context "$context" get namespace aligner >/dev/null
kubectl --context "$context" -n aligner create secret generic aligner-api-secrets \
  --from-env-file="$secret_file" \
  --dry-run=client \
  -o yaml | kubectl --context "$context" apply -f - >/dev/null

if kubectl --context "$context" -n aligner get deployment aligner-api >/dev/null 2>&1; then
  kubectl --context "$context" -n aligner rollout restart deployment/aligner-api >/dev/null
  kubectl --context "$context" -n aligner rollout status deployment/aligner-api --timeout=5m
fi
echo "aligner/aligner-api-secrets를 생성하거나 갱신했습니다."
