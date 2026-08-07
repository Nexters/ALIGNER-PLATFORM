# Contributing

## 브랜치·커밋·PR

`ALIGNER-SERVER`와 동일한 규칙을 따른다.

- `main`은 항상 배포 가능한 상태를 유지한다. 직접 push·force push를 금지한다.
- 작업은 이슈에서 시작한다 — `.github/ISSUE_TEMPLATE/`의 "작업" 또는 "장애·사고" 폼을 쓴다.
- 작업 브랜치: `<타입>/<이슈번호>-<제목>` (예: `feature/12-k3s-bootstrap`)
- PR은 draft로 열고, 작성자가 직접 준비 완료 처리한다. PR 본문은 자동 채워지는
  `.github/PULL_REQUEST_TEMPLATE.md`를 따른다 — 특히 관리망/방화벽 순서, ESO 경로,
  Cilium CIDR 관련 체크리스트는 비워두지 않는다.
- `CODEOWNERS`에 지정된 경로(ESO/SecretStore, 관리망/방화벽, 보안그룹)는 지정된 리뷰어의
  승인 없이 merge할 수 없다.

## 리뷰 우선순위

다음 변경은 최우선 리뷰 대상이다.

```text
- ansible/roles/management_network/**, ansible/roles/firewall/**
  (순서를 바꾸면 노드 잠금 사고가 난다)
- gitops/infrastructure/controllers/external-secrets/**
- gitops/infrastructure/configs/secret-stores/**
- infra/bootstrap/security-groups.yaml
```

## 로컬 검증

```bash
make lint      # ansible-lint, yamllint, tflint, shellcheck
make render    # 모든 GitOps overlay kustomize build 검증
```

## 시크릿

이 저장소에는 실제 자격증명을 절대 넣지 않는다. `SECURITY.md`와 설계 문서
(`docs/architecture/`)의 시크릿 관리 절을 먼저 읽는다.
