#!/usr/bin/env python3
"""Validate secret-free evidence for the issue #32 PostgreSQL PITR drill."""

import argparse
import json
import re
import sys


ALLOWED_STATUS = {"NOT_EXECUTED", "PASS", "FAIL"}
SECRET_MARKERS = re.compile(r"(authorization|credential|password|secret|token|access[_-]?key|private[_-]?key)", re.I)
ALLOWED_SECRET_METADATA_KEYS = {"restore_credential_mode", "restore_credential_revoked"}


def secret_like_keys(value):
    if isinstance(value, dict):
        for key, nested_value in value.items():
            if isinstance(key, str) and key not in ALLOWED_SECRET_METADATA_KEYS and SECRET_MARKERS.search(key):
                yield key
            yield from secret_like_keys(nested_value)
    elif isinstance(value, list):
        for item in value:
            yield from secret_like_keys(item)


def validate(result):
    errors = []
    if not isinstance(result, dict):
        return ["result must be an object"]
    if result.get("issue") != 32:
        errors.append("issue must be 32")
    if result.get("status") not in ALLOWED_STATUS:
        errors.append("status must be NOT_EXECUTED, PASS, or FAIL")
    if result.get("status") == "NOT_EXECUTED":
        if set(result) != {"issue", "status"}:
            errors.append("NOT_EXECUTED result may contain only issue and status")
        return errors

    required = {"issue", "status", "started_at_utc", "target_time_utc", "production_cluster", "production_namespace", "production_pvcs", "restore_cluster", "restore_namespace", "restore_pvcs", "wal_continuity_verified", "restore_credential_mode", "baseline", "restored", "schema_match", "marker_match", "row_counts_match", "checksum_match", "rto_seconds", "rpo_seconds", "cleanup"}
    missing = required - set(result)
    if missing:
        errors.append("missing required fields: " + ",".join(sorted(missing)))
    if result.get("restore_cluster") == result.get("production_cluster"):
        errors.append("restore_cluster must differ from production_cluster")
    if result.get("restore_namespace") == result.get("production_namespace"):
        errors.append("restore_namespace must differ from production_namespace")
    production_pvcs, restore_pvcs = result.get("production_pvcs"), result.get("restore_pvcs")
    if not isinstance(production_pvcs, list) or not isinstance(restore_pvcs, list) or not restore_pvcs:
        errors.append("production_pvcs and non-empty restore_pvcs must be lists")
    elif set(production_pvcs) & set(restore_pvcs):
        errors.append("restore_pvcs must not overlap production_pvcs")
    if result.get("restore_credential_mode") != "read-only":
        errors.append("restore_credential_mode must be read-only")
    for field in ("wal_continuity_verified", "schema_match", "marker_match", "row_counts_match", "checksum_match"):
        if not isinstance(result.get(field), bool):
            errors.append(field + " must be boolean")
    for field in ("rto_seconds", "rpo_seconds"):
        if not isinstance(result.get(field), (int, float)) or isinstance(result.get(field), bool) or result.get(field, -1) < 0:
            errors.append(field + " must be a non-negative number")
    baseline, restored = result.get("baseline"), result.get("restored")
    for name, value in (("baseline", baseline), ("restored", restored)):
        if not isinstance(value, dict) or not isinstance(value.get("marker"), str) or not isinstance(value.get("row_counts"), dict) or not isinstance(value.get("checksums"), dict):
            errors.append(name + " must contain marker, row_counts, and checksums")
    cleanup = result.get("cleanup")
    cleanup_fields = {"restore_cluster_deleted", "restore_pvcs_deleted", "restore_credential_revoked"}
    if not isinstance(cleanup, dict) or any(cleanup.get(field) is not True for field in cleanup_fields):
        errors.append("cleanup must prove restore cluster, PVCs, and credential were removed")
    if result.get("status") == "PASS":
        for field in ("wal_continuity_verified", "schema_match", "marker_match", "row_counts_match", "checksum_match"):
            if result.get(field) is not True:
                errors.append("PASS requires " + field)
        if isinstance(baseline, dict) and isinstance(restored, dict):
            if baseline.get("marker") != restored.get("marker"):
                errors.append("PASS requires matching marker")
            if baseline.get("row_counts") != restored.get("row_counts"):
                errors.append("PASS requires matching row_counts")
            if baseline.get("checksums") != restored.get("checksums"):
                errors.append("PASS requires matching checksums")
    for key in secret_like_keys(result):
        errors.append("secret-like field is forbidden: " + key)
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
