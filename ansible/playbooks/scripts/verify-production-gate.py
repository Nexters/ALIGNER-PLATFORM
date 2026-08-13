#!/usr/bin/env python3
"""Fixed, read-only Kubernetes production-readiness assertions."""

import argparse
import datetime
import json
import os
import subprocess
import sys


K3S = "/usr/local/bin/k3s"
EXPECTED_NODES = ["k3s-01", "k3s-02", "k3s-03"]
REQUIRED_NAMESPACES = ["kube-system", "argocd", "cert-manager", "traefik", "aligner", "aligner-data"]
SAFE_COMMANDS = {
    "nodes": "sudo /usr/local/bin/k3s kubectl get nodes -o wide",
    "etcd": "sudo /usr/local/bin/k3s etcdctl endpoint health --cluster",
    "cilium": "make verify-cilium",
    "workloads": "sudo /usr/local/bin/k3s kubectl get pods -n <namespace>",
    "gateway": "kubectl get gateway,httproute,certificate -A",
    "external": "Follow docs/runbooks/https-entry.md; record External LB health evidence outside Git.",
    "capacity": "sudo /usr/local/bin/k3s kubectl describe nodes",
}


def run(*argv):
    result = subprocess.run(argv, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip()[:500])
    return json.loads(result.stdout)


def truthy_condition(conditions, kind):
    return any(item.get("type") == kind and item.get("status") == "True" for item in conditions or [])


def quantity(value):
    value = str(value or "0")
    multipliers = {"n": 1e-9, "u": 1e-6, "m": 1e-3, "Ki": 1024, "Mi": 1024**2, "Gi": 1024**3}
    for suffix, multiplier in multipliers.items():
        if value.endswith(suffix):
            return float(value[: -len(suffix)]) * multiplier
    return float(value)


def capacity_after_one_node_loss(nodes, pods):
    totals = {"cpu": 0.0, "memory": 0.0}
    for pod in pods:
        for container in pod.get("spec", {}).get("containers", []):
            for resource in totals:
                totals[resource] += quantity(container.get("resources", {}).get("requests", {}).get(resource, "0"))
    allocatable = {
        resource: sorted(quantity(node.get("status", {}).get("allocatable", {}).get(resource, "0")) for node in nodes)
        for resource in totals
    }
    # Survive loss of the largest node; the two smallest allocatable nodes remain.
    return {resource: totals[resource] / sum(allocatable[resource][:-1]) for resource in totals}


