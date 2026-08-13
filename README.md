# ALIGNER-PLATFORM

ALIGNER의 가비아 gCloud 3노드 K3s 플랫폼 정본이다.

```text
L1  gabiactl   가비아 인프라 생성과 Ansible inventory 출력
L2  Ansible    Ubuntu, storage, WireGuard, firewall, K3s, Cilium
L3  Argo CD    Traefik, Gateway API, cert-manager, ESO, CNPG, 앱
```

## 문서

- [현행 아키텍처](docs/architecture/overview.md)
- [가비아 Gen2 API 계약 조사](docs/architecture/gabia-gen2-api-contract.md)
- [구축·운영 로드맵](docs/roadmap.md)
- [ADR](docs/adr/)
- [Runbook](docs/runbooks/)
- [보관된 v7 설계](docs/archive/gabia-k3s-9month-design-v7.md) — 실행 기준 아님

## 기본 흐름

필수 도구: `ansible-core`, `ansible-lint`, `yamllint`, `shellcheck`.

Ansible 실행 전 고정 collection을 설치한다.

```bash
make collections
```

```bash
gabiactl validate -f infra/bootstrap/desired-infrastructure.yaml
gabiactl apply -f infra/bootstrap/desired-infrastructure.yaml
ALIGNER_BOOTSTRAP_CIDR=<current-ip>/32 make bootstrap-access bootstrap-inventory bootstrap-management
make inventory lockdown site verify
```

실제 credential, IP, state, inventory, kubeconfig는 커밋하지 않는다. 상세 기준은 [SECURITY.md](SECURITY.md)를 따른다.
