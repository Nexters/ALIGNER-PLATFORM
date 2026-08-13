import json
import subprocess
import unittest
from pathlib import Path
import importlib.util
from decimal import Decimal


SCRIPT = Path(__file__).with_name("verify_cilium_capacity.py")
SPEC = importlib.util.spec_from_file_location("verify_cilium_capacity", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def node(ready=True, unschedulable=False, taints=None):
    return {"spec": {"unschedulable": unschedulable, "taints": taints or []}, "status": {"allocatable": {"cpu": "4", "memory": "8Gi"}, "conditions": [{"type": "Ready", "status": "True" if ready else "False"}]}}


class CapacityGateTest(unittest.TestCase):
    def run_gate(self, nodes, pods):
        return subprocess.run(["python3", str(SCRIPT)], input=json.dumps({"nodes": {"items": nodes}, "pods": {"items": pods}}), text=True, capture_output=True)

    def test_passes_normal_requests(self):
        pod = {"status": {"phase": "Running"}, "spec": {"containers": [{"resources": {"requests": {"cpu": "500m", "memory": "1Gi"}}}]}}
        self.assertEqual(self.run_gate([node(), node(), node()], [pod]).returncode, 0)

    def test_rejects_unready_node(self):
        self.assertNotEqual(self.run_gate([node(), node(), node(False)], []).returncode, 0)

    def test_rejects_cordoned_or_non_three_nodes(self):
        self.assertNotEqual(self.run_gate([node(), node(), node(unschedulable=True)], []).returncode, 0)
        self.assertNotEqual(self.run_gate([node(), node()], []).returncode, 0)

    def test_rejects_no_schedule_taint(self):
        self.assertNotEqual(
            self.run_gate([node(), node(), node(taints=[{"effect": "NoSchedule"}])], []).returncode,
            0,
        )

    def test_counts_init_and_overhead(self):
        pod = {"status": {"phase": "Running"}, "spec": {"containers": [{"resources": {"requests": {"cpu": "1", "memory": "1Gi"}}}], "initContainers": [{"resources": {"requests": {"cpu": "7", "memory": "14Gi"}}}], "overhead": {"cpu": "100m", "memory": "100Mi"}}}
        self.assertNotEqual(self.run_gate([node(), node(), node()], [pod]).returncode, 0)

    def test_rejects_malformed_quantity_with_structured_error(self):
        pod = {"spec": {"containers": [{"resources": {"requests": {"cpu": "wat", "memory": "1Gi"}}}]}}
        result = self.run_gate([node(), node(), node()], [pod])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('"code": "invalid_quantity"', result.stderr)

    def test_canonicalizes_quantity_precision_and_decimal_si(self):
        self.assertEqual(Decimal("0.001"), MODULE.quantity("0.1m", resource="cpu"))
        self.assertEqual(Decimal(1), MODULE.quantity("0.1", resource="memory"))
        self.assertEqual(Decimal(1000), MODULE.quantity("1K", resource="memory"))
        self.assertEqual(Decimal(1000), MODULE.quantity("1e3", resource="memory"))
        with self.assertRaises(MODULE.CapacityInputError):
            MODULE.quantity("1e3Mi", resource="memory")

    def test_status_allocated_resources_override_lower_spec_request(self):
        pod = {
            "spec": {"containers": [{"name": "app", "resources": {"requests": {"cpu": "500m", "memory": "1Gi"}}}]},
            "status": {"containerStatuses": [{"name": "app", "allocatedResources": {"cpu": "5", "memory": "1Gi"}}]},
        }
        self.assertNotEqual(self.run_gate([node(), node(), node()], [pod]).returncode, 0)

    def test_infeasible_resize_uses_actuated_request_only(self):
        pod = {
            "spec": {"containers": [{
                "name": "app", "resources": {"requests": {"cpu": "5", "memory": "1Gi"}}
            }]},
            "status": {
                "conditions": [{
                    "type": "PodResizePending", "status": "True", "reason": "Infeasible"
                }],
                "containerStatuses": [{
                    "name": "app", "resources": {"requests": {"cpu": "500m", "memory": "1Gi"}}
                }],
            },
        }
        self.assertEqual(
            Decimal("0.5"), MODULE.effective_pod_requests(pod, 0)["cpu"]
        )

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
