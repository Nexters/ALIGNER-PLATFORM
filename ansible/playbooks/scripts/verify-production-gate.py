#!/usr/bin/env python3
"""Fixed, read-only Kubernetes production-readiness assertions."""

import argparse
import datetime
from decimal import Decimal, DecimalException, InvalidOperation, ROUND_CEILING
import json
import os
import re
import subprocess
import sys


K3S = "/usr/local/bin/k3s"
EXPECTED_NODES = ["k3s-01", "k3s-02", "k3s-03"]
REQUIRED_NAMESPACES = [
    "kube-system", "argocd", "cert-manager", "traefik", "aligner", "aligner-data",
]
SAFE_COMMANDS = {
    "nodes": "sudo /usr/local/bin/k3s kubectl get nodes -o wide",
    "etcd": "sudo /usr/local/bin/k3s etcdctl endpoint health --cluster",
    "cilium": "make verify-cilium",
    "workloads": "sudo /usr/local/bin/k3s kubectl get pods -n <namespace>",
    "gateway": "kubectl get gateway,httproute,certificate -A",
    "external": (
        "Follow docs/runbooks/https-entry.md; record External LB health evidence outside Git."
    ),
    "capacity": "sudo /usr/local/bin/k3s kubectl describe nodes",
}

RESOURCES = ("cpu", "memory")
QUANTITY = re.compile(
    r"(?P<number>[+-]?(?:\d+(?:\.\d*)?|\.\d+))"
    r"(?P<suffix>[eE][+-]?\d+|Ki|Mi|Gi|Ti|Pi|Ei|n|u|m|k|K|M|G|T|P|E)?$"
)
MULTIPLIERS = {
    "": Decimal(1), "n": Decimal("1e-9"), "u": Decimal("1e-6"), "m": Decimal("1e-3"),
    "k": Decimal("1e3"), "K": Decimal("1e3"), "M": Decimal("1e6"),
    "G": Decimal("1e9"), "T": Decimal("1e12"), "P": Decimal("1e15"),
    "E": Decimal("1e18"), "Ki": Decimal(2) ** 10, "Mi": Decimal(2) ** 20,
    "Gi": Decimal(2) ** 30, "Ti": Decimal(2) ** 40, "Pi": Decimal(2) ** 50,
    "Ei": Decimal(2) ** 60,
}
INT64_MAX = Decimal(2) ** 63 - 1


class CapacityInputError(ValueError):
    def __init__(self, code, path, detail):
        self.error = {"code": code, "path": path, "detail": detail}
        super().__init__("capacity input error: " + json.dumps(self.error, sort_keys=True))


def quantity(value, path="quantity", resource=None):
    if not isinstance(value, (str, int, Decimal)) or isinstance(value, bool):
        raise CapacityInputError("invalid_quantity", path, "must be a Kubernetes Quantity")
    match = QUANTITY.fullmatch(str(value))
    if not match:
        raise CapacityInputError("invalid_quantity", path, "must be a Kubernetes Quantity")
    try:
        suffix = match.group("suffix") or ""
        multiplier = (
            Decimal(10) ** int(suffix[1:])
            if suffix[:1].lower() == "e"
            else MULTIPLIERS[suffix]
        )
        result = Decimal(match.group("number")) * multiplier
    except (DecimalException, InvalidOperation, KeyError):
        raise CapacityInputError(
            "invalid_quantity", path, "must be a Kubernetes Quantity"
        ) from None
    if not result.is_finite() or result < 0:
        raise CapacityInputError(
            "invalid_quantity", path, "must be a finite non-negative Kubernetes Quantity"
        )
    if resource == "cpu":
        millicores = (result * 1000).to_integral_value(rounding=ROUND_CEILING)
        if millicores > INT64_MAX:
            raise CapacityInputError(
                "invalid_quantity", path, "canonical value exceeds signed int64"
            )
        return millicores / 1000
    if resource == "memory":
        bytes_value = result.to_integral_value(rounding=ROUND_CEILING)
        if bytes_value > INT64_MAX:
            raise CapacityInputError(
                "invalid_quantity", path, "canonical value exceeds signed int64"
            )
        return bytes_value
    return result


def _object(value, path):
    if not isinstance(value, dict):
        raise CapacityInputError("invalid_input", path, "must be an object")
    return value


