#!/usr/bin/env python3
import json
import sys


def quantity(value, cpu=False):
    units = {"Ki": 2**10, "Mi": 2**20, "Gi": 2**30, "Ti": 2**40, "n": 1e-9, "u": 1e-6, "m": 0.001}
    for suffix, factor in units.items():
        if value.endswith(suffix):
            return float(value[: -len(suffix)]) * factor
    return float(value)


payload = json.load(sys.stdin)
nodes, pods = payload["nodes"], payload["pods"]
alloc = []
for node in nodes["items"]:
    conditions = {item["type"]: item["status"] for item in node["status"].get("conditions", [])}
    if conditions.get("Ready") != "True" or node.get("spec", {}).get("unschedulable", False):
        raise SystemExit("capacity gate requires exactly three Ready schedulable nodes")
    values = node["status"]["allocatable"]
    alloc.append((quantity(values["cpu"], True), quantity(values["memory"])))
if len(alloc) != 3:
    raise SystemExit("capacity gate requires exactly three nodes")
remaining_cpu = sum(v[0] for v in alloc) - max(v[0] for v in alloc)
remaining_memory = sum(v[1] for v in alloc) - max(v[1] for v in alloc)
requested_cpu = requested_memory = 0.0
for pod in pods["items"]:
    if pod.get("status", {}).get("phase") in {"Succeeded", "Failed"}:
        continue
    regular_cpu = regular_memory = 0.0
    for container in pod.get("spec", {}).get("containers", []):
        requests = container.get("resources", {}).get("requests", {})
        regular_cpu += quantity(requests.get("cpu", "0"), True)
        regular_memory += quantity(requests.get("memory", "0"))
    init_cpu = init_memory = 0.0
    for container in pod.get("spec", {}).get("initContainers", []):
        requests = container.get("resources", {}).get("requests", {})
        init_cpu = max(init_cpu, quantity(requests.get("cpu", "0"), True))
        init_memory = max(init_memory, quantity(requests.get("memory", "0")))
    overhead = pod.get("spec", {}).get("overhead", {})
    requested_cpu += max(regular_cpu, init_cpu) + quantity(overhead.get("cpu", "0"), True)
    requested_memory += max(regular_memory, init_memory) + quantity(overhead.get("memory", "0"))
cpu_ratio = requested_cpu / remaining_cpu if remaining_cpu else 1
memory_ratio = requested_memory / remaining_memory if remaining_memory else 1
if max(cpu_ratio, memory_ratio) > 0.85:
    raise SystemExit(f"one-node-loss capacity exceeds 85%: cpu={cpu_ratio:.3f} memory={memory_ratio:.3f}")
print(json.dumps({"cpu_ratio": cpu_ratio, "memory_ratio": memory_ratio}, sort_keys=True))
