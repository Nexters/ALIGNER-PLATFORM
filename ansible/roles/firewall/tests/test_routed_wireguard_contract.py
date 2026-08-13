#!/usr/bin/env python3
"""Static contract checks for gateway and routed WireGuard firewall paths."""

from pathlib import Path
import unittest

from jinja2 import Environment, StrictUndefined


ROLE_DIR = Path(__file__).resolve().parents[1]


class RoutedWireGuardFirewallContractTest(unittest.TestCase):
    def setUp(self):
        self.tasks = (ROLE_DIR / "tasks/main.yml").read_text()
        environment = Environment(undefined=StrictUndefined)
        environment.filters["bool"] = bool
        self.template = environment.from_string(
            (ROLE_DIR / "templates/aligner.nft.j2").read_text()
        )

    def render(self, gateway):
        return self.template.render(
            firewall_is_management_gateway=gateway,
            firewall_wireguard_cidrs=["10.99.1.0/24", "10.99.2.0/24"],
            firewall_management_gateway_private_ips=["10.20.0.11", "10.20.0.12"],
            firewall_private_interfaces=["ens3"],
            wireguard_interface="wg0",
            wireguard_vpc_cidr="10.20.0.0/16",
            firewall_gabia_lb_private_ip="10.20.0.10",
            firewall_nodeport_range="30000-32767",
        )

    def test_gateway_requires_wg0_facts_and_renders_direct_wireguard_access(self):
        self.assertIn("wireguard_interface in ansible_interfaces", self.tasks)
        rendered = self.render(True)
        self.assertIn('iifname "wg0" tcp dport { 22, 6443 } accept', rendered)
        self.assertNotIn('iifname "ens3" tcp dport 22 accept', rendered)

    def test_non_gateway_requires_exact_gateway_private_ips_and_renders_routed_ssh(self):
        self.assertIn("firewall_management_gateway_private_ips | sort ==", self.tasks)
        self.assertIn("map('extract', hostvars, 'private_ip')", self.tasks)
        rendered = self.render(False)
        self.assertIn(
            'ip saddr { 10.20.0.11, 10.20.0.12 } iifname "ens3" tcp dport 22 accept',
            rendered,
        )
        self.assertNotIn('iifname "wg0" tcp dport { 22, 6443 } accept', rendered)

    def test_sensitive_checks_are_hidden_and_unchanged_rules_are_not_reloaded(self):
        self.assertGreaterEqual(self.tasks.count("no_log: true"), 4)
        self.assertIn("register: firewall_persisted", self.tasks)
        self.assertGreaterEqual(self.tasks.count("when: firewall_persisted.changed"), 2)


if __name__ == "__main__":
    unittest.main()