def _request(container, path):
    requests = _object(container, path).get("resources", {}).get("requests", {})
    if not isinstance(requests, dict):
        raise CapacityInputError(
            "invalid_input", path + ".resources.requests", "must be an object"
        )
    return {
        item: quantity(requests.get(item, "0"), path + ".resources.requests." + item, item)
        for item in RESOURCES
    }


def _resource_request(values, path):
    if not isinstance(values, dict):
        raise CapacityInputError("invalid_input", path, "must be an object")
    return {
        item: quantity(values.get(item, "0"), path + "." + item, item)
        for item in RESOURCES
    }


def _container_statuses_by_name(statuses, containers, path):
    if not isinstance(statuses, list):
        raise CapacityInputError("invalid_input", path, "must be an array")
    names = {}
    for position, container in enumerate(containers):
        name = _object(container, f"{path}.spec[{position}]").get("name")
        if not isinstance(name, str) or not name:
            raise CapacityInputError(
                "invalid_input", f"{path}.spec[{position}].name", "must be a non-empty string"
            )
        names[name] = position
    result = {}
    for position, container_status in enumerate(statuses):
        container_status = _object(container_status, f"{path}[{position}]")
        name = container_status.get("name")
        if not isinstance(name, str) or name not in names or name in result:
            raise CapacityInputError(
                "invalid_input", f"{path}[{position}].name", "must match one spec container once"
            )
        result[name] = container_status
    return result


def _container_request(container, path, statuses, source, resize_infeasible):
    spec_request = _request(container, path)
    if source == "spec":
        return spec_request
    status = statuses.get(_object(container, path).get("name"))
    values, value_path = None, path
    if status is not None:
        status_path = path.replace(".spec.", ".status.")
        if source == "actuated":
            resources = status.get("resources")
            if resources is not None:
                resources = _object(resources, status_path + ".resources")
                if "requests" in resources:
                    values = resources["requests"]
                    value_path = status_path + ".resources.requests"
        if values is None and status.get("allocatedResources") is not None:
            values = status["allocatedResources"]
            value_path = status_path + ".allocatedResources"
    if values is not None:
        return _resource_request(values, value_path)
    if resize_infeasible:
        return {item: Decimal(0) for item in RESOURCES}
    return spec_request


def _aggregate_container_requests(
    containers, init, app_statuses, init_statuses, source, resize_infeasible, path
):
    app = {item: Decimal(0) for item in RESOURCES}
    for position, container in enumerate(containers):
        request = _container_request(
            container, f"{path}.containers[{position}]", app_statuses, source, resize_infeasible
        )
        for item in RESOURCES:
            app[item] += request[item]
    sidecar = {item: Decimal(0) for item in RESOURCES}
    init_peak = {item: Decimal(0) for item in RESOURCES}
    for position, container in enumerate(init):
        request = _container_request(
            container, f"{path}.initContainers[{position}]", init_statuses,
            source, resize_infeasible,
        )
        is_sidecar = _object(container, f"{path}.initContainers[{position}]").get(
            "restartPolicy"
        ) == "Always"
        for item in RESOURCES:
            if is_sidecar:
                sidecar[item] += request[item]
            else:
                init_peak[item] = max(init_peak[item], sidecar[item] + request[item])
    return {item: max(app[item] + sidecar[item], init_peak[item]) for item in RESOURCES}


