.PHONY: lint collections render bootstrap-access bootstrap-inventory bootstrap-management bootstrap-firewall inventory lockdown site verify verify-cilium test-verify test-failover-drill test-etcd-recovery test-k3s-cilium-upgrade test-full-rebuild test-postgresql-pitr test-bootstrap-secret test-update-image test

ANSIBLE_CONFIG := $(CURDIR)/ansible/ansible.cfg
ANSIBLE_COLLECTIONS_PATH := $(CURDIR)/.ansible/collections
TAILSCALE_INVENTORY := $(CURDIR)/ansible/inventories/tailscale/hosts.yml

lint:
	ANSIBLE_CONFIG=$(ANSIBLE_CONFIG) ANSIBLE_COLLECTIONS_PATH=$(ANSIBLE_COLLECTIONS_PATH) ansible-lint ansible/
	yamllint ansible/
	find ansible/roles scripts -type f \( -name '*.sh' -o -path '*/files/*.sh' \) -exec shellcheck {} +

collections:
	ANSIBLE_CONFIG=$(ANSIBLE_CONFIG) ansible-galaxy collection install -r ansible/requirements.yml -p $(ANSIBLE_COLLECTIONS_PATH)

render:
	@for overlay in normal degraded maintenance; do \
		echo "== gitops/apps/aligner-api/overlays/$$overlay =="; \
		kubectl kustomize gitops/apps/aligner-api/overlays/$$overlay > /dev/null || exit 1; \
	done
	bash gitops/infrastructure/configs/secret-stores/tests/assert-ordering.sh
	bash gitops/infrastructure/configs/gateway/tests/assert-attachment-boundary.sh
	bash gitops/infrastructure/configs/cluster-services/tests/assert-tailscale-boundary.sh
	@echo "모든 overlay 렌더 성공"

bootstrap-access:
	@test -n "$$ALIGNER_BOOTSTRAP_CIDR" || (echo "ALIGNER_BOOTSTRAP_CIDR=<current-ip>/32 가 필요합니다"; exit 1)
	gabiactl access open -f infra/bootstrap/desired-infrastructure.yaml --cidr "$$ALIGNER_BOOTSTRAP_CIDR" --targets k3s-01,k3s-02,k3s-03

bootstrap-inventory:
	gabiactl inventory -f infra/bootstrap/desired-infrastructure.yaml --connect-via public -o .runtime/bootstrap-inventory.yaml

bootstrap-management:
	@test -n "$$ALIGNER_TAILSCALE_AUTH_KEY_FILE" || (echo "ALIGNER_TAILSCALE_AUTH_KEY_FILE이 필요합니다"; exit 1)
	@test -f "$$ALIGNER_TAILSCALE_AUTH_KEY_FILE" || (echo "ALIGNER_TAILSCALE_AUTH_KEY_FILE 파일이 필요합니다"; exit 1)
	@test ! -L "$$ALIGNER_TAILSCALE_AUTH_KEY_FILE" || (echo "auth key 파일은 symlink일 수 없습니다"; exit 1)
	@mode=$$(stat -f '%Lp' "$$ALIGNER_TAILSCALE_AUTH_KEY_FILE" 2>/dev/null || stat -c '%a' "$$ALIGNER_TAILSCALE_AUTH_KEY_FILE"); test "$$mode" = 400 -o "$$mode" = 600 || (echo "auth key 파일 권한은 0400 또는 0600이어야 합니다"; exit 1)
	ANSIBLE_CONFIG=$(ANSIBLE_CONFIG) ANSIBLE_COLLECTIONS_PATH=$(ANSIBLE_COLLECTIONS_PATH) ansible-playbook -i .runtime/bootstrap-inventory.yaml ansible/playbooks/management-access.yml -e management_network_tailscale_runtime_approved=true -e management_network_tailscale_auth_key_file="$$ALIGNER_TAILSCALE_AUTH_KEY_FILE"

