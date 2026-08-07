.PHONY: lint render inventory site verify

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

inventory:
	gabiactl output --format ansible > .runtime/inventory.yaml

site:
	ansible-playbook -i .runtime/inventory.yaml ansible/playbooks/site.yml

verify:
	ansible-playbook -i .runtime/inventory.yaml ansible/playbooks/verify.yml
