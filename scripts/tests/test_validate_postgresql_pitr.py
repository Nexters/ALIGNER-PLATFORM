#!/usr/bin/env python3
import importlib.util
import pathlib
import unittest


SPEC = importlib.util.spec_from_file_location("validate_postgresql_pitr", pathlib.Path(__file__).resolve().parent.parent / "validate_postgresql_pitr.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def passing_result():
    return {"issue": 32, "status": "PASS", "started_at_utc": "2026-08-12T00:00:00Z", "target_time_utc": "2026-08-12T00:05:00Z", "production_cluster": "aligner-db", "production_namespace": "aligner-data", "production_pvcs": ["aligner-db-1"], "restore_cluster": "aligner-db-pitr-drill", "restore_namespace": "aligner-pitr-drill", "restore_pvcs": ["aligner-db-pitr-drill-1"], "wal_continuity_verified": True, "restore_credential_mode": "read-only", "baseline": {"marker": "drill-1", "row_counts": {"sessions": 1}, "checksums": {"sessions": "abc"}}, "restored": {"marker": "drill-1", "row_counts": {"sessions": 1}, "checksums": {"sessions": "abc"}}, "schema_match": True, "marker_match": True, "row_counts_match": True, "checksum_match": True, "rto_seconds": 1, "rpo_seconds": 1, "cleanup": {"restore_cluster_deleted": True, "restore_pvcs_deleted": True, "restore_credential_revoked": True}}


class PostgreSqlPitrResultTest(unittest.TestCase):
    def test_complete_pass_is_valid(self):
        self.assertEqual([], MODULE.validate(passing_result()))

    def test_not_executed_is_initial_evidence(self):
        self.assertEqual([], MODULE.validate({"issue": 32, "status": "NOT_EXECUTED"}))

    def test_pass_rejects_production_target_and_missing_cleanup(self):
        result = passing_result()
        result["restore_cluster"] = "aligner-db"
        self.assertIn("restore_cluster must differ from production_cluster", MODULE.validate(result))
        result = passing_result()
        result["cleanup"]["restore_pvcs_deleted"] = False
        self.assertIn("cleanup must prove restore cluster, PVCs, and credential were removed", MODULE.validate(result))

    def test_pass_rejects_claimed_checksum_match_with_different_checksum(self):
        result = passing_result()
        result["restored"]["checksums"] = {"sessions": "different"}
        self.assertIn("PASS requires matching checksums", MODULE.validate(result))

    def test_rejects_nested_secret_like_field(self):
        result = passing_result()
        result["baseline"]["checksums"] = [{"access_token": "redacted"}]
        self.assertIn("secret-like field is forbidden: access_token", MODULE.validate(result))


if __name__ == "__main__":
    unittest.main()
