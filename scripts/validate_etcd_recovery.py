#!/usr/bin/env python3
"""Validates the structure and correctness of etcd disaster recovery evidence."""
from __future__ import annotations

import argparse
import json
import sys
import re
from typing import Any, Iterator

ALLOWED_STATUS = {"NOT_EXECUTED", "PASS", "FAIL"}
FORBIDDEN_FIELD = re.compile(
    r"(authorization|credential|password|access[_-]?(?:key|token)|private[_-]?key|"
    r"secret.*(?:key|value|data|content)|token.*(?:value|data|content))",
    re.I,
)


def secret_like_keys(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, nested in value.items():
            if isinstance(key, str) and FORBIDDEN_FIELD.search(key):
                yield key
            yield from secret_like_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from secret_like_keys(nested)


def is_non_negative_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def validate(result: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(result, dict):
        return ["result must be an object"]
    if result.get("issue") != 33:
        errors.append("issue must be 33")
    if result.get("status") not in ALLOWED_STATUS:
        errors.append("status must be NOT_EXECUTED, PASS, or FAIL")
    if result.get("status") == "NOT_EXECUTED":
        if set(result) != {"issue", "status"}:
            errors.append("NOT_EXECUTED result may contain only issue and status")
        return errors

    required = {
        "issue", "status", "started_at_utc", "snapshot", "original_token_off_cluster_evidence",
        "production_environment", "recovery_environment", "first_server_restore", "api_ready_after_first",
        "etcd_members_after_first", "sequential_server_joins", "etcd_members", "nodes",
        "kubernetes_resource_counts", "gitops_reconciled", "postgresql_restore_runbook",
        "user_request_succeeded", "rpo_seconds", "rto_seconds", "manual_actions", "cleanup",
    }
    missing = required - set(result)
    if missing:
        errors.append("missing required fields: " + ",".join(sorted(missing)))

    snapshot = result.get("snapshot")
    if (
        not isinstance(snapshot, dict)
        or not isinstance(snapshot.get("b2_object"), str)
        or not isinstance(snapshot.get("created_at_utc"), str)
        or not is_non_negative_number(snapshot.get("size_bytes"))
        or not isinstance(snapshot.get("checksum"), str)
    ):
        errors.append("snapshot must contain b2_object, created_at_utc, non-negative size_bytes, and checksum")

    token = result.get("original_token_off_cluster_evidence")
    if (
        not isinstance(token, dict)
        or token.get("storage") != "off-cluster"
        or token.get("present") is not True
        or set(token) != {"storage", "present"}
    ):
        errors.append("original_token_off_cluster_evidence must prove off-cluster original token presence without its value")

    production, recovery = result.get("production_environment"), result.get("recovery_environment")
    if not isinstance(production, str) or not isinstance(recovery, str):
        errors.append("production_environment and recovery_environment must be strings")
    elif recovery.casefold() == production.casefold() or "prod" in recovery.casefold():
        errors.append("recovery_environment must be isolated from production and must not target prod")

    first = result.get("first_server_restore")
    required_first = {"manual_approval", "k3s_stopped", "cluster_reset_restore_manual"}
    if not isinstance(first, dict) or any(first.get(field) is not True for field in required_first):
        errors.append("first_server_restore must prove manual approval, K3s stop, and manual cluster-reset restore")
    if not isinstance(result.get("api_ready_after_first"), bool):
        errors.append("api_ready_after_first must be boolean")
    if result.get("etcd_members_after_first") != 1:
        errors.append("etcd_members_after_first must be 1")

    joins = result.get("sequential_server_joins")
    if (
        not isinstance(joins, list)
        or len(joins) != 2
        or not all(isinstance(server, str) and server for server in joins)
        or len(set(joins)) != 2
    ):
        errors.append("sequential_server_joins must contain two distinct servers")
    if result.get("etcd_members") != 3:
        errors.append("etcd_members must be 3")
    if result.get("nodes") != 3:
        errors.append("nodes must be 3")

    counts = result.get("kubernetes_resource_counts")
    count_fields = {"namespaces", "crds", "secrets"}
    if (
        not isinstance(counts, dict)
        or set(counts) != count_fields
        or not all(is_non_negative_number(counts.get(field)) for field in count_fields)
    ):
        errors.append("kubernetes_resource_counts must contain only non-negative namespaces, crds, and secrets counts")
    if not isinstance(result.get("gitops_reconciled"), bool):
        errors.append("gitops_reconciled must be boolean")
    if result.get("postgresql_restore_runbook") != "docs/runbooks/postgresql-recovery.md":
        errors.append("postgresql_restore_runbook must reference docs/runbooks/postgresql-recovery.md")
    if not isinstance(result.get("user_request_succeeded"), bool):
        errors.append("user_request_succeeded must be boolean")
    for field in ("rpo_seconds", "rto_seconds"):
        if not is_non_negative_number(result.get(field)):
            errors.append(field + " must be a non-negative number")
    if (
        not isinstance(result.get("manual_actions"), list)
        or not result.get("manual_actions")
        or not all(isinstance(action, str) and action for action in result.get("manual_actions"))
    ):
        errors.append("manual_actions must be a non-empty list of action records")

    cleanup = result.get("cleanup")
    cleanup_fields = {"recovery_environment_deleted", "temporary_credentials_revoked"}
    if not isinstance(cleanup, dict) or any(cleanup.get(field) is not True for field in cleanup_fields):
        errors.append("cleanup must prove the recovery environment and temporary credentials were removed")
    for key in secret_like_keys(result):
        errors.append("secret-like field is forbidden: " + key)

    if result.get("status") == "PASS":
        for field in ("api_ready_after_first", "gitops_reconciled", "user_request_succeeded"):
            if result.get(field) is not True:
                errors.append("PASS requires " + field)
        if result.get("etcd_members_after_first") != 1 or result.get("etcd_members") != 3 or result.get("nodes") != 3:
            errors.append("PASS requires API/single-member recovery followed by 3 etcd members and 3 nodes")
    return errors


def main() -> int:
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
