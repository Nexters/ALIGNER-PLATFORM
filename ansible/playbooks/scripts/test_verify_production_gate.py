#!/usr/bin/env python3
import importlib.util
import pathlib
import unittest

SPEC = importlib.util.spec_from_file_location(
    "verify_production_gate", pathlib.Path(__file__).with_name("verify-production-gate.py")
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
capacity_after_one_node_loss = MODULE.capacity_after_one_node_loss


class CapacityAfterOneNodeLossTest(unittest.TestCase):
    def test_uses_two_smallest_nodes_after_largest_loss(self):
        nodes = [{"status": {"allocatable": {"cpu": "4", "memory": "8Gi"}}}, {"status": {"allocatable": {"cpu": "2", "memory": "4Gi"}}}, {"status": {"allocatable": {"cpu": "2", "memory": "4Gi"}}}]
        pods = [{"spec": {"containers": [{"resources": {"requests": {"cpu": "3400m", "memory": "6800Mi"}}}]}}]
        ratios = capacity_after_one_node_loss(nodes, pods)
        self.assertEqual(0.85, ratios["cpu"])
        self.assertEqual(6800 / 8192, ratios["memory"])


if __name__ == "__main__":
    unittest.main()
