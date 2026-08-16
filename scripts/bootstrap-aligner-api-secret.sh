#!/usr/bin/env bash
set -euo pipefail

# scripts/bootstrap-aligner-api-secret.sh
# Validates and creates/updates the aligner-api-secrets Secret in a target namespace.

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KEYS_FILE="$repo_root/gitops/apps/aligner-api/runtime-secret.keys"

SECRET_FILE=""
KUBECONFIG_FILE=""
NAMESPACE=""
POSITIONAL_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      echo "Usage: $0 <secret-file> [kubeconfig-file] [namespace]"
      echo "       $0 --secret-file <secret-file> [--kubeconfig <kubeconfig-file>] [--namespace <namespace>]"
      echo ""
      echo "Bootstraps the 'aligner-api-secrets' Kubernetes Secret in the specified namespace."
      echo ""
      echo "Arguments & Options:"
      echo "  <secret-file>            Path to file containing key=value secrets"
      echo "  [kubeconfig-file]        Path to kubeconfig file (optional)"
      echo "  [namespace]              Target namespace (default: aligner, e.g. aligner-sandbox)"
      echo "  -k, --kubeconfig <path>  Explicit path to kubeconfig file"
      echo "  -n, --namespace <ns>     Target Kubernetes namespace"
      echo "  -s, --secret-file <path> Path to secret file"
      echo "  -h, --help               Show this help message"
      exit 0
      ;;
    -k|--kubeconfig)
      if [ -z "${2:-}" ] || [[ "$2" =~ ^- ]]; then
        echo "ERROR: --kubeconfig requires a path argument" >&2
        exit 1
      fi
      KUBECONFIG_FILE="$2"
      shift 2
      ;;
    --kubeconfig=*)
      KUBECONFIG_FILE="${1#*=}"
      shift
      ;;
    -n|--namespace)
      if [ -z "${2:-}" ] || [[ "$2" =~ ^- ]]; then
        echo "ERROR: --namespace requires a namespace argument" >&2
        exit 1
      fi
      NAMESPACE="$2"
      shift 2
      ;;
    --namespace=*)
      NAMESPACE="${1#*=}"
      shift
      ;;
    -s|--secret-file)
      if [ -z "${2:-}" ] || [[ "$2" =~ ^- ]]; then
        echo "ERROR: --secret-file requires a file argument" >&2
        exit 1
      fi
      SECRET_FILE="$2"
      shift 2
      ;;
    --secret-file=*)
      SECRET_FILE="${1#*=}"
      shift
      ;;
    *)
      POSITIONAL_ARGS+=("$1")
      shift
      ;;
  esac
done

