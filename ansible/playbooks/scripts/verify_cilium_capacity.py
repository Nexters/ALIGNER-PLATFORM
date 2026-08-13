#!/usr/bin/env python3
import json
import sys
from decimal import Decimal, DecimalException, InvalidOperation, ROUND_CEILING
import re


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
        raise CapacityInputError("invalid_input", path + ".resources.requests", "must be an object")
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


def main():
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise CapacityInputError("invalid_input", "payload", "must be an object")
        nodes = payload.get("nodes", {}).get("items")
        pods = payload.get("pods", {}).get("items")
        ratios = capacity_after_one_node_loss(nodes, pods)
    except (json.JSONDecodeError, CapacityInputError, AttributeError) as error:
        detail = (
            error.error
            if isinstance(error, CapacityInputError)
            else {"code": "invalid_input", "path": "payload", "detail": str(error)}
        )
        print(json.dumps({"valid": False, "error": detail}, sort_keys=True), file=sys.stderr)
        return 1
    if any(value > Decimal("0.85") for value in ratios.values()):
        report = {
            "valid": False,
            "error": {
                "code": "capacity_exceeded",
                "detail": (
                    "aggregate-only N-1 capacity exceeds 85%; "
                    "this is not a scheduler placement guarantee"
                ),
            },
            "ratios": {key: decimal_text(value) for key, value in ratios.items()},
        }
        print(json.dumps(report, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps({
        "cpu_ratio": decimal_text(ratios["cpu"]),
        "memory_ratio": decimal_text(ratios["memory"]),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
