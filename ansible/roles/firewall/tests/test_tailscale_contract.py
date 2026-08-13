#!/usr/bin/env python3
"""Static contract checks for direct Tailscale firewall access."""

from pathlib import Path
import unittest


ROLE = Path(__file__).resolve().parents[1]


class TailscaleFirewallContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tasks = (ROLE / "tasks/main.yml").read_text(encoding="utf-8")
        cls.template = (ROLE / "templates/aligner.nft.j2").read_text(encoding="utf-8")

    def test_mutation_requires_tagged_running_tailscale_identity(self) -> None:
        self.assertIn("firewall_tailscale_access_proven | bool", self.tasks)
        self.assertIn("firewall_tailscale_interface in ansible_interfaces", self.tasks)
        self.assertIn(".BackendState == 'Running'", self.tasks)
        self.assertIn("firewall_tailscale_server_tag", self.tasks)
        self.assertIn("Self.Tags | default([])", self.tasks)
        self.assertGreaterEqual(self.tasks.count('host: "{{ inventory_hostname }}"'), 2)

    def test_template_allows_only_management_ports_on_tailscale(self) -> None:
        self.assertIn(
            'iifname "{{ firewall_tailscale_interface }}" tcp dport { 22, 6443 } accept',
            self.template,
        )
        self.assertNotIn("wg0", self.template)
        self.assertNotIn("management_gateway", self.template)
        self.assertIn("firewall_k3s_node_private_ips | join", self.template)
        self.assertNotIn("ip saddr {{ firewall_vpc_cidr }}", self.template)

    def test_retains_root_only_break_glass_rollback_copy(self) -> None:
        self.assertIn("dest: /etc/nftables.conf.aligner-pre-firewall", self.tasks)
        self.assertNotIn("Remove rollback copy after successful validation", self.tasks)


if __name__ == "__main__":
    unittest.main()
