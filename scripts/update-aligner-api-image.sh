#!/usr/bin/env bash
set -euo pipefail

# scripts/update-aligner-api-image.sh
# Updates the container image reference in ALIGNER GitOps deployment manifests
# and validates the updated image reference.

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DEFAULT_REPO="ghcr.io/nexters/aligner-server"
API_DEPLOYMENT="$repo_root/gitops/apps/aligner-api/base/deployment.yaml"
SANDBOX_DEPLOYMENT="$repo_root/gitops/apps/aligner-sandbox/base/deployment.yaml"

TARGET=""
IMAGE_INPUT=""
CUSTOM_FILE=""
DEFAULT_REPO_OVERRIDE=""
DRY_RUN=false

usage() {
  cat <<EOF
Usage: $0 [options] <image-reference-or-tag-or-digest>
       $0 [target] <image-reference-or-tag-or-digest>

Updates the container image in gitops deployment manifest(s) and validates the reference.

Targets:
  api (default)   gitops/apps/aligner-api/base/deployment.yaml
  sandbox         gitops/apps/aligner-sandbox/base/deployment.yaml
  all | both      Updates both api and sandbox deployments

Options:
  -t, --target <target>     Target to update: 'api', 'sandbox', 'all', 'both' (default: api)
  -f, --file <file-path>    Direct path to deployment.yaml
  -r, --repo <image-repo>   Base image repo when only tag or digest is passed (default: $DEFAULT_REPO)
  -d, --dry-run             Validate and show changes without writing to disk
  -h, --help                Show this help message

Examples:
  $0 ghcr.io/nexters/aligner-server:sha-1a2b3c4
  $0 --target sandbox ghcr.io/nexters/aligner-server@sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
  $0 -t all v1.0.0
  $0 sha-1a2b3c4
  $0 sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
EOF
}

POSITIONAL_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    -t|--target)
      if [ -z "${2:-}" ] || [[ "$2" =~ ^- ]]; then
        echo "ERROR: --target requires an argument (api, sandbox, all)" >&2
        exit 1
      fi
      TARGET="$2"
      shift 2
      ;;
    --target=*)
      TARGET="${1#*=}"
      shift
      ;;
    -f|--file)
      if [ -z "${2:-}" ] || [[ "$2" =~ ^- ]]; then
        echo "ERROR: --file requires a file path argument" >&2
        exit 1
      fi
      CUSTOM_FILE="$2"
      shift 2
      ;;
    --file=*)
      CUSTOM_FILE="${1#*=}"
      shift
      ;;
    -r|--repo)
      if [ -z "${2:-}" ] || [[ "$2" =~ ^- ]]; then
        echo "ERROR: --repo requires an image repo argument" >&2
        exit 1
      fi
      DEFAULT_REPO_OVERRIDE="$2"
      shift 2
      ;;
    --repo=*)
      DEFAULT_REPO_OVERRIDE="${1#*=}"
      shift
      ;;
    -d|--dry-run)
      DRY_RUN=true
      shift
      ;;
    *)
      POSITIONAL_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ -n "$DEFAULT_REPO_OVERRIDE" ]]; then
  DEFAULT_REPO="$DEFAULT_REPO_OVERRIDE"
fi

