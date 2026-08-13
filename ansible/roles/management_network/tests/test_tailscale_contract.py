#!/usr/bin/env python3
"""Static safety contract for the Tailscale cutover role."""

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
        self.assertIn("state: absent", self.tasks)
        self.assertGreaterEqual(self.tasks.count("no_log: true"), 3)

    def test_tailscale_identity_precedes_legacy_removal(self) -> None:
        identity = self.tasks.index("Tagged Tailscale 관리 경로 검증")
        removal = self.tasks.index("Legacy WireGuard 제거 별도 승인")
        self.assertLess(identity, removal)
        self.assertIn("BackendState == 'Running'", self.tasks)
        self.assertIn("management_network_tailscale_server_tag", self.tasks)

    def test_legacy_removal_is_double_gated_and_scoped(self) -> None:
        self.assertIn("management_network_remove_legacy_wireguard: false", self.defaults)
        self.assertIn("management_network_legacy_wireguard_removal_approved: false", self.defaults)
        self.assertIn("ansible_host == inventory_hostname", self.tasks)
        self.assertIn("difference(['/etc/wireguard/wg0.conf'])", self.tasks)
        self.assertIn("management_network_tailscale_firewall_proven | bool", self.tasks)
        self.assertIn("host: \"{{ inventory_hostname }}\"", self.tasks)

    def test_running_node_skips_authentication(self) -> None:
        self.assertIn("management_network_tailscale_needs_auth", self.tasks)
        self.assertIn("when: management_network_tailscale_needs_auth | bool", self.tasks)


if __name__ == "__main__":
    unittest.main()
