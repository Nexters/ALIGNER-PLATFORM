#!/usr/bin/env python3
import importlib.util
import pathlib
import unittest


SPEC = importlib.util.spec_from_file_location("validate_k3s_cilium_upgrade", pathlib.Path(__file__).with_name("validate_k3s_cilium_upgrade.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def gate():
    return {"ready_nodes": 3, "etcd_healthy_members": 3, "cilium_connectivity": True, "user_request_succeeded": True, "quorum_maintained": True}


def passing_result():
    return {
        "issue": 34, "status": "PASS", "started_at_utc": "2026-08-12T00:00:00Z",
        "versions": {"source": {"k3s": "v1.35.7+k3s1", "cilium_chart": "1.19.3"}, "target": {"k3s": "v1.36.3+k3s1", "cilium_chart": "1.20.0"}},
        "compatibility_evidence": {"k3s_release": "https://docs.k3s.io/", "cilium_upgrade": "https://docs.cilium.io/", "target_kubernetes_supported": True},
        "backup_checks": {"etcd_snapshot_current": True, "postgresql_base_backup_current": True, "postgresql_wal_archive_current": True},
        "current_install": {"k3s_binary": "v1.35.7+k3s1", "cilium_chart": "1.19.3"},
        "nodes": [{"name": name, "order": index, "cnpg": {"was_primary": index == 2, "switchover_completed_before_drain": index == 2}, "drain_completed": True, "upgrade_completed": True, "uncordon_completed": True, "health_gate": gate()} for index, name in enumerate(("k3s-01", "k3s-02", "k3s-03"), 1)],
        "rollback_test": {"demonstrated": True, "restored_source_k3s": True, "restored_source_cilium": True, "health_gate": gate()},
        "changes": {"error_rate_percent": 0, "total_duration_seconds": 120, "cpu_millicores_delta": 10, "memory_bytes_delta": 1024},
    }


class K3sCiliumUpgradeResultTest(unittest.TestCase):
    def test_not_executed_is_initial_evidence(self):
        self.assertEqual([], MODULE.validate({"issue": 34, "status": "NOT_EXECUTED"}))

    def test_pass_requires_pins_compatibility_backups_and_current_install(self):
        for path, value in ((["versions", "target", "k3s"], "latest"), (["compatibility_evidence", "target_kubernetes_supported"], False), (["backup_checks", "etcd_snapshot_current"], False), (["current_install", "cilium_chart"], "1.20.0")):
            result = passing_result()
            target = result
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            self.assertTrue(MODULE.validate(result), path)

    def test_pass_requires_exact_distinct_k3s_and_cilium_versions(self):
        for path, value in ((["versions", "target", "k3s"], "1.36.3+k3s1"), (["versions", "target", "cilium_chart"], "v1.20.0")):
            result = passing_result()
            target = result
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            self.assertIn("versions.target must contain exact K3s and Cilium semantic versions", MODULE.validate(result))
        result = passing_result()
        result["versions"]["target"] = result["versions"]["source"].copy()
        self.assertIn("versions.source and versions.target must differ", MODULE.validate(result))

    def test_pass_rejects_unordered_nodes_or_any_node_gate_failure(self):
        result = passing_result()
        result["nodes"][1]["name"] = "k3s-03"
        self.assertTrue(MODULE.validate(result))
        for field, value in (("ready_nodes", 2), ("etcd_healthy_members", 2), ("cilium_connectivity", False), ("user_request_succeeded", False), ("quorum_maintained", False)):
            result = passing_result()
            result["nodes"][0]["health_gate"][field] = value
            self.assertTrue(MODULE.validate(result), field)

    def test_pass_requires_primary_switchover_rollback_and_change_records(self):
        result = passing_result()
        result["nodes"][1]["cnpg"]["switchover_completed_before_drain"] = False
        self.assertTrue(MODULE.validate(result))
        result = passing_result()
        result["rollback_test"]["demonstrated"] = False
        self.assertTrue(MODULE.validate(result))
        result = passing_result()
        del result["changes"]["memory_bytes_delta"]
        self.assertTrue(MODULE.validate(result))


if __name__ == "__main__":
    unittest.main()