# Parse positional arguments
if [[ ${#POSITIONAL_ARGS[@]} -eq 1 ]]; then
  IMAGE_INPUT="${POSITIONAL_ARGS[0]}"
elif [[ ${#POSITIONAL_ARGS[@]} -eq 2 ]]; then
  arg1="${POSITIONAL_ARGS[0]}"
  arg2="${POSITIONAL_ARGS[1]}"
  if [[ "$arg1" =~ ^(api|sandbox|all|both)$ ]] && [[ -z "$TARGET" ]]; then
    TARGET="$arg1"
    IMAGE_INPUT="$arg2"
  elif [[ "$arg2" =~ ^(api|sandbox|all|both)$ ]] && [[ -z "$TARGET" ]]; then
    IMAGE_INPUT="$arg1"
    TARGET="$arg2"
  else
    echo "ERROR: Unexpected positional arguments: ${POSITIONAL_ARGS[*]}" >&2
    usage
    exit 1
  fi
elif [[ ${#POSITIONAL_ARGS[@]} -gt 2 ]]; then
  echo "ERROR: Too many arguments: ${POSITIONAL_ARGS[*]}" >&2
  usage
  exit 1
fi

if [[ -z "$IMAGE_INPUT" ]]; then
  echo "ERROR: Image reference, tag, or digest argument is required." >&2
  usage
  exit 1
fi

# Determine target files
TARGET_FILES=()

if [[ -n "$CUSTOM_FILE" ]]; then
  if [[ ! -f "$CUSTOM_FILE" ]]; then
    echo "ERROR: Specified deployment file does not exist: $CUSTOM_FILE" >&2
    exit 1
  fi
  TARGET_FILES+=("$CUSTOM_FILE")
else
  TARGET="${TARGET:-api}"
  case "$TARGET" in
    api)
      TARGET_FILES+=("$API_DEPLOYMENT")
      ;;
    sandbox)
      TARGET_FILES+=("$SANDBOX_DEPLOYMENT")
      ;;
    all|both)
      TARGET_FILES+=("$API_DEPLOYMENT" "$SANDBOX_DEPLOYMENT")
      ;;
    *)
      echo "ERROR: Invalid target '$TARGET'. Must be one of: api, sandbox, all, both" >&2
      exit 1
      ;;
  esac
fi

for f in "${TARGET_FILES[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "ERROR: Target deployment manifest does not exist: $f" >&2
    exit 1
  fi
done

# Resolve full image reference
RESOLVED_IMAGE=""

# Check if input is a raw digest sha256:...
if [[ "$IMAGE_INPUT" =~ ^sha256:[a-fA-F0-9]{64}$ ]]; then
  RESOLVED_IMAGE="${DEFAULT_REPO}@${IMAGE_INPUT}"
# Check if input is a tag without repo prefix (no slash and no sha256 prefix)
elif [[ ! "$IMAGE_INPUT" =~ / ]] && [[ ! "$IMAGE_INPUT" =~ ^sha256: ]]; then
  RESOLVED_IMAGE="${DEFAULT_REPO}:${IMAGE_INPUT}"
else
  RESOLVED_IMAGE="$IMAGE_INPUT"
fi

# Validate Image Reference
validate_image_reference() {
  local img="$1"

  # Reject empty or whitespace
  if [[ -z "$img" ]] || [[ "$img" =~ [[:space:]] ]]; then
    echo "ERROR: Image reference cannot be empty or contain whitespace: '$img'" >&2
    return 1
  fi

  # Reject invalid/placeholder image references
  if [[ "$img" =~ registry\.invalid ]] || [[ "$img" =~ @sha256:0{64} ]]; then
    echo "ERROR: Image reference must not be the placeholder 'registry.invalid' or all-zero digest: '$img'" >&2
    return 1
  fi

  # Must contain a tag (:tag) or digest (@sha256:hex) or both
  # Valid characters in docker references: [a-zA-Z0-9_./:-] and @sha256:[a-f0-9]{64}
  local valid_pattern='^([a-zA-Z0-9_.-]+(:[0-9]+)?/)?([a-zA-Z0-9_.-]+(/[a-zA-Z0-9_.-]+)*)(:[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,127})?(@sha256:[a-fA-F0-9]{64})?$'
  if [[ ! "$img" =~ $valid_pattern ]]; then
    echo "ERROR: Image reference '$img' does not match standard container image format." >&2
    return 1
  fi

  # Must have either tag or digest
  if [[ ! "$img" =~ :[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,127} ]] && [[ ! "$img" =~ @sha256:[a-fA-F0-9]{64} ]]; then
    echo "ERROR: Image reference must include a tag (e.g., :develop, :sha-1234567, :v1.0.0) or digest (@sha256:...): '$img'" >&2
    return 1
  fi

  return 0
}

if ! validate_image_reference "$RESOLVED_IMAGE"; then
  exit 1
fi

echo "== Validated Image Reference: $RESOLVED_IMAGE =="

# Update Deployment Manifest(s)
for target_file in "${TARGET_FILES[@]}"; do
  echo "Target manifest: $target_file"

  # Verify container 'api' exists in manifest
  if ! grep -q 'name: api' "$target_file"; then
    echo "ERROR: Container 'name: api' not found in $target_file" >&2
    exit 1
  fi

  if [[ "$DRY_RUN" == "true" ]]; then
    echo "[DRY-RUN] Would update image to: $RESOLVED_IMAGE in $target_file"
    continue
  fi

  # Perform Python-based in-place replacement to safely preserve formatting and comments
  python3 - <<PYEOF
import re
import sys

filepath = "$target_file"
new_image = "$RESOLVED_IMAGE"

with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Replace image: under containers where name is api
# Match pattern: (name:\s*api\s*\n\s*image:\s*)\S+ or (image:\s*)\S+(\s*\n\s*name:\s*api)
pattern = r'(name:\s*api\s*\n\s*image:\s*)\S+'
if re.search(pattern, content):
    updated_content = re.sub(pattern, r'\g<1>' + new_image, content)
else:
    pattern2 = r'(image:\s*)\S+(\s*\n\s*imagePullPolicy:[^\n]*\n\s*(?:securityContext:[^\n]*\n\s*(?:allowPrivilegeEscalation:[^\n]*\n\s*(?:capabilities:[^\n]*\n\s*(?:drop:[^\n]*\n\s*(?:-\s*ALL\s*\n\s*)?)?)?)?)?name:\s*api)'
    # fallback: replace first image under containers
    pattern3 = r'(image:\s*)\S+'
    updated_content = re.sub(pattern3, r'\g<1>' + new_image, content, count=1)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(updated_content)

PYEOF

  # Assert update succeeded and verify YAML validity
  python3 - <<PYEOF
import yaml
import sys

filepath = "$target_file"
expected_image = "$RESOLVED_IMAGE"

with open(filepath, "r", encoding="utf-8") as f:
    docs = list(yaml.safe_load_all(f))

found = False
for doc in docs:
    if not isinstance(doc, dict):
        continue
    if doc.get("kind") == "Deployment":
        containers = doc.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
        for c in containers:
            if c.get("name") == "api":
                if c.get("image") == expected_image:
                    found = True
                else:
                    print(f"ERROR: Image mismatch in {filepath}. Expected {expected_image}, found {c.get('image')}", file=sys.stderr)
                    sys.exit(1)

if not found:
    print(f"ERROR: Could not find container 'api' with image '{expected_image}' in {filepath}", file=sys.stderr)
    sys.exit(1)

print(f"✓ Verification passed for {filepath}")
PYEOF

done

if [[ "$DRY_RUN" == "true" ]]; then
  echo "Dry-run validation complete. No files modified."
  exit 0
fi

echo "Successfully updated image reference to '$RESOLVED_IMAGE'."
