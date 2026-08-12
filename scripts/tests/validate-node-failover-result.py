#!/usr/bin/env python3
"""Validate the portable, secret-free evidence record for issue #31."""

import argparse
import json
import re
import sys


ALLOWED_STATUS = {"NOT_EXECUTED", "PASS", "FAIL"}
SECRET_MARKERS = re.compile(r"(authorization|credential|password|secret|token|access[_-]?key|private[_-]?key)", re.IGNORECASE)


def validate(result):
    errors = []
    if not isinstance(result, dict):
        return ["result must be an object"]
    if result.get("status") not in ALLOWED_STATUS:
        errors.append("status must be NOT_EXECUTED, PASS, or FAIL")
    if result.get("issue") != 31:
        errors.append("issue must be 31")
    if result.get("status") == "NOT_EXECUTED":
        if set(result) != {"issue", "status"}:
            errors.append("NOT_EXECUTED result may contain only issue and status")
        return errors
    required = {"issue", "status", "started_at_utc", "write_rto_seconds", "required_pods_pending", "cnpg_instances_ready", "manual_intervention"}
    missing = required - set(result)
    if missing:
        errors.append("missing required fields: " + ",".join(sorted(missing)))
    if not isinstance(result.get("write_rto_seconds"), (int, float)) or isinstance(result.get("write_rto_seconds"), bool) or result.get("write_rto_seconds", 61) < 0:
        errors.append("write_rto_seconds must be a non-negative number")
    if result.get("status") == "PASS" and result.get("write_rto_seconds", 61) > 60:
        errors.append("PASS requires write_rto_seconds <= 60")
    if result.get("required_pods_pending") != 0:
        errors.append("required_pods_pending must be 0")
    if result.get("cnpg_instances_ready") != 2:
        errors.append("cnpg_instances_ready must be 2")
    if not isinstance(result.get("manual_intervention"), bool):
        errors.append("manual_intervention must be boolean")
    for key in result:
        if SECRET_MARKERS.search(key):
            errors.append("secret-like field is forbidden: " + key)
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", required=True, help="path to the JSON evidence record")
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