def effective_pod_requests(pod, index):
    pod = _object(pod, f"pods[{index}]")
    status = _object(pod.get("status", {}), f"pods[{index}].status")
    if status.get("phase") in {"Succeeded", "Failed"}:
        return None
    conditions = status.get("conditions", [])
    if not isinstance(conditions, list):
        raise CapacityInputError(
            "invalid_input", f"pods[{index}].status.conditions", "must be an array"
        )
    spec = _object(pod.get("spec", {}), f"pods[{index}].spec")
    containers, init = spec.get("containers", []), spec.get("initContainers", [])
    if not isinstance(containers, list) or not isinstance(init, list):
        raise CapacityInputError(
            "invalid_input", f"pods[{index}].spec", "containers and initContainers must be arrays"
        )
    app_statuses = _container_statuses_by_name(
        status.get("containerStatuses", []), containers, f"pods[{index}].status.containerStatuses"
    ) if "containerStatuses" in status else {}
    init_statuses = _container_statuses_by_name(
        status.get("initContainerStatuses", []), init, f"pods[{index}].status.initContainerStatuses"
    ) if "initContainerStatuses" in status else {}
    resize_infeasible = any(
        isinstance(condition, dict)
        and condition.get("type") == "PodResizePending"
        and condition.get("status") == "True"
        and condition.get("reason") == "Infeasible"
        for condition in conditions
    )
    aggregates = [
        _aggregate_container_requests(
            containers, init, app_statuses, init_statuses, source, resize_infeasible,
            f"pods[{index}].spec",
        )
        for source in (("actuated", "allocated") if resize_infeasible
                       else ("spec", "actuated", "allocated"))
    ]
    if status.get("allocatedResources") is not None and (
        isinstance(status.get("resources"), dict)
        and status["resources"].get("requests") is not None
    ):
        aggregates = [] if resize_infeasible else [
            _aggregate_container_requests(
                containers, init, app_statuses, init_statuses, "spec", False,
                f"pods[{index}].spec",
            )
        ]
        aggregates.extend([
            _resource_request(status["resources"]["requests"], f"pods[{index}].status.resources.requests"),
            _resource_request(status["allocatedResources"], f"pods[{index}].status.allocatedResources"),
        ])
    effective = {
        item: max((request[item] for request in aggregates), default=Decimal(0))
        for item in RESOURCES
    }
    pod_resources = spec.get("resources", {})
    if not isinstance(pod_resources, dict):
        raise CapacityInputError("invalid_input", f"pods[{index}].spec.resources", "must be an object")
    pod_requests = pod_resources.get("requests", {})
    if not isinstance(pod_requests, dict):
        raise CapacityInputError(
            "invalid_input", f"pods[{index}].spec.resources.requests", "must be an object"
        )
    if pod_requests:
        pod_sources = [
            (pod_requests, f"pods[{index}].spec.resources.requests")
        ]
        if status.get("resources") is not None:
            resources = _object(status["resources"], f"pods[{index}].status.resources")
            status_requests = resources.get("requests", {})
            pod_sources = [] if resize_infeasible else pod_sources
            pod_sources.extend([
                (status_requests, f"pods[{index}].status.resources.requests"),
                (status.get("allocatedResources", {}), f"pods[{index}].status.allocatedResources"),
            ])
        parsed_sources = [(_resource_request(values, path), values) for values, path in pod_sources]
        for item in RESOURCES:
            if any(item in values for _, values in parsed_sources):
                effective[item] = max(request[item] for request, _ in parsed_sources)
    overhead = spec.get("overhead", {})
    if not isinstance(overhead, dict):
        raise CapacityInputError(
            "invalid_input", f"pods[{index}].spec.overhead", "must be an object"
        )
    return {
        item: effective[item]
        + quantity(overhead.get(item, "0"), f"pods[{index}].spec.overhead.{item}", item)
        for item in RESOURCES
    }


def capacity_after_one_node_loss(nodes, pods):
    if not isinstance(nodes, list) or len(nodes) != 3:
        raise CapacityInputError(
            "invalid_nodes", "nodes", "requires exactly three Ready schedulable nodes"
        )
    allocatable = []
    for index, node in enumerate(nodes):
        node = _object(node, f"nodes[{index}]")
        status = _object(node.get("status", {}), f"nodes[{index}].status")
        conditions = status.get("conditions", [])
        spec = _object(node.get("spec", {}), f"nodes[{index}].spec")
        if not isinstance(conditions, list):
            raise CapacityInputError(
                "invalid_input", f"nodes[{index}].status.conditions", "must be an array"
            )
        ready = any(
            item.get("type") == "Ready" and item.get("status") == "True"
            for item in conditions
            if isinstance(item, dict)
        )
        if not ready or spec.get("unschedulable", False):
            raise CapacityInputError(
                "invalid_nodes", f"nodes[{index}]", "requires exactly three Ready schedulable nodes"
            )
        taints = spec.get("taints", [])
        if not isinstance(taints, list):
            raise CapacityInputError(
                "invalid_input", f"nodes[{index}].spec.taints", "must be an array"
            )
        if any(
            isinstance(taint, dict) and taint.get("effect") in {"NoSchedule", "NoExecute"}
            for taint in taints
        ):
            raise CapacityInputError(
                "invalid_nodes",
                f"nodes[{index}].spec.taints",
                "NoSchedule and NoExecute taints are unsupported",
            )
        values = _object(status.get("allocatable", {}), f"nodes[{index}].status.allocatable")
        allocatable.append({
            item: quantity(values.get(item, "0"), f"nodes[{index}].status.allocatable.{item}", item)
            for item in RESOURCES
        })
    if not isinstance(pods, list):
        raise CapacityInputError("invalid_input", "pods", "must be an array")
    requests = [
        request for index, pod in enumerate(pods)
        if (request := effective_pod_requests(pod, index)) is not None
    ]
    total = {item: sum((request[item] for request in requests), Decimal(0)) for item in RESOURCES}
    scenarios = []
    for failed in range(3):
        remaining = {
            item: sum(
                (node[item] for position, node in enumerate(allocatable) if position != failed),
                Decimal(0),
            )
            for item in RESOURCES
        }
        if any(value == 0 for value in remaining.values()):
            raise CapacityInputError(
                "invalid_nodes",
                f"nodes[{failed}]",
                "surviving allocatable CPU and memory must be positive",
            )
        for request in requests:
            fits = any(
                all(request[item] <= node[item] for item in RESOURCES)
                for position, node in enumerate(allocatable)
                if position != failed
            )
            if not fits:
                raise CapacityInputError(
                    "unplaceable_pod",
                    "pods",
                    f"effective pod request fits no surviving node after loss of nodes[{failed}]",
                )
        scenarios.append({item: total[item] / remaining[item] for item in RESOURCES})
    return {item: max(scenario[item] for scenario in scenarios) for item in RESOURCES}


