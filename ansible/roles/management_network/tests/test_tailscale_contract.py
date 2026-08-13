#!/usr/bin/env python3
"""Static safety contract for the Tailscale management role."""

from pathlib import Path
import unittest


ROLE = Path(__file__).resolve().parents[1]


class TailscaleManagementContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.defaults = (ROLE / "defaults/main.yml").read_text(encoding="utf-8")
        cls.tasks = (ROLE / "tasks/main.yml").read_text(encoding="utf-8")

    def test_auth_key_is_temporary_and_never_logged(self) -> None:
        self.assertIn("--auth-key=file:", self.tasks)
        self.assertIn("not management_network_tailscale_local_auth_key.stat.islnk", self.tasks)
        self.assertIn("state: absent", self.tasks)
        self.assertGreaterEqual(self.tasks.count("no_log: true"), 3)

    def test_tailscale_identity_is_verified(self) -> None:
        self.assertIn("BackendState == 'Running'", self.tasks)
        self.assertIn("management_network_tailscale_server_tag", self.tasks)

    def test_running_node_skips_authentication(self) -> None:
        self.assertIn("management_network_tailscale_needs_auth", self.tasks)
        self.assertIn("when: management_network_tailscale_needs_auth | bool", self.tasks)


if __name__ == "__main__":
    unittest.main()
