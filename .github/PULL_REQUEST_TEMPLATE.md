## 무엇을 왜 하는가

<!-- 이 PR이 하는 일과 이유. 설계 문서 §번호가 있으면 함께 적는다. -->

## 관련 이슈

<!-- Closes #123 / Refs #123 -->

## 어떻게 검증했는가

<!-- 예: ansible-lint 통과, kustomize build 통과, 로컬에서 gitleaks detect 실행 -->

## 체크리스트

- [ ] `make lint` / `make render` 통과 확인
- [ ] 로컬에서 `gitleaks detect` 실행 — 시크릿 없음 확인
- [ ] `.runtime/`, `*.tfstate`, `*.kubeconfig` 등이 diff에 없음을 확인

### 아래 경로를 변경했다면 추가로 확인

- [ ] `ansible/roles/management_network/` 또는 `firewall/` — **순서를 바꾸지 않았다**
      (management_network 검증 전에 firewall 이 22/6443 을 닫으면 노드 잠금 사고가 난다)
- [ ] `gitops/infrastructure/**/external-secrets*` 또는 `secret-stores/` — CODEOWNERS 승인 필요
- [ ] `infra/bootstrap/security-groups.yaml` — CODEOWNERS 승인 필요
- [ ] Cilium 관련 (`ansible/roles/cilium/`, `cluster_cidr`) — **Day 1 확정값이라 사후 변경 불가**.
      정말 바꿔야 한다면 재구축이 필요함을 PR 설명에 명시했다

## 리뷰어에게

<!-- 특별히 봐줬으면 하는 부분, 트레이드오프, 후속 작업으로 미룬 것 -->
