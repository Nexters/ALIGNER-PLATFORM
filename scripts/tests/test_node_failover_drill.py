#!/usr/bin/env python3
import importlib.util
import pathlib
import unittest


SPEC = importlib.util.spec_from_file_location(
    "validate_node_failover_result", pathlib.Path(__file__).with_name("validate-node-failover-result.py")
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FailoverResultTest(unittest.TestCase):
    def test_not_executed_is_the_only_allowed_initial_evidence(self):
        self.assertEqual([], MODULE.validate({"issue": 31, "status": "NOT_EXECUTED"}))
        self.assertTrue(MODULE.validate({"issue": 31, "status": "NOT_EXECUTED", "note": "no"}))

    def test_pass_requires_rto_and_redundancy(self):
        valid = {"issue": 31, "status": "PASS", "started_at_utc": "2026-08-12T00:00:00Z", "write_rto_seconds": 60, "required_pods_pending": 0, "cnpg_instances_ready": 2, "manual_intervention": False}
        self.assertEqual([], MODULE.validate(valid))
        valid["manual_intervention"] = True
        self.assertIn("PASS requires manual_intervention=false", MODULE.validate(valid))
        valid["manual_intervention"] = False
        valid["write_rto_seconds"] = 60.001
        self.assertIn("PASS requires write_rto_seconds <= 60", MODULE.validate(valid))

    def test_secret_like_fields_are_rejected(self):
        result = {"issue": 31, "status": "FAIL", "started_at_utc": "2026-08-12T00:00:00Z", "write_rto_seconds": 61, "required_pods_pending": 0, "cnpg_instances_ready": 2, "manual_intervention": False, "token": "redacted"}
        self.assertIn("secret-like field is forbidden: token", MODULE.validate(result))

    def test_nested_secret_like_fields_are_rejected(self):
        result = {"issue": 31, "status": "FAIL", "started_at_utc": "2026-08-12T00:00:00Z", "write_rto_seconds": 61, "required_pods_pending": 0, "cnpg_instances_ready": 2, "manual_intervention": False, "evidence": [{"private_key": "redacted"}]}
        self.assertIn("secret-like field is forbidden: private_key", MODULE.validate(result))


if __name__ == "__main__":
    unittest.main()
