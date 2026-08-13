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
        self.assertNotIn("management_gateway", self.template)
        self.assertIn("firewall_k3s_node_private_ips | join", self.template)
        self.assertNotIn("ip saddr {{ firewall_vpc_cidr }}", self.template)

    def test_retains_root_only_dedicated_rollback_copy(self) -> None:
        self.assertIn("dest: /etc/nftables.d/aligner.nft.aligner-pre-firewall", self.tasks)
        self.assertNotIn("Remove rollback copy after successful validation", self.tasks)

    def test_dedicated_file_never_overwrites_system_policy(self) -> None:
        self.assertNotIn("dest: /etc/nftables.conf", self.tasks)
        self.assertNotIn("src: /etc/nftables.conf", self.tasks)
        self.assertIn('line: \'include "/etc/nftables.d/*.nft"\'', self.tasks)
        self.assertIn("--file\n          - /etc/nftables.conf", self.tasks)
        self.assertLess(
            self.tasks.index("register: firewall_persisted"),
            self.tasks.index("- name: Check complete persistent nftables configuration"),
        )

    def test_missing_live_table_is_reconciled_when_file_is_unchanged(self) -> None:
        self.assertIn("register: firewall_persisted", self.tasks)
        self.assertIn("register: firewall_aligner_table", self.tasks)
        self.assertIn("firewall_reconcile_required:", self.tasks)
        self.assertIn("firewall_persisted.changed or firewall_aligner_table.rc != 0", self.tasks)
        self.assertGreaterEqual(self.tasks.count("firewall_reconcile_required | bool"), 2)
        self.assertNotIn("state: started\n\n    - name: Check new Tailscale", self.tasks)


if __name__ == "__main__":
    unittest.main()
