.PHONY: lint collections render bootstrap-access bootstrap-inventory bootstrap-management inventory lockdown site verify verify-cilium test-verify test-failover-drill test-etcd-recovery test-k3s-cilium-upgrade test-full-rebuild test-postgresql-pitr

ANSIBLE_CONFIG := $(CURDIR)/ansible/ansible.cfg
ANSIBLE_COLLECTIONS_PATH := $(CURDIR)/.ansible/collections

lint:
	ANSIBLE_CONFIG=$(ANSIBLE_CONFIG) ANSIBLE_COLLECTIONS_PATH=$(ANSIBLE_COLLECTIONS_PATH) ansible-lint ansible/
	yamllint ansible/
	find ansible/roles -type f -path '*/files/*.sh' -exec shellcheck {} +

collections:
	ANSIBLE_CONFIG=$(ANSIBLE_CONFIG) ansible-galaxy collection install -r ansible/requirements.yml -p $(ANSIBLE_COLLECTIONS_PATH)

render:
	@for overlay in normal degraded maintenance; do \
		echo "== gitops/apps/aligner-api/overlays/$$overlay =="; \
		kubectl kustomize gitops/apps/aligner-api/overlays/$$overlay > /dev/null || exit 1; \
	done
	@echo "모든 overlay 렌더 성공"

bootstrap-access:
	@test -n "$$ALIGNER_BOOTSTRAP_CIDR" || (echo "ALIGNER_BOOTSTRAP_CIDR=<current-ip>/32 가 필요합니다"; exit 1)
	gabiactl access open -f infra/bootstrap/desired-infrastructure.yaml --cidr "$$ALIGNER_BOOTSTRAP_CIDR" --targets k3s-01,k3s-02

bootstrap-inventory:
	gabiactl inventory -f infra/bootstrap/desired-infrastructure.yaml --connect-via public -o .runtime/bootstrap-inventory.yaml

bootstrap-management:
	ANSIBLE_CONFIG=$(ANSIBLE_CONFIG) ANSIBLE_COLLECTIONS_PATH=$(ANSIBLE_COLLECTIONS_PATH) ansible-playbook -i .runtime/bootstrap-inventory.yaml ansible/playbooks/management-access.yml

inventory:
	gabiactl inventory -f infra/bootstrap/desired-infrastructure.yaml --connect-via private -o .runtime/inventory.yaml

lockdown:
	gabiactl access close -f infra/bootstrap/desired-infrastructure.yaml --targets k3s-01,k3s-02

site:
	ANSIBLE_CONFIG=$(ANSIBLE_CONFIG) ANSIBLE_COLLECTIONS_PATH=$(ANSIBLE_COLLECTIONS_PATH) ansible-playbook -i .runtime/inventory.yaml ansible/playbooks/site.yml

verify:
	ANSIBLE_CONFIG=$(ANSIBLE_CONFIG) ANSIBLE_COLLECTIONS_PATH=$(ANSIBLE_COLLECTIONS_PATH) ansible-playbook -i .runtime/inventory.yaml ansible/playbooks/verify.yml

verify-cilium:
	ANSIBLE_CONFIG=$(ANSIBLE_CONFIG) ANSIBLE_COLLECTIONS_PATH=$(ANSIBLE_COLLECTIONS_PATH) ansible-playbook -i .runtime/inventory.yaml ansible/playbooks/verify-cilium.yml

test-verify:
	python3 ansible/playbooks/scripts/test_verify_production_gate.py

test-failover-drill:
	python3 scripts/tests/test_node_failover_drill.py

test-etcd-recovery:
	python3 scripts/test_validate_etcd_recovery.py

test-k3s-cilium-upgrade:
	python3 scripts/test_validate_k3s_cilium_upgrade.py

test-full-rebuild:
	python3 scripts/test_validate_full_rebuild.py

test-postgresql-pitr:
	python3 scripts/test_validate_postgresql_pitr.py
