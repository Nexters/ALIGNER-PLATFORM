#!/usr/bin/env python3
import importlib.util
import pathlib
import unittest


SPEC = importlib.util.spec_from_file_location("validate_full_rebuild", pathlib.Path(__file__).with_name("validate_full_rebuild.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def passing_result():
    checksum = "sha256:" + "a" * 64
    return {
        "issue": 35, "status": "PASS",
        "environment": {"name": "rebuild-issue-35", "classification": "isolated-rebuild", "cost_limit_krw": 100000, "started_at_utc": "2026-08-12T00:00:00Z", "ended_at_utc": "2026-08-12T01:00:00Z", "deletion_owner": "platform-oncall"},
        "phases": {"l1_gabiactl": True, "l2_tailscale_ansible_k3s_cilium": True, "l3_argo_root": True},
        "restores": {item: {"r2_checksum": checksum, "restored_checksum": checksum, "checksum_match": True} for item in ("etcd", "postgresql")},
        "public_validation": {item: True for item in ("load_balancer", "dns", "tls", "login", "core_write")},
        "outcomes": {"total_rto_seconds": 3600, "total_rpo_seconds": 60, "manual_actions": ["approval"], "failures": [], "actual_cost_krw": 50000},
        "shutdown": {"final_backups": {item: {"r2_checksum": checksum, "aws_s3_checksum": checksum} for item in ("etcd", "postgresql")}, "deletion_order": ["apps", "platform", "cluster", "load_balancer", "servers", "network"], "cleanup": {item: True for item in ("apps", "platform", "cluster", "load_balancer", "servers", "network")}, "billing_zero_evidence": {"gabia_console": True, "gabia_billing": True, "residual_billable_resources": 0}},
    }


class FullRebuildResultTest(unittest.TestCase):
    def test_not_executed_is_initial_evidence(self):
        self.assertEqual([], MODULE.validate({"issue": 35, "status": "NOT_EXECUTED"}))
        self.assertTrue(MODULE.validate({"issue": 35, "status": "NOT_EXECUTED", "note": "no"}))

    def test_pass_requires_isolated_environment_and_all_phases(self):
        result = passing_result()
        result["environment"]["name"] = "production"
        self.assertIn("environment.name must be a known isolated rebuild-* environment", MODULE.validate(result))
        result = passing_result()
        result["phases"]["l3_argo_root"] = False
        self.assertIn("all rebuild phases must be completed", MODULE.validate(result))

    def test_pass_requires_restore_and_two_provider_checksums(self):
        result = passing_result()
        result["restores"]["etcd"]["restored_checksum"] = "sha256:different"
        self.assertIn("restores.etcd must prove matching R2 and restored SHA-256 checksums", MODULE.validate(result))
        result = passing_result()
        result["shutdown"]["final_backups"]["postgresql"]["aws_s3_checksum"] = "sha256:different"
        self.assertIn("shutdown.final_backups.postgresql must prove matching R2 and AWS S3 SHA-256 checksums", MODULE.validate(result))

    def test_pass_rejects_short_or_malformed_checksum(self):
        for value in ("sha256:abc", "sha512:" + "a" * 64):
            result = passing_result()
            result["restores"]["etcd"]["r2_checksum"] = value
            self.assertIn("restores.etcd must prove matching R2 and restored SHA-256 checksums", MODULE.validate(result))

    def test_pass_requires_order_cleanup_and_zero_billing(self):
        result = passing_result()
        result["shutdown"]["deletion_order"].reverse()
        self.assertIn("shutdown.deletion_order must be apps, platform, cluster, load_balancer, servers, network", MODULE.validate(result))
        result = passing_result()
        result["shutdown"]["billing_zero_evidence"]["residual_billable_resources"] = 1
        self.assertIn("shutdown.billing_zero_evidence must prove zero Gabia console/billing resources", MODULE.validate(result))


if __name__ == "__main__":
    unittest.main()