def main():
    parser = argparse.ArgumentParser()
    parser.parse_args()
    cilium_evidence_present = os.environ.get("PRODUCTION_GATE_CILIUM_EVIDENCE_PRESENT", "false")
    encryption_hashes = json.loads(os.environ.get("PRODUCTION_GATE_ENCRYPTION_HASHES", "[]"))
    external_health_evidence_ref = os.environ.get("PRODUCTION_GATE_EXTERNAL_HEALTH_EVIDENCE_REF", "")
    checks = []

    def check(name, target, next_command, assertion):
        try:
            assertion()
            checks.append({"name": name, "target": target, "status": "PASS"})
        except Exception as error:  # emit every failed target; do not stop at the first one
            checks.append({"name": name, "target": target, "status": "FAIL", "next_safe_command": next_command, "reason": str(error)})

    cluster = {}
    check("nodes", "k3s-01,k3s-02,k3s-03", SAFE_COMMANDS["nodes"], lambda: cluster.setdefault("nodes", run(K3S, "kubectl", "get", "nodes", "-o", "json")))

    def assert_nodes():
        nodes = cluster["nodes"]["items"]
        names = sorted(node["metadata"]["name"] for node in nodes)
        if names != EXPECTED_NODES or not all(truthy_condition(node["status"].get("conditions"), "Ready") for node in nodes):
            raise AssertionError("expected exactly the three Ready server names")
    check("nodes-ready", "Kubernetes nodes", SAFE_COMMANDS["nodes"], assert_nodes)

    def assert_encryption_hashes():
        if len(encryption_hashes) != 3 or len(set(encryption_hashes)) != 1:
            raise AssertionError("K3s encryption configuration hash does not match on all three servers")
    check("encryption-config", "K3s secret encryption configuration", "sudo sha256sum /var/lib/rancher/k3s/server/cred/encryption-config.json", assert_encryption_hashes)

    def assert_etcd():
        members = run(K3S, "etcdctl", "member", "list", "--write-out=json")
        health = run(K3S, "etcdctl", "endpoint", "health", "--cluster", "--write-out=json")
        if len(members.get("members", [])) != 3 or len(health) != 3:
            raise AssertionError("expected three etcd members and three healthy endpoints")
    check("etcd", "embedded etcd", SAFE_COMMANDS["etcd"], assert_etcd)

    def assert_cilium():
        daemonset = run(K3S, "kubectl", "-n", "kube-system", "get", "daemonset", "cilium", "-o", "json")
        operator = run(K3S, "kubectl", "-n", "kube-system", "get", "deployment", "cilium-operator", "-o", "json")
        status = daemonset.get("status", {})
        if status.get("desiredNumberScheduled") != 3 or status.get("numberReady") != 3:
            raise AssertionError("Cilium DaemonSet is not Ready on all three servers")
        if operator.get("status", {}).get("availableReplicas", 0) < 1:
            raise AssertionError("Cilium operator has no available replica")
        if cilium_evidence_present != "true":
            raise AssertionError("read-only Cilium connectivity evidence is absent")
    check("cilium", "Cilium DaemonSet, operator, connectivity evidence", SAFE_COMMANDS["cilium"], assert_cilium)

    all_pods = []
    def assert_workloads():
        for namespace in REQUIRED_NAMESPACES:
            pods = run(K3S, "kubectl", "-n", namespace, "get", "pods", "-o", "json")["items"]
            all_pods.extend(pods)
            healthy = [pod for pod in pods if pod.get("status", {}).get("phase") == "Running" and truthy_condition(pod.get("status", {}).get("conditions"), "Ready")]
            bad = [pod["metadata"]["name"] for pod in pods if pod.get("status", {}).get("phase") not in {"Running", "Succeeded"} or (pod.get("status", {}).get("phase") == "Running" and not truthy_condition(pod.get("status", {}).get("conditions"), "Ready"))]
            if not healthy:
                raise AssertionError(f"{namespace}: no Running and Ready workload pod")
            if bad:
                raise AssertionError(f"{namespace}: unhealthy or Pending pods: {','.join(bad)}")
    check("required-workloads", ",".join(REQUIRED_NAMESPACES), SAFE_COMMANDS["workloads"], assert_workloads)

    def assert_edge():
        gateway = run(K3S, "kubectl", "-n", "traefik", "get", "gateway", "platform", "-o", "json")
        route = run(K3S, "kubectl", "-n", "aligner", "get", "httproute", "aligner-api", "-o", "json")
        certificate = run(K3S, "kubectl", "-n", "traefik", "get", "certificate", "aligner-api", "-o", "json")
        if not truthy_condition(gateway.get("status", {}).get("conditions"), "Accepted") or not truthy_condition(gateway.get("status", {}).get("conditions"), "Programmed"):
            raise AssertionError("Gateway/platform is not Accepted and Programmed")
        if not truthy_condition(route.get("status", {}).get("parents", [{}])[0].get("conditions"), "Accepted"):
            raise AssertionError("HTTPRoute/aligner-api is not Accepted")
        if not truthy_condition(certificate.get("status", {}).get("conditions"), "Ready"):
            raise AssertionError("Certificate/aligner-api is not Ready")
        if not external_health_evidence_ref.strip():
            raise AssertionError("External LB health evidence reference is required")
    check("gateway-tls-external-health", "Gateway, HTTPRoute, Certificate, External LB", SAFE_COMMANDS["external"], assert_edge)

    def assert_capacity():
        ratios = capacity_after_one_node_loss(cluster["nodes"]["items"], all_pods)
        if any(value > 0.85 for value in ratios.values()):
            raise AssertionError("one-node-loss requested capacity exceeds 85%: " + json.dumps(ratios, sort_keys=True))
    check("one-node-loss-capacity", "required namespace requests", SAFE_COMMANDS["capacity"], assert_capacity)

    version_lines = subprocess.run([K3S, "--version"], capture_output=True, text=True, check=False).stdout.splitlines()
    report = {"checked_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "k3s_version": version_lines[0] if version_lines else "unavailable", "checks": checks}
    print(json.dumps(report, sort_keys=True))
    return 0 if all(check["status"] == "PASS" for check in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
