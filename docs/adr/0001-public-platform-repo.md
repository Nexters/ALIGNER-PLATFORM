# 0001. Public 플랫폼 저장소와 저장소 3분할

## 상태

Accepted

## 배경

`ALIGNER-SERVER`(애플리케이션 저장소)는 Public이다. 인프라 설계 문서를 같은 저장소에 두면
실제 VPC CIDR, 노드별 역할, 관리 게이트웨이 지목, break-glass 경로, 보안그룹 규칙 전체가
공개된다.

## 결정

저장소를 역할 기준으로 3분할한다. 공개 여부가 아니라 **변경 책임과 생명주기가 다르기 때문**이다.

```text
Nexters/ALIGNER-SERVER            Public   애플리케이션 소스와 CI
Nexters/ALIGNER-PLATFORM          Public   인프라·Ansible·K3s·GitOps·ADR·Runbook (이 저장소)
개인/terraform-provider-gabiacloud Private  재사용 가능한 Provider (Aligner 비종속)
```

`Nexters` Organization 아래에 둔다. CODEOWNERS의 승인자는 `@move-hoon`.

`ALIGNER-PLATFORM`을 Private이 아니라 **Public**으로 두는 이유: 보안을 저장소 비공개성에
의존하지 않는다. 인증·최소 권한·방화벽·암호화·키 관리로 보안을 보장하고, 자격증명·State·
Private Key·생성된 인벤토리(`.runtime/`)는 처음부터 Git 관리 대상에서 제외한다.

## 대안 검토

- **인프라 저장소를 Private으로 유지** — 실제 값 노출을 저장소 비공개에 의존하게 된다.
  포트·구조가 노출돼도 안전해야 한다는 원칙과 맞지 않는다.
- **별도 `ALIGNER-ENV` 저장소** — 단일 클러스터에서 저장소 분리 비용이 이득보다 크다.
- **Private Git submodule** — 로컬·CI·Argo CD 인증과 커밋 포인터 관리 복잡도가 커진다.

## 영향

- 앱 CI는 GHCR push 후 이 저장소에 image digest 변경 PR을 생성한다.
- `docs/architecture/`의 설계 문서에 들어가는 값(IP, 노드 역할 등)은 실제 값이 아니라
  변수 표기(`{{ k3s_node_ips[0] }}` 등)로 작성한다.
- Public 저장소이므로 secret scanning, push protection, CODEOWNERS를 Phase 0에서 필수로
  구성한다.
- **`Nexters` Organization 소속이라 `gitleaks-action` 대신 TruffleHog OSS를 채택했다.**
  `gitleaks-action`은 Organization 소유 저장소에서 무료 라이선스(`GITLEAKS_LICENSE`, 발급처
  [gitleaks.io](https://gitleaks.io))를 요구하는데, TruffleHog OSS Action은 라이선스 없이
  동작하고 발견한 후보를 실제 서비스 API로 검증하는 기능이 있어 오탐이 적다. `SECURITY.md`
  참조.
