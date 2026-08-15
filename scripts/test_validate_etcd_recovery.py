#!/usr/bin/env python3
import importlib.util
import pathlib
import unittest


SPEC = importlib.util.spec_from_file_location("validate_etcd_recovery", pathlib.Path(__file__).with_name("validate_etcd_recovery.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def passing_result():
    return {
        "issue": 33, "status": "PASS", "started_at_utc": "2026-08-12T00:00:00Z",
        "snapshot": {"b2_object": "redacted-snapshot-id", "created_at_utc": "2026-08-11T18:00:00Z", "size_bytes": 1048576, "checksum": "sha256:redacted"},
        "original_token_off_cluster_evidence": {"storage": "off-cluster", "present": True},
        "production_environment": "production", "recovery_environment": "drill-isolated",
        "first_server_restore": {"manual_approval": True, "k3s_stopped": True, "cluster_reset_restore_manual": True},
        "api_ready_after_first": True, "etcd_members_after_first": 1,
        "sequential_server_joins": ["drill-server-02", "drill-server-03"], "etcd_members": 3, "nodes": 3,
        "kubernetes_resource_counts": {"namespaces": 7, "crds": 12, "secrets": 9},
        "gitops_reconciled": True, "postgresql_restore_runbook": "docs/runbooks/postgresql-recovery.md",
        "user_request_succeeded": True, "rpo_seconds": 1, "rto_seconds": 1,
        "manual_actions": ["approved first-server stop", "approved cluster-reset restore"],
        "cleanup": {"recovery_environment_deleted": True, "temporary_credentials_revoked": True},
    }


class EtcdRecoveryResultTest(unittest.TestCase):
    def test_not_executed_is_initial_evidence(self):
        self.assertEqual([], MODULE.validate({"issue": 33, "status": "NOT_EXECUTED"}))

    def test_rejects_production_target_and_missing_original_token_evidence(self):
        result = passing_result()
        result["recovery_environment"] = "production"
        self.assertIn("recovery_environment must be isolated from production and must not target prod", MODULE.validate(result))
        result = passing_result()
        del result["original_token_off_cluster_evidence"]
        self.assertTrue(any("original_token_off_cluster_evidence" in error for error in MODULE.validate(result)))

    def test_pass_rejects_incomplete_cluster_gitops_user_or_cleanup(self):
        for field, value in (("etcd_members", 2), ("nodes", 2), ("gitops_reconciled", False), ("user_request_succeeded", False)):
            result = passing_result()
            result[field] = value
            self.assertTrue(MODULE.validate(result), field)
        result = passing_result()
        result["cleanup"]["recovery_environment_deleted"] = False
        self.assertIn("cleanup must prove the recovery environment and temporary credentials were removed", MODULE.validate(result))

    def test_rejects_nested_secret_like_field(self):
        result = passing_result()
        result["snapshot"]["access_key"] = "redacted"
        self.assertIn("secret-like field is forbidden: access_key", MODULE.validate(result))


if __name__ == "__main__":
    unittest.main()
