#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/../../../.." && pwd)
deployment="$repo_root/gitops/apps/aligner-api/base/deployment.yaml"
contract="$repo_root/gitops/apps/aligner-api/runtime-secret.keys"

expected=$(printf '%s\n' \
  DB_URL DB_USERNAME DB_PASSWORD SERVER_PORT JWT_SECRET \
  KAKAO_CLIENT_ID KAKAO_CLIENT_SECRET SPRINGDOC_ENABLED YMOVE_API_KEY | sort)
actual=$(sort "$contract")
if [[ "$actual" != "$expected" ]]; then
  echo "ALIGNER-SERVER와 Platform의 환경변수 계약이 다릅니다." >&2
  exit 1
fi

grep -Eq 'image: ghcr\.io/nexters/aligner-server@sha256:[0-9a-f]{64}$' "$deployment"
grep -Fq 'name: aligner-api-secrets' "$deployment"
if grep -Eq 'registry\.invalid|aligner-api-runtime|DATABASE_URL|OAUTH_CLIENT_SECRET' "$deployment"; then
  echo "deployment contains an obsolete runtime contract" >&2
  exit 1
fi
if find "$repo_root/gitops" -type f -name '*.yaml' \
  -exec grep -El '^kind: (ExternalSecret|SecretStore|Secret)$' {} + | grep -q .; then
  echo "secret values or external secret controllers must not be stored in Git" >&2
  exit 1
fi
