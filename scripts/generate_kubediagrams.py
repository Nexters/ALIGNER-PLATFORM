#!/usr/bin/env python3
"""
Generate Clean, Compact World-Class Kubernetes Architecture Diagrams using KubeDiagrams.
Filters noise, excludes internal controller boilerplate, and focuses on core architecture tiers.
"""

import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DOCS_ASSETS = ROOT_DIR / "docs" / "assets"
DOCS_ASSETS.mkdir(parents=True, exist_ok=True)

KUBECONFIG = ROOT_DIR / ".runtime" / "kubeconfig"
KUBE_DIAGRAMS_BIN = "/Users/donghoon/.local/pipx/venvs/ansible/bin/kube-diagrams"
CONFIG_FILE = ROOT_DIR / ".kubediagrams.yaml"

def run_cmd(cmd: str, check: bool = True) -> str:
    res = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    if check and res.returncode != 0:
        print(f"Command failed: {cmd}\nStderr: {res.stderr}", file=sys.stderr)
        sys.exit(res.returncode)
    return res.stdout

def main():
    print("🚀 Extracting core architectural resources from ALIGNER K3s Cluster...")
    manifest_file = Path("/tmp/aligner_core_manifests.yaml")
    
    # 1. Target key architectural resources (filtering out internal controller sub-pods/noise)
    dump_queries = [
        # Nodes
        f"kubectl --kubeconfig {KUBECONFIG} get nodes -o yaml",
        # Ingress Plane
        f"kubectl --kubeconfig {KUBECONFIG} get gateway,httproute -n traefik -o yaml 2>/dev/null || true",
        f"kubectl --kubeconfig {KUBECONFIG} get ds/traefik svc/traefik -n traefik -o yaml 2>/dev/null || true",
        # Core Applications
        f"kubectl --kubeconfig {KUBECONFIG} get deploy/aligner-api svc/aligner-api httproute/aligner-api secret/aligner-api-secrets -n aligner -o yaml 2>/dev/null || true",
        f"kubectl --kubeconfig {KUBECONFIG} get deploy/aligner-sandbox-api svc/aligner-sandbox-api httproute/aligner-sandbox-api -n aligner-sandbox -o yaml 2>/dev/null || true",
        # Data & Storage
        f"kubectl --kubeconfig {KUBECONFIG} get cluster/aligner-db svc/aligner-db-rw svc/aligner-db-ro -n aligner-data -o yaml 2>/dev/null || true",
        f"kubectl --kubeconfig {KUBECONFIG} get deploy/aligner-redis svc/aligner-redis -n aligner-data -o yaml 2>/dev/null || true",
        # TLS & Certificates
        f"kubectl --kubeconfig {KUBECONFIG} get clusterissuer/letsencrypt-production certificate/aligner-api -n cert-manager -o yaml 2>/dev/null || true",
        # GitOps Plane
        f"kubectl --kubeconfig {KUBECONFIG} get deploy/argocd-server statefulset/argocd-application-controller -n argocd -o yaml 2>/dev/null || true",
        # Tailscale Ingress
        f"kubectl --kubeconfig {KUBECONFIG} get deploy/operator statefulset/aligner-argocd-ui -n tailscale -o yaml 2>/dev/null || true",
    ]
    
    full_yaml = ""
    for cmd in dump_queries:
        out = run_cmd(cmd, check=False)
        if out.strip():
            full_yaml += out + "\n---\n"
            
    manifest_file.write_text(full_yaml)
    print(f"✅ Saved core architectural manifests to {manifest_file} ({len(full_yaml)} bytes)")
    
    config_opt = f"-c {CONFIG_FILE}" if CONFIG_FILE.exists() else ""
    
    # 2. Generate Clean PNG
    print("🎨 Generating High-Resolution Diagram via KubeDiagrams...")
    png_out = DOCS_ASSETS / "architecture_kubediagrams.png"
    run_cmd(f"{KUBE_DIAGRAMS_BIN} {config_opt} {manifest_file} -o {png_out} -f png")
    print(f"✨ Generated: {png_out}")
    
    # 3. Generate SVG
    print("🎨 Generating Scalable Vector Graphic (SVG) via KubeDiagrams...")
    svg_out = DOCS_ASSETS / "architecture_kubediagrams.svg"
    run_cmd(f"{KUBE_DIAGRAMS_BIN} {config_opt} {manifest_file} -o {svg_out} -f svg --embed-all-icons")
    print(f"✨ Generated: {svg_out}")
    
    # 4. Generate Editable draw.io XML
    print("🎨 Generating Editable draw.io XML via KubeDiagrams...")
    drawio_out = DOCS_ASSETS / "architecture.drawio"
    run_cmd(f"{KUBE_DIAGRAMS_BIN} {config_opt} {manifest_file} -o {drawio_out} -f drawio")
    print(f"✨ Generated: {drawio_out}")

if __name__ == "__main__":
    main()