# Resolve positional arguments
if [ -z "$SECRET_FILE" ] && [ ${#POSITIONAL_ARGS[@]} -ge 1 ]; then
  SECRET_FILE="${POSITIONAL_ARGS[0]}"
fi

if [ -z "$KUBECONFIG_FILE" ] && [ ${#POSITIONAL_ARGS[@]} -ge 2 ]; then
  if [ -n "${POSITIONAL_ARGS[1]}" ]; then
    KUBECONFIG_FILE="${POSITIONAL_ARGS[1]}"
  fi
fi

if [ -z "$NAMESPACE" ]; then
  if [ ${#POSITIONAL_ARGS[@]} -ge 3 ] && [ -n "${POSITIONAL_ARGS[2]}" ]; then
    NAMESPACE="${POSITIONAL_ARGS[2]}"
  else
    NAMESPACE="aligner"
  fi
fi

# 1. Validate Secret File existence
if [ -z "$SECRET_FILE" ]; then
  echo "ERROR: Secret file argument is required." >&2
  echo "Usage: $0 <secret-file> [kubeconfig-file] [namespace]" >&2
  exit 1
fi

if [ "${BASH_VERSINFO[0]:-0}" -lt 4 ]; then
  echo "ERROR: Bash 4 or higher is required." >&2
  exit 1
fi

trim_whitespace() {
  local var="$*"
  var="${var#"${var%%[![:space:]]*}"}"
  var="${var%"${var##*[![:space:]]}"}"
  printf '%s' "$var"
}

if [ ! -f "$SECRET_FILE" ]; then
  echo "ERROR: Secret file '$SECRET_FILE' does not exist or is not a regular file." >&2
  exit 1
fi

if [ ! -f "$KEYS_FILE" ]; then
  echo "ERROR: Runtime secret keys reference file '$KEYS_FILE' not found." >&2
  exit 1
fi

# 2. Validate all required keys are present in the secret file
REQUIRED_KEYS=()
while IFS= read -r key || [ -n "$key" ]; do
  key_trimmed=$(trim_whitespace "$key")
  [ -z "$key_trimmed" ] && continue
  [[ "$key_trimmed" =~ ^# ]] && continue
  REQUIRED_KEYS+=("$key_trimmed")
done < "$KEYS_FILE"

# Parse and normalize secret file entries
declare -A FOUND_KEYS
umask 077
tmp_env_dir=$(mktemp -d)
trap 'rm -rf "$tmp_env_dir"' EXIT
clean_env_file="$tmp_env_dir/secrets.env"
touch "$clean_env_file"

line_number=0
while IFS= read -r line || [ -n "$line" ]; do
  line_number=$((line_number + 1))
  trimmed=$(trim_whitespace "$line")
  [ -z "$trimmed" ] && continue
  [[ "$trimmed" =~ ^# ]] && continue
  trimmed="${trimmed#export }"
  trimmed=$(trim_whitespace "$trimmed")
  if [[ "$trimmed" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
    key_name="${BASH_REMATCH[1]}"
    val="${BASH_REMATCH[2]}"
    # Strip optional surrounding single/double quotes
    if [[ "$val" =~ ^\"(.*)\"$ ]] || [[ "$val" =~ ^\'(.*)\'$ ]]; then
      val="${BASH_REMATCH[1]}"
    fi
    FOUND_KEYS["$key_name"]=1
    echo "${key_name}=${val}" >> "$clean_env_file"
  else
    echo "ERROR: Malformed line $line_number in '$SECRET_FILE': '$line'" >&2
    exit 1
  fi
done < "$SECRET_FILE"

MISSING_KEYS=()
for req_key in "${REQUIRED_KEYS[@]}"; do
  if [ -z "${FOUND_KEYS[$req_key]:-}" ]; then
    MISSING_KEYS+=("$req_key")
  fi
done

if [ ${#MISSING_KEYS[@]} -ne 0 ]; then
  echo "ERROR: Secret file '$SECRET_FILE' is missing required keys from $(basename "$KEYS_FILE"):" >&2
  for mkey in "${MISSING_KEYS[@]}"; do
    echo "  - $mkey" >&2
  done
  exit 1
fi

echo "✓ Secret file validated against $(basename "$KEYS_FILE") (all ${#REQUIRED_KEYS[@]} keys present)."

# 3. Resolve Kubeconfig
KUBECTL_ARGS=()
if [ -n "$KUBECONFIG_FILE" ]; then
  if [ ! -f "$KUBECONFIG_FILE" ]; then
    echo "ERROR: Kubeconfig file '$KUBECONFIG_FILE' not found." >&2
    exit 1
  fi
  KUBECTL_ARGS+=(--kubeconfig "$KUBECONFIG_FILE")
elif [ -n "${KUBECONFIG:-}" ] && [ -f "$KUBECONFIG" ]; then
  KUBECTL_ARGS+=(--kubeconfig "$KUBECONFIG")
elif [ -f "$repo_root/.runtime/kubeconfig" ]; then
  KUBECTL_ARGS+=(--kubeconfig "$repo_root/.runtime/kubeconfig")
fi

# 4. Ensure Namespace exists & Apply Secret aligner-api-secrets
if ! kubectl ${KUBECTL_ARGS[@]+"${KUBECTL_ARGS[@]}"} get namespace "$NAMESPACE" >/dev/null 2>&1; then
  echo "Namespace '$NAMESPACE' does not exist; creating namespace..."
  kubectl ${KUBECTL_ARGS[@]+"${KUBECTL_ARGS[@]}"} create namespace "$NAMESPACE"
fi

echo "Applying secret 'aligner-api-secrets' in namespace '$NAMESPACE'..."
kubectl ${KUBECTL_ARGS[@]+"${KUBECTL_ARGS[@]}"} create secret generic aligner-api-secrets \
  --namespace="$NAMESPACE" \
  --from-env-file="$clean_env_file" \
  --dry-run=client -o yaml | kubectl ${KUBECTL_ARGS[@]+"${KUBECTL_ARGS[@]}"} apply -f -

echo "✓ Secret 'aligner-api-secrets' applied successfully in namespace '$NAMESPACE'."

# 5. Restart Deployment if present
deployments=$(kubectl ${KUBECTL_ARGS[@]+"${KUBECTL_ARGS[@]}"} get deployments -n "$NAMESPACE" -l "app.kubernetes.io/part-of=aligner" -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || true)

if [ -z "$deployments" ]; then
  for candidate in "aligner-api" "aligner-sandbox-api"; do
    if kubectl ${KUBECTL_ARGS[@]+"${KUBECTL_ARGS[@]}"} get deployment "$candidate" -n "$NAMESPACE" >/dev/null 2>&1; then
      deployments="$candidate"
      break
    fi
  done
fi

if [ -n "$deployments" ]; then
  for dep in $deployments; do
    echo "Triggering rollout restart for deployment '$dep' in namespace '$NAMESPACE'..."
    kubectl ${KUBECTL_ARGS[@]+"${KUBECTL_ARGS[@]}"} rollout restart deployment/"$dep" -n "$NAMESPACE"
    echo "✓ Rollout restart triggered for deployment '$dep'."
  done
else
  echo "Note: No active deployment found in namespace '$NAMESPACE' (skipping restart)."
fi
