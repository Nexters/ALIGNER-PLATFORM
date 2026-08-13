#!/usr/bin/env python3
"""Static contract checks for WireGuard gateway/client secret separation."""

from pathlib import Path
import unittest


ROLE_DIR = Path(__file__).resolve().parents[1]


class WireGuardPeerContractTest(unittest.TestCase):
    def test_gateway_peer_assert_never_requires_client_private_key(self):
        tasks = (ROLE_DIR / "tasks/main.yml").read_text()
        gateway_peer_assert = tasks.split("- name: WireGuard 클라이언트 profile key", 1)[0]

        self.assertNotIn("item.private_key", gateway_peer_assert)
        self.assertIn(
            "map(attribute='allowed_ips.' ~ inventory_hostname)", gateway_peer_assert
        )

    def test_client_profile_uses_explicit_valid_interface_name(self):
        tasks = (ROLE_DIR / "tasks/main.yml").read_text()

        self.assertIn("item.interface_names['k3s-01'] is match", tasks)
        self.assertIn("item.interface_names['k3s-02'] is match", tasks)
        self.assertIn("/{{ item.0.interface_names[item.1] }}.conf", tasks)

    def test_gateway_changes_flush_before_firewall_role(self):
        tasks = (ROLE_DIR / "tasks/main.yml").read_text()

        self.assertIn("ansible.builtin.meta: flush_handlers", tasks)
        self.assertLess(tasks.index("flush_handlers"), tasks.index("WireGuard gateway 활성화"))


if __name__ == "__main__":
    unittest.main()