def decimal_text(value):
    return format(value, "f")


def run(*argv):
    result = subprocess.run(argv, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip()[:500])
    return json.loads(result.stdout)


def truthy_condition(conditions, kind):
    return any(
        item.get("type") == kind and item.get("status") == "True"
        for item in conditions or []
    )


def main():
    parser = argparse.ArgumentParser()
    parser.parse_args()
    cilium_evidence_present = os.environ.get("PRODUCTION_GATE_CILIUM_EVIDENCE_PRESENT", "false")
    encryption_hashes = os.environ.get("PRODUCTION_GATE_ENCRYPTION_HASHES", "[]")
    external_health_evidence_ref = os.environ.get(
        "PRODUCTION_GATE_EXTERNAL_HEALTH_EVIDENCE_REF", ""
    )
    checks = []

    def check(name, target, next_command, assertion):
        try:
            assertion()
            checks.append({"name": name, "target": target, "status": "PASS"})
        except Exception as error:  # emit every failed target; do not stop at the first one
            checks.append({
                "name": name,
                "target": target,
                "status": "FAIL",
                "next_safe_command": next_command,
                "reason": str(error),
            })

    cluster = {}
    check(
        "nodes",
        "k3s-01,k3s-02,k3s-03",
        SAFE_COMMANDS["nodes"],
        lambda: cluster.setdefault("nodes", run(K3S, "kubectl", "get", "nodes", "-o", "json")),
    )

    def assert_nodes():
        nodes = cluster["nodes"]["items"]
        names = sorted(node["metadata"]["name"] for node in nodes)
        if names != EXPECTED_NODES or not all(
            truthy_condition(node["status"].get("conditions"), "Ready")
            and not node.get("spec", {}).get("unschedulable", False)
            for node in nodes
        ):
            raise AssertionError("expected exactly the three Ready schedulable server names")
    check("nodes-ready", "Kubernetes nodes", SAFE_COMMANDS["nodes"], assert_nodes)

    def assert_encryption_hashes():
        try:
            hashes = json.loads(encryption_hashes)
        except json.JSONDecodeError as error:
            raise AssertionError(
                "PRODUCTION_GATE_ENCRYPTION_HASHES must be JSON: " + str(error)
            ) from None
        if not isinstance(hashes, list) or len(hashes) != 3 or len(set(hashes)) != 1:
            raise AssertionError(
                "K3s encryption configuration hash does not match on all three servers"
            )
    check(
        "encryption-config",
        "K3s secret encryption configuration",
        "sudo sha256sum /var/lib/rancher/k3s/server/cred/encryption-config.json",
        assert_encryption_hashes,
    )

    def assert_etcd():
        members = run(K3S, "etcdctl", "member", "list", "--write-out=json")
        health = run(K3S, "etcdctl", "endpoint", "health", "--cluster", "--write-out=json")
        if len(members.get("members", [])) != 3 or len(health) != 3:
            raise AssertionError("expected three etcd members and three healthy endpoints")
    check("etcd", "embedded etcd", SAFE_COMMANDS["etcd"], assert_etcd)

    def assert_cilium():
        daemonset = run(
            K3S, "kubectl", "-n", "kube-system", "get", "daemonset", "cilium", "-o", "json"
        )
        operator = run(
            K3S, "kubectl", "-n", "kube-system", "get", "deployment",
            "cilium-operator", "-o", "json",
        )
        status = daemonset.get("status", {})
        if status.get("desiredNumberScheduled") != 3 or status.get("numberReady") != 3:
            raise AssertionError("Cilium DaemonSet is not Ready on all three servers")
        if operator.get("status", {}).get("availableReplicas", 0) < 1:
            raise AssertionError("Cilium operator has no available replica")
        if cilium_evidence_present != "true":
            raise AssertionError("read-only Cilium connectivity evidence is absent")
    check(
        "cilium",
        "Cilium DaemonSet, operator, connectivity evidence",
        SAFE_COMMANDS["cilium"],
        assert_cilium,
    )

    def assert_workloads():
        for namespace in REQUIRED_NAMESPACES:
            pods = run(K3S, "kubectl", "-n", namespace, "get", "pods", "-o", "json")["items"]
            healthy = [
                pod for pod in pods
                if pod.get("status", {}).get("phase") == "Running"
                and truthy_condition(pod.get("status", {}).get("conditions"), "Ready")
            ]
            bad = [
                pod["metadata"]["name"] for pod in pods
                if pod.get("status", {}).get("phase") not in {"Running", "Succeeded"}
                or (
                    pod.get("status", {}).get("phase") == "Running"
                    and not truthy_condition(pod.get("status", {}).get("conditions"), "Ready")
                )
            ]
            if not healthy:
                raise AssertionError(f"{namespace}: no Running and Ready workload pod")
            if bad:
                raise AssertionError(f"{namespace}: unhealthy or Pending pods: {','.join(bad)}")
    check(
        "required-workloads",
        ",".join(REQUIRED_NAMESPACES),
        SAFE_COMMANDS["workloads"],
        assert_workloads,
    )

    def assert_edge():
        gateway = run(K3S, "kubectl", "-n", "traefik", "get", "gateway", "platform", "-o", "json")
        route = run(
            K3S, "kubectl", "-n", "aligner", "get", "httproute", "aligner-api", "-o", "json"
        )
        certificate = run(
            K3S, "kubectl", "-n", "traefik", "get", "certificate", "aligner-api", "-o", "json"
        )
        gateway_conditions = gateway.get("status", {}).get("conditions")
        if not (
            truthy_condition(gateway_conditions, "Accepted")
            and truthy_condition(gateway_conditions, "Programmed")
        ):
            raise AssertionError("Gateway/platform is not Accepted and Programmed")
        route_conditions = route.get("status", {}).get("parents", [{}])[0].get("conditions")
        if not truthy_condition(route_conditions, "Accepted"):
            raise AssertionError("HTTPRoute/aligner-api is not Accepted")
        if not truthy_condition(certificate.get("status", {}).get("conditions"), "Ready"):
            raise AssertionError("Certificate/aligner-api is not Ready")
        if not external_health_evidence_ref.strip():
            raise AssertionError("External LB health evidence reference is required")
    check(
        "gateway-tls-external-health",
        "Gateway, HTTPRoute, Certificate, External LB",
        SAFE_COMMANDS["external"],
        assert_edge,
    )

    def assert_capacity():
        all_pods = run(K3S, "kubectl", "get", "pods", "--all-namespaces", "-o", "json")["items"]
        ratios = capacity_after_one_node_loss(cluster["nodes"]["items"], all_pods)
        if any(value > Decimal("0.85") for value in ratios.values()):
            values = {key: decimal_text(value) for key, value in ratios.items()}
            raise AssertionError(
                "one-node-loss aggregate requested capacity exceeds 85% "
                "(not a scheduler placement guarantee): "
                + json.dumps(values, sort_keys=True)
            )
    check(
        "one-node-loss-capacity",
        "all namespace requests",
        SAFE_COMMANDS["capacity"],
        assert_capacity,
    )

    version_lines = subprocess.run(
        [K3S, "--version"], capture_output=True, text=True, check=False
    ).stdout.splitlines()
    report = {
        "checked_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "k3s_version": version_lines[0] if version_lines else "unavailable",
        "checks": checks,
    }
    print(json.dumps(report, sort_keys=True))
    return 0 if all(check["status"] == "PASS" for check in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
