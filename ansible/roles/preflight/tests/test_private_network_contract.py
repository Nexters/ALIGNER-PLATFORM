import pathlib
import unittest


class PrivateNetworkPreflightContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tasks = (pathlib.Path(__file__).parent.parent / "tasks" / "main.yml").read_text()

    def test_does_not_require_private_ssh(self) -> None:
        self.assertIn("- ip\n      - route\n      - get", self.tasks)
        self.assertNotIn("ansible.builtin.wait_for", self.tasks)

    def test_join_checks_the_kubernetes_api_port(self) -> None:
        k3s_tasks = (pathlib.Path(__file__).parents[2] / "k3s" / "tasks" / "main.yml").read_text()
        self.assertIn("Verify first-server Kubernetes API is reachable before joining", k3s_tasks)
        self.assertIn("    port: 6443", k3s_tasks)
        self.assertIn("storage_data_b_guard_path | default", k3s_tasks)
        self.assertIn("Wait for joining server registration", k3s_tasks)
        self.assertNotIn("Wait for joining server node readiness", k3s_tasks)

    def test_k3s_defaults_cover_the_public_inventory_schema(self) -> None:
        defaults = (pathlib.Path(__file__).parents[2] / "k3s" / "defaults" / "main.yml").read_text()
        for variable in ("k3s_data_dir:", "application_data_dir:", "cluster_cidr:", "service_cidr:", "k3s_node_ips:"):
            self.assertIn(variable, defaults)


if __name__ == "__main__":
    unittest.main()
