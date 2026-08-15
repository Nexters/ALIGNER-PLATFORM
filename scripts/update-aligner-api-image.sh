#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 1 ]]; then
  echo "사용법: $0 ghcr.io/nexters/aligner-server@sha256:<64-hex>" >&2
  exit 2
fi

image_reference=$1
if [[ ! "$image_reference" =~ ^ghcr\.io/nexters/aligner-server@sha256:[0-9a-f]{64}$ ]]; then
  echo "ALIGNER-SERVER의 GHCR SHA256 digest만 사용할 수 있습니다." >&2
  exit 1
fi

repo_root=$(cd "$(dirname "$0")/.." && pwd)
deployment="$repo_root/gitops/apps/aligner-api/base/deployment.yaml"
IMAGE_REFERENCE="$image_reference" perl -0pi -e \
  's#image: ghcr\.io/nexters/aligner-server\@sha256:[0-9a-f]{64}#image: $ENV{IMAGE_REFERENCE}#' \
  "$deployment"

grep -Fq "image: $image_reference" "$deployment"
