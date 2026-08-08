.PHONY: lint render bootstrap-access bootstrap-inventory bootstrap-management inventory lockdown site verify

lint:
	ansible-lint ansible/
	yamllint .
	shellcheck ansible/roles/**/files/*.sh 2>/dev/null || true

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
	ansible-playbook -i .runtime/bootstrap-inventory.yaml ansible/playbooks/management-access.yml

inventory:
	gabiactl inventory -f infra/bootstrap/desired-infrastructure.yaml --connect-via private -o .runtime/inventory.yaml

lockdown:
	gabiactl access close -f infra/bootstrap/desired-infrastructure.yaml --targets k3s-01,k3s-02

site:
	ansible-playbook -i .runtime/inventory.yaml ansible/playbooks/site.yml

verify:
	ansible-playbook -i .runtime/inventory.yaml ansible/playbooks/verify.yml
