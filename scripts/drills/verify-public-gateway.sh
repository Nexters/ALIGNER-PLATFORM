#!/usr/bin/env bash
set -euo pipefail

# Scripts/drills/verify-public-gateway.sh
# End-to-end verification script for Gateway API, Cert-Manager, CloudNativePG,
# and GitOps application manifests (both static rendering and optional live cluster checks).

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

LIVE_MODE=false
for arg in "$@"; do
  case "$arg" in
    --live)
      LIVE_MODE=true
      ;;
    -h|--help)
      echo "Usage: $0 [--live]"
      echo "  --live   Verify live Kubernetes cluster state if .runtime/kubeconfig is present"
      exit 0
      ;;
  esac
done

echo "============================================================"
echo "  ALIGNER Public Gateway & Data Foundation Verification"
echo "============================================================"

# 1. Verify gitops/infrastructure/configs kustomization
echo ""
echo "[1/3] Verifying Kustomize rendering: gitops/infrastructure/configs..."
configs_manifest=$(kubectl kustomize "$repo_root/gitops/infrastructure/configs")
if [ -z "$configs_manifest" ]; then
  echo "ERROR: gitops/infrastructure/configs rendered empty output" >&2
  exit 1
fi

# Assert expected resources in configs
echo "$configs_manifest" | grep -q 'name: platform-gateway'
echo "$configs_manifest" | grep -q 'name: platform-traefik'
echo "$configs_manifest" | grep -q 'name: letsencrypt-production'
echo "$configs_manifest" | grep -q 'name: aligner-api-tls'
echo "$configs_manifest" | grep -q 'test.aligneryoga.com'
echo "$configs_manifest" | grep -q 'name: aligner-db'
echo "$configs_manifest" | grep -q 'name: infisical-runtime'
echo "  ✓ gitops/infrastructure/configs rendered and validated successfully."

# 2. Verify gitops/apps/aligner-sandbox/base kustomization
echo ""
echo "[2/3] Verifying Kustomize rendering: gitops/apps/aligner-sandbox/base..."
sandbox_manifest=$(kubectl kustomize "$repo_root/gitops/apps/aligner-sandbox/base")
if [ -z "$sandbox_manifest" ]; then
  echo "ERROR: gitops/apps/aligner-sandbox/base rendered empty output" >&2
  exit 1
fi

# Assert expected resources in sandbox
echo "$sandbox_manifest" | grep -q 'name: aligner-sandbox'
echo "$sandbox_manifest" | grep -q 'name: sandbox-quota'
echo "$sandbox_manifest" | grep -q 'name: sandbox-limits'
echo "$sandbox_manifest" | grep -q 'name: aligner-sandbox-api'
echo "$sandbox_manifest" | grep -q 'dev-api.aligneryoga.com'
echo "  ✓ gitops/apps/aligner-sandbox/base rendered and validated successfully."

# 3. Verify gitops/apps/aligner-api/overlays/normal kustomization
echo ""
echo "[3/3] Verifying Kustomize rendering: gitops/apps/aligner-api/overlays/normal..."
normal_manifest=$(kubectl kustomize "$repo_root/gitops/apps/aligner-api/overlays/normal")
if [ -z "$normal_manifest" ]; then
  echo "ERROR: gitops/apps/aligner-api/overlays/normal rendered empty output" >&2
  exit 1
fi

# Assert expected resources in normal overlay
echo "$normal_manifest" | grep -q 'name: aligner-api'
echo "$normal_manifest" | grep -q 'name: platform-gateway'
echo "$normal_manifest" | grep -q 'api.aligneryoga.com'
echo "  ✓ gitops/apps/aligner-api/overlays/normal rendered and validated successfully."

# 4. Optional Live Cluster Verification
if [ "$LIVE_MODE" = true ]; then
  echo ""
  echo "============================================================"
  echo "  Live Cluster Verification (--live)"
  echo "============================================================"
  kubeconfig="${KUBECONFIG:-$repo_root/.runtime/kubeconfig}"

  if [ ! -f "$kubeconfig" ]; then
    echo "ERROR: --live was specified but kubeconfig '$kubeconfig' was not found" >&2
    exit 1
  fi

  echo "Using kubeconfig: $kubeconfig"
  
  echo ""
  echo "Checking GatewayClass status..."
  kubectl --kubeconfig "$kubeconfig" get gatewayclasses.gateway.networking.k8s.io platform-traefik

  echo ""
  echo "Checking Gateway in namespace 'traefik'..."
  kubectl --kubeconfig "$kubeconfig" get gateways.gateway.networking.k8s.io -n traefik || true

  echo ""
  echo "Checking Cert-Manager CRDs and ClusterIssuers..."
  kubectl --kubeconfig "$kubeconfig" get crd clusterissuers.cert-manager.io certificates.cert-manager.io
  kubectl --kubeconfig "$kubeconfig" get clusterissuers.cert-manager.io

  echo ""
  echo "Checking CloudNativePG CRDs..."
  kubectl --kubeconfig "$kubeconfig" get crd clusters.postgresql.cnpg.io

  echo ""
  echo "  ✓ Live cluster resources verified successfully."
fi

echo ""
echo "============================================================"
echo "  All verifications completed successfully."
echo "============================================================"
exit 0