bootstrap-firewall:
	@test -n "$$ALIGNER_TAILSCALE_AUTH_KEY_FILE" || (echo "ALIGNER_TAILSCALE_AUTH_KEY_FILE이 필요합니다"; exit 1)
	@test -f "$$ALIGNER_TAILSCALE_AUTH_KEY_FILE" || (echo "ALIGNER_TAILSCALE_AUTH_KEY_FILE 파일이 필요합니다"; exit 1)
	@test ! -L "$$ALIGNER_TAILSCALE_AUTH_KEY_FILE" || (echo "auth key 파일은 symlink일 수 없습니다"; exit 1)
	@mode=$$(stat -f '%Lp' "$$ALIGNER_TAILSCALE_AUTH_KEY_FILE" 2>/dev/null || stat -c '%a' "$$ALIGNER_TAILSCALE_AUTH_KEY_FILE"); test "$$mode" = 400 -o "$$mode" = 600 || (echo "auth key 파일 권한은 0400 또는 0600이어야 합니다"; exit 1)
	@test -n "$$ALIGNER_GABIA_LB_PRIVATE_IP" || (echo "ALIGNER_GABIA_LB_PRIVATE_IP가 필요합니다"; exit 1)
	ANSIBLE_CONFIG=$(ANSIBLE_CONFIG) ANSIBLE_COLLECTIONS_PATH=$(ANSIBLE_COLLECTIONS_PATH) ansible-playbook -i .runtime/bootstrap-inventory.yaml ansible/playbooks/bootstrap-firewall.yml -e management_network_tailscale_runtime_approved=true -e management_network_tailscale_auth_key_file="$$ALIGNER_TAILSCALE_AUTH_KEY_FILE" -e firewall_runtime_approved=true -e firewall_tailscale_access_proven=true -e firewall_gabia_lb_private_ip="$$ALIGNER_GABIA_LB_PRIVATE_IP"

inventory:
	gabiactl inventory -f infra/bootstrap/desired-infrastructure.yaml --connect-via private -o .runtime/inventory.yaml

lockdown:
	gabiactl access close -f infra/bootstrap/desired-infrastructure.yaml --targets k3s-01,k3s-02,k3s-03

site:
	@test -n "$$ALIGNER_RUNTIME_VARS_FILE" || (echo "ALIGNER_RUNTIME_VARS_FILE이 필요합니다"; exit 1)
	@test -f "$$ALIGNER_RUNTIME_VARS_FILE" || (echo "ALIGNER_RUNTIME_VARS_FILE 파일이 필요합니다"; exit 1)
	@test ! -L "$$ALIGNER_RUNTIME_VARS_FILE" || (echo "runtime vars 파일은 symlink일 수 없습니다"; exit 1)
	@mode=$$(stat -f '%Lp' "$$ALIGNER_RUNTIME_VARS_FILE" 2>/dev/null || stat -c '%a' "$$ALIGNER_RUNTIME_VARS_FILE"); test "$$mode" = 400 -o "$$mode" = 600 || (echo "runtime vars 파일 권한은 0400 또는 0600이어야 합니다"; exit 1)
	ANSIBLE_CONFIG=$(ANSIBLE_CONFIG) ANSIBLE_COLLECTIONS_PATH=$(ANSIBLE_COLLECTIONS_PATH) ansible-playbook -i .runtime/inventory.yaml -i $(TAILSCALE_INVENTORY) ansible/playbooks/site.yml -e "@$$ALIGNER_RUNTIME_VARS_FILE"

verify:
	ANSIBLE_CONFIG=$(ANSIBLE_CONFIG) ANSIBLE_COLLECTIONS_PATH=$(ANSIBLE_COLLECTIONS_PATH) ansible-playbook -i .runtime/inventory.yaml -i $(TAILSCALE_INVENTORY) ansible/playbooks/verify.yml

verify-cilium:
	ANSIBLE_CONFIG=$(ANSIBLE_CONFIG) ANSIBLE_COLLECTIONS_PATH=$(ANSIBLE_COLLECTIONS_PATH) ansible-playbook -i .runtime/inventory.yaml -i $(TAILSCALE_INVENTORY) ansible/playbooks/verify-cilium.yml

test-verify:
	python3 ansible/playbooks/scripts/test_verify_production_gate.py

test-failover-drill:
	python3 scripts/tests/test_node_failover_drill.py

test-etcd-recovery:
	python3 scripts/tests/test_validate_etcd_recovery.py

test-k3s-cilium-upgrade:
	python3 scripts/tests/test_validate_k3s_cilium_upgrade.py

test-full-rebuild:
	python3 scripts/tests/test_validate_full_rebuild.py

test-postgresql-pitr:
	python3 scripts/tests/test_validate_postgresql_pitr.py

test-bootstrap-secret:
	python3 scripts/tests/test_bootstrap_aligner_api_secret.py

test-update-image:
	python3 scripts/tests/test_update_aligner_api_image.py

test: test-verify test-bootstrap-secret test-update-image

