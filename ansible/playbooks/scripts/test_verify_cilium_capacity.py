import json
import subprocess
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("verify_cilium_capacity.py")


def node(ready=True, unschedulable=False):
    return {"spec": {"unschedulable": unschedulable}, "status": {"allocatable": {"cpu": "4", "memory": "8Gi"}, "conditions": [{"type": "Ready", "status": "True" if ready else "False"}]}}


class CapacityGateTest(unittest.TestCase):
    def run_gate(self, nodes, pods):
        return subprocess.run(["python3", str(SCRIPT)], input=json.dumps({"nodes": {"items": nodes}, "pods": {"items": pods}}), text=True, capture_output=True)

    def test_passes_normal_requests(self):
        pod = {"status": {"phase": "Running"}, "spec": {"containers": [{"resources": {"requests": {"cpu": "500m", "memory": "1Gi"}}}]}}
        self.assertEqual(self.run_gate([node(), node(), node()], [pod]).returncode, 0)

    def test_rejects_unready_node(self):
        self.assertNotEqual(self.run_gate([node(), node(), node(False)], []).returncode, 0)

    def test_counts_init_and_overhead(self):
        pod = {"status": {"phase": "Running"}, "spec": {"containers": [{"resources": {"requests": {"cpu": "1", "memory": "1Gi"}}}], "initContainers": [{"resources": {"requests": {"cpu": "7", "memory": "14Gi"}}}], "overhead": {"cpu": "100m", "memory": "100Mi"}}}
        self.assertNotEqual(self.run_gate([node(), node(), node()], [pod]).returncode, 0)


if __name__ == "__main__":
    unittest.main()
