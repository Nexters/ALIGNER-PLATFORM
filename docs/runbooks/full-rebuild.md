# 전체 재구축과 종료

상태: **NOT EXECUTED**. 이 문서는 Issue #35의 승인·증적 게이트다. 이 저장소에서는 cloud resource 생성/삭제, DNS 전환, R2·etcd·PostgreSQL 복원 명령을 실행하지 않는다. 초기 증적은 [full-rebuild-result.not-executed.json](evidence/full-rebuild-result.not-executed.json)이며, 실제 secret-free 결과는 승인된 evidence 위치에서 `python3 scripts/validate_full_rebuild.py --result <evidence.json>`로 검증한다.

## 재구축 게이트

시작 전 `environment.name`은 `rebuild-`로 시작하는 격리 이름, `classification`은 `isolated-rebuild`로 정한다. 비용 한도(KRW), 시작·종료 UTC, 삭제 책임자를 승인 기록에 고정한다. production, 이름이 확인되지 않은 환경, 개인 PC 상태는 대상이 아니다.

1. **L1 — gabiactl:** 목표 정의 검증, 기존 상태 관측, 격리 inventory를 증적으로 남긴다. 현재 gabiactl write API 계약은 gate이므로 승인된 write-capability 검증 전에는 다음 단계로 진행하지 않는다.
2. **Tailscale 후 L2:** 세 노드의 MagicDNS 경유 OpenSSH 확인 뒤에만 Ansible로 storage, firewall, K3s, Cilium을 구성한다. L2 완료 증적 없이는 L3를 시작하지 않는다.
3. **L3 — Argo CD root:** root application이 platform과 앱을 reconcile한 뒤에만 데이터 복구를 승인한다.
4. **R2 복원:** etcd와 PostgreSQL(base backup/WAL)을 각각 R2에서 복원하고, 원본 R2 SHA-256과 복원 결과 SHA-256이 일치함을 기록한다.
5. **외부 경로:** LB, DNS, TLS, 로그인, 핵심 write를 모두 확인한다. DNS 변경은 이 runbook의 실행 범위 밖이며, 별도 승인된 change에서만 수행한다.
6. **결과:** 총 RTO/RPO, 수동 작업, 실패 목록, 실제 비용을 기록한다.

## 종료 게이트

종료는 R2와 AWS S3의 최종 **etcd 및 PostgreSQL** SHA-256 사본이 각각 일치한 뒤에만 승인한다. 삭제 증적의 순서는 정확히 `apps → platform → cluster → load_balancer → servers → network`다. 각 단계의 완료와 가비아 콘솔·청구 화면의 0 리소스/0 잔여 과금 증적을 모두 남긴다. AWS S3와 R2 보존 사본의 비용은 삭제 대상이 아니므로 보존·비용 기록을 별도로 유지한다.

`PASS`는 L1/L2/L3, 두 데이터 복원 checksum, 외부 검증, 총 RTO/RPO·수동 작업·비용, R2/AWS S3 최종 checksum, 정확한 종료 순서, 전 cleanup, 0 잔여 과금이 모두 있을 때만 가능하다. 누락·불일치·production/unknown 환경은 `PASS`가 될 수 없다.
