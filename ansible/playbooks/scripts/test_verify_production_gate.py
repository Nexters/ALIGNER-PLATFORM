#!/usr/bin/env python3
import importlib.util
import pathlib
import unittest
from decimal import Decimal

SPEC = importlib.util.spec_from_file_location(
    "verify_production_gate", pathlib.Path(__file__).with_name("verify-production-gate.py")
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
capacity_after_one_node_loss = MODULE.capacity_after_one_node_loss


class CapacityAfterOneNodeLossTest(unittest.TestCase):
    def node(self, cpu, memory):
        return {"spec": {}, "status": {"allocatable": {"cpu": cpu, "memory": memory}, "conditions": [{"type": "Ready", "status": "True"}]}}

    def test_uses_two_smallest_nodes_after_largest_loss(self):
        nodes = [self.node("4", "8Gi"), self.node("2", "4Gi"), self.node("2", "4Gi")]
        pods = [{"spec": {"containers": [{"resources": {"requests": {"cpu": "2", "memory": "4Gi"}}}]}}]
        ratios = capacity_after_one_node_loss(nodes, pods)
        self.assertEqual(Decimal("0.5"), ratios["cpu"])
        self.assertEqual(Decimal("0.5"), ratios["memory"])

    def test_checks_each_actual_heterogeneous_failure_pair(self):
        nodes = [self.node("8", "2Gi"), self.node("2", "16Gi"), self.node("2", "16Gi")]
        pods = [{"spec": {"containers": [{"resources": {"requests": {"cpu": "2", "memory": "2Gi"}}}]}}]
        self.assertEqual(Decimal("0.5"), capacity_after_one_node_loss(nodes, pods)["cpu"])

    def test_effective_requests_include_sidecars_init_overhead_and_pod_level(self):
        nodes = [self.node("10", "20Gi") for _ in range(3)]
        pod = {"spec": {"containers": [{"resources": {"requests": {"cpu": "1", "memory": "1Gi"}}}], "initContainers": [{"restartPolicy": "Always", "resources": {"requests": {"cpu": "2", "memory": "2Gi"}}}, {"resources": {"requests": {"cpu": "4", "memory": "4Gi"}}}], "resources": {"requests": {"cpu": "7", "memory": "7Gi"}}, "overhead": {"cpu": "100m", "memory": "100Mi"}}}
        ratios = capacity_after_one_node_loss(nodes, [pod, {"status": {"phase": "Succeeded"}, "spec": {"containers": [{"resources": {"requests": {"cpu": "99", "memory": "99Gi"}}}]}}])
        self.assertEqual(Decimal("0.355"), ratios["cpu"])

    def test_quantity_grammar_and_invalid_input_are_structured(self):
        self.assertEqual(Decimal(1000), MODULE.quantity("1e3"))
        self.assertEqual(Decimal(1024), MODULE.quantity("1Ki"))
        self.assertEqual(Decimal("0.001"), MODULE.quantity("0.1m", resource="cpu"))
        self.assertEqual(Decimal(1), MODULE.quantity("0.1", resource="memory"))
        self.assertEqual(Decimal(1000), MODULE.quantity("1K", resource="memory"))
        self.assertEqual(Decimal(1000), MODULE.quantity("1e3", resource="memory"))
        with self.assertRaises(MODULE.CapacityInputError):
            MODULE.quantity("NaN")
        with self.assertRaises(MODULE.CapacityInputError):
            MODULE.quantity("1e3Mi", resource="memory")
        with self.assertRaises(MODULE.CapacityInputError):
            MODULE.quantity("1e3n")
        with self.assertRaises(MODULE.CapacityInputError):
            MODULE.quantity("1e30", resource="memory")
        nodes = [self.node("1", "1Gi") for _ in range(3)]
        with self.assertRaises(MODULE.CapacityInputError):
            capacity_after_one_node_loss(nodes, [{"spec": {"containers": [{"resources": {"requests": {"cpu": "2", "memory": "1Gi"}}}]}}])

    def test_status_allocated_resources_and_taints_fail_closed(self):
        nodes = [self.node("4", "8Gi") for _ in range(3)]
        pod = {
            "spec": {"containers": [{"name": "app", "resources": {"requests": {"cpu": "500m", "memory": "1Gi"}}}]},
            "status": {"containerStatuses": [{"name": "app", "allocatedResources": {"cpu": "5", "memory": "1Gi"}}]},
        }
        with self.assertRaises(MODULE.CapacityInputError):
            capacity_after_one_node_loss(nodes, [pod])
        nodes[0]["spec"]["taints"] = [{"effect": "NoExecute"}]
        with self.assertRaises(MODULE.CapacityInputError):
            capacity_after_one_node_loss(nodes, [])

    def test_resize_requests_match_kubernetes_effective_aggregation(self):
        pod = {
            "spec": {
                "containers": [
                    {"name": "a", "resources": {"requests": {"cpu": "5"}}},
                    {"name": "b", "resources": {"requests": {"cpu": "1"}}},
                ]
            },
            "status": {
                "containerStatuses": [
                    {"name": "a", "resources": {"requests": {"cpu": "1"}}},
                    {"name": "b", "resources": {"requests": {"cpu": "5"}}},
                ]
            },
        }
        self.assertEqual(Decimal("6"), MODULE.effective_pod_requests(pod, 0)["cpu"])

        pod["status"]["conditions"] = [{
            "type": "PodResizePending", "status": "True", "reason": "Infeasible"
        }]
        self.assertEqual(Decimal("6"), MODULE.effective_pod_requests(pod, 0)["cpu"])
        pod["status"]["containerStatuses"][1]["resources"]["requests"]["cpu"] = "500m"
        self.assertEqual(Decimal("1.5"), MODULE.effective_pod_requests(pod, 0)["cpu"])

    def test_pod_level_request_overrides_container_sum(self):
        pod = {
            "spec": {
                "containers": [
                    {"resources": {"requests": {"cpu": "4", "memory": "4Gi"}}},
                    {"resources": {"requests": {"cpu": "4", "memory": "4Gi"}}},
                ],
                "resources": {"requests": {"cpu": "2"}},
            }
        }
        request = MODULE.effective_pod_requests(pod, 0)
        self.assertEqual(Decimal("2"), request["cpu"])
        self.assertEqual(Decimal(8 * 2**30), request["memory"])


if __name__ == "__main__":
    unittest.main()
