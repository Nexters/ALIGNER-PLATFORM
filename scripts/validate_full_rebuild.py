#!/usr/bin/env python3
"""Validate secret-free evidence for issue #35 full rebuild and decommission."""

import argparse
import json
import re
import sys


ALLOWED_STATUS = {"NOT_EXECUTED", "PASS", "FAIL"}
PHASES = ("l1_gabiactl", "l2_tailscale_ansible_k3s_cilium", "l3_argo_root")
SHUTDOWN_ORDER = ["apps", "platform", "cluster", "load_balancer", "servers", "network"]
FORBIDDEN_FIELD = re.compile(
    r"(authorization|credential|password|access[_-]?(?:key|token)|private[_-]?key|"
    r"secret.*(?:key|value|data|content)|token.*(?:value|data|content))",
    re.I,
)


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


def checksum(value):
    return isinstance(value, str) and bool(re.fullmatch(r"sha256:[0-9a-fA-F]{64}", value))


def validate(result):
    errors = []
    if not isinstance(result, dict):
        return ["result must be an object"]
    if result.get("issue") != 35:
        errors.append("issue must be 35")
    if result.get("status") not in ALLOWED_STATUS:
        errors.append("status must be NOT_EXECUTED, PASS, or FAIL")
    if result.get("status") == "NOT_EXECUTED":
        if set(result) != {"issue", "status"}:
            errors.append("NOT_EXECUTED result may contain only issue and status")
        return errors

    required = {"issue", "status", "environment", "phases", "restores", "public_validation", "outcomes", "shutdown"}
    missing = required - set(result)
    if missing:
        errors.append("missing required fields: " + ",".join(sorted(missing)))

    environment = result.get("environment")
    environment_fields = {"name", "classification", "cost_limit_krw", "started_at_utc", "ended_at_utc", "deletion_owner"}
    if not isinstance(environment, dict) or set(environment) != environment_fields:
        errors.append("environment must contain only name, classification, cost_limit_krw, started_at_utc, ended_at_utc, and deletion_owner")
    else:
        name = environment.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"rebuild-[a-z0-9-]+", name):
            errors.append("environment.name must be a known isolated rebuild-* environment")
        if environment.get("classification") != "isolated-rebuild":
            errors.append("environment.classification must be isolated-rebuild")
        if not non_negative_number(environment.get("cost_limit_krw")) or environment["cost_limit_krw"] <= 0:
            errors.append("environment.cost_limit_krw must be a positive number")
        for field in ("started_at_utc", "ended_at_utc", "deletion_owner"):
            if not isinstance(environment.get(field), str) or not environment[field]:
                errors.append("environment." + field + " must be a non-empty string")

    phases = result.get("phases")
    if not isinstance(phases, dict) or set(phases) != set(PHASES):
        errors.append("phases must contain l1_gabiactl, l2_tailscale_ansible_k3s_cilium, and l3_argo_root")
    elif any(phases.get(phase) is not True for phase in PHASES):
        errors.append("all rebuild phases must be completed")

    restores = result.get("restores")
    restore_fields = {"etcd", "postgresql"}
    if not isinstance(restores, dict) or set(restores) != restore_fields:
        errors.append("restores must contain only etcd and postgresql")
    else:
        for item in restore_fields:
            record = restores.get(item)
            expected = {"b2_checksum", "restored_checksum", "checksum_match"}
            if not isinstance(record, dict) or set(record) != expected or not checksum(record.get("b2_checksum")) or not checksum(record.get("restored_checksum")) or record.get("checksum_match") is not True or record.get("b2_checksum") != record.get("restored_checksum"):
                errors.append("restores." + item + " must prove matching B2 and restored SHA-256 checksums")

    public = result.get("public_validation")
    public_fields = {"load_balancer", "dns", "tls", "login", "core_write"}
    if not isinstance(public, dict) or set(public) != public_fields or any(public.get(field) is not True for field in public_fields):
        errors.append("public_validation must prove load_balancer, dns, tls, login, and core_write")

    outcomes = result.get("outcomes")
    outcome_fields = {"total_rto_seconds", "total_rpo_seconds", "manual_actions", "failures", "actual_cost_krw"}
    if not isinstance(outcomes, dict) or set(outcomes) != outcome_fields:
        errors.append("outcomes must contain total RTO/RPO, manual actions, failures, and actual cost")
    elif not all(non_negative_number(outcomes.get(field)) for field in ("total_rto_seconds", "total_rpo_seconds", "actual_cost_krw")) or not isinstance(outcomes.get("manual_actions"), list) or not isinstance(outcomes.get("failures"), list):
        errors.append("outcomes must record non-negative RTO/RPO/cost and manual_actions/failures lists")

    shutdown = result.get("shutdown")
    shutdown_fields = {"final_backups", "deletion_order", "cleanup", "billing_zero_evidence"}
    if not isinstance(shutdown, dict) or set(shutdown) != shutdown_fields:
        errors.append("shutdown must contain final_backups, deletion_order, cleanup, and billing_zero_evidence")
    else:
        final_backups = shutdown.get("final_backups")
        if not isinstance(final_backups, dict) or set(final_backups) != restore_fields:
            errors.append("shutdown.final_backups must contain etcd and postgresql")
        else:
            for item in restore_fields:
                record = final_backups.get(item)
                expected = {"b2_checksum"}
                if not isinstance(record, dict) or set(record) != expected or not checksum(record.get("b2_checksum")):
                    errors.append("shutdown.final_backups." + item + " must prove a B2 SHA-256 checksum")
        if shutdown.get("deletion_order") != SHUTDOWN_ORDER:
            errors.append("shutdown.deletion_order must be apps, platform, cluster, load_balancer, servers, network")
        cleanup = shutdown.get("cleanup")
        if not isinstance(cleanup, dict) or set(cleanup) != set(SHUTDOWN_ORDER) or any(cleanup.get(item) is not True for item in SHUTDOWN_ORDER):
            errors.append("shutdown.cleanup must prove every deletion phase completed")
        billing = shutdown.get("billing_zero_evidence")
        billing_fields = {"gabia_console", "gabia_billing", "residual_billable_resources"}
        if not isinstance(billing, dict) or set(billing) != billing_fields or billing.get("gabia_console") is not True or billing.get("gabia_billing") is not True or billing.get("residual_billable_resources") != 0:
            errors.append("shutdown.billing_zero_evidence must prove zero Gabia console/billing resources")

    for key in secret_like_keys(result):
        errors.append("secret-like field is forbidden: " + key)
    if result.get("status") == "PASS" and errors:
        errors.append("PASS requires every phase, restore checksum, public validation, shutdown cleanup, and zero-billing record")
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
