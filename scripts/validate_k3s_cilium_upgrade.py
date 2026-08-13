#!/usr/bin/env python3
"""Validate secret-free evidence for the issue #34 K3s/Cilium upgrade."""

import argparse
import json
import re
import sys


ALLOWED_STATUS = {"NOT_EXECUTED", "PASS", "FAIL"}
NODE_ORDER = ["k3s-01", "k3s-02", "k3s-03"]
FORBIDDEN_FIELD = re.compile(
    r"(authorization|credential|password|access[_-]?(?:key|token)|private[_-]?key|"
    r"secret.*(?:key|value|data|content)|token.*(?:value|data|content))",
    re.I,
)
K3S_VERSION = re.compile(r"v\d+\.\d+\.\d+\+k3s\d+")
CILIUM_VERSION = re.compile(r"\d+\.\d+\.\d+")


def secret_like_keys(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            if isinstance(key, str) and FORBIDDEN_FIELD.search(key):
                yield key
            yield from secret_like_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from secret_like_keys(nested)


def non_negative_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def pinned(value):
    return isinstance(value, str) and bool(value.strip()) and "latest" not in value.casefold()


def health_gate(value):
    fields = {"ready_nodes", "etcd_healthy_members", "cilium_connectivity", "user_request_succeeded", "quorum_maintained"}
    return isinstance(value, dict) and set(value) == fields and value["ready_nodes"] == 3 and value["etcd_healthy_members"] == 3 and all(value[field] is True for field in fields - {"ready_nodes", "etcd_healthy_members"})


def validate(result):
    errors = []
    if not isinstance(result, dict):
        return ["result must be an object"]
    if result.get("issue") != 34:
        errors.append("issue must be 34")
    if result.get("status") not in ALLOWED_STATUS:
        errors.append("status must be NOT_EXECUTED, PASS, or FAIL")
    if result.get("status") == "NOT_EXECUTED":
        if set(result) != {"issue", "status"}:
            errors.append("NOT_EXECUTED result may contain only issue and status")
        return errors

    required = {"issue", "status", "started_at_utc", "versions", "compatibility_evidence", "backup_checks", "current_install", "nodes", "rollback_test", "changes"}
    missing = required - set(result)
    if missing:
        errors.append("missing required fields: " + ",".join(sorted(missing)))

    versions = result.get("versions")
    if not isinstance(versions, dict) or set(versions) != {"source", "target"}:
        errors.append("versions must contain only source and target")
    else:
        for label in ("source", "target"):
            item = versions.get(label)
            if not isinstance(item, dict) or set(item) != {"k3s", "cilium_chart"} or not isinstance(item.get("k3s"), str) or not K3S_VERSION.fullmatch(item["k3s"]) or not isinstance(item.get("cilium_chart"), str) or not CILIUM_VERSION.fullmatch(item["cilium_chart"]):
                errors.append("versions." + label + " must contain exact K3s and Cilium semantic versions")
        if versions.get("source") == versions.get("target"):
            errors.append("versions.source and versions.target must differ")

    compatibility = result.get("compatibility_evidence")
    compatibility_fields = {"k3s_release", "cilium_upgrade", "target_kubernetes_supported"}
    if not isinstance(compatibility, dict) or set(compatibility) != compatibility_fields or not all(isinstance(compatibility.get(field), str) and compatibility[field].startswith("https://") for field in ("k3s_release", "cilium_upgrade")) or compatibility.get("target_kubernetes_supported") is not True:
        errors.append("compatibility_evidence must contain HTTPS K3s/Cilium evidence and target_kubernetes_supported=true")

    backups = result.get("backup_checks")
    backup_fields = {"etcd_snapshot_current", "postgresql_base_backup_current", "postgresql_wal_archive_current"}
    if not isinstance(backups, dict) or set(backups) != backup_fields or not all(backups.get(field) is True for field in backup_fields):
        errors.append("backup_checks must prove current etcd snapshot and PostgreSQL backup/WAL archive")

    current = result.get("current_install")
    source = versions.get("source") if isinstance(versions, dict) else None
    if not isinstance(current, dict) or set(current) != {"k3s_binary", "cilium_chart"} or not all(pinned(current.get(field)) for field in current) or not isinstance(source, dict) or current.get("k3s_binary") != source.get("k3s") or current.get("cilium_chart") != source.get("cilium_chart"):
        errors.append("current_install must prove the current binary/chart equal the source pins")

    nodes = result.get("nodes")
    expected_node_fields = {"name", "order", "cnpg", "drain_completed", "upgrade_completed", "uncordon_completed", "health_gate"}
    if not isinstance(nodes, list) or len(nodes) != 3:
        errors.append("nodes must contain exactly three ordered nodes")
    else:
        for index, node in enumerate(nodes, 1):
            if not isinstance(node, dict) or set(node) != expected_node_fields or node.get("name") != NODE_ORDER[index - 1] or node.get("order") != index:
                errors.append("nodes must be k3s-01, k3s-02, k3s-03 in order")
                break
            cnpg = node.get("cnpg")
            if not isinstance(cnpg, dict) or set(cnpg) != {"was_primary", "switchover_completed_before_drain"} or not isinstance(cnpg.get("was_primary"), bool) or not isinstance(cnpg.get("switchover_completed_before_drain"), bool) or (cnpg["was_primary"] and not cnpg["switchover_completed_before_drain"]):
                errors.append("each node must record CNPG primary status and pre-drain switchover")
            if any(node.get(field) is not True for field in ("drain_completed", "upgrade_completed", "uncordon_completed")):
                errors.append("each node must prove drain, upgrade, and uncordon completion")
            if not health_gate(node.get("health_gate")):
                errors.append("each node must maintain 3 Ready nodes, 3 healthy etcd members, Cilium, user, and quorum gates")

    rollback = result.get("rollback_test")
    rollback_fields = {"demonstrated", "restored_source_k3s", "restored_source_cilium", "health_gate"}
    if not isinstance(rollback, dict) or set(rollback) != rollback_fields or any(rollback.get(field) is not True for field in ("demonstrated", "restored_source_k3s", "restored_source_cilium")) or not health_gate(rollback.get("health_gate")):
        errors.append("rollback_test must demonstrate source K3s/Cilium restore with all health gates")

    changes = result.get("changes")
    if not isinstance(changes, dict) or set(changes) != {"error_rate_percent", "total_duration_seconds", "cpu_millicores_delta", "memory_bytes_delta"} or not all(non_negative_number(changes.get(field)) for field in changes):
        errors.append("changes must record non-negative error, time, CPU, and memory changes")

    for key in secret_like_keys(result):
        errors.append("secret-like field is forbidden: " + key)

    if result.get("status") == "PASS" and errors:
        errors.append("PASS requires every backup, compatibility, node, rollback, and change record check")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()
    try:
        with open(args.result, encoding="utf-8") as file:
            result = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        print(json.dumps({"valid": False, "errors": [str(error)]}, sort_keys=True))
        return 1
    errors = validate(result)
    print(json.dumps({"valid": not errors, "errors": errors}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
