# K3s etcd 복구 드릴

상태: **NOT EXECUTED**. 이 Runbook은 별도 격리 복구 환경에서만 사용하는 수동 절차와 증적 계약이다. 운영 환경을 대상으로 하지 않으며, 이 저장소에서 K3s 중지·`cluster-reset`·cloud/R2 조작 명령을 실행하지 않는다.

## 시작 전 중단 조건

다음 항목을 secret-free 드릴 기록에 준비한다. 누락 시 명령을 하나도 실행하지 않고 중단한다.

1. 가장 최근 R2 snapshot의 식별자, 생성 UTC 시각, 바이트 크기, SHA-256 checksum
2. **원본** K3s server token이 오프클러스터 보관소에 존재한다는 증적. token 값, 보관소 URL, credential은 기록하지 않는다.
3. 운영과 다른 이름·네트워크·VM을 사용하는 명시적 격리 복구 환경
4. 동일 K3s 버전과 server 설정, 승인 ID, 담당자·rollback 담당자
5. [PostgreSQL 복구 Runbook](postgresql-recovery.md)의 별도 복구 계획

초기 증적은 [etcd-recovery-result.not-executed.json](evidence/etcd-recovery-result.not-executed.json)이며 `NOT_EXECUTED` 그대로 유지한다. 실제 결과는 Git이 아닌 승인된 incident evidence 위치에 기록한다.

## 수동 승인 복구 순서

1. 기록자가 대상이 `production`이 아닌 격리 환경임을 확인한다.
2. 승인자가 첫 server의 K3s 중지와 `cluster-reset --cluster-reset-restore-path` 실행을 각각 명시적으로 승인한다. 승인된 운영자가 별도 터미널에서 수동으로 수행한다.
3. 첫 server의 API readiness와 etcd **단일 member(1)** 상태를 확인한다.
4. 나머지 두 server를 순서대로 한 대씩 재조인한다. 각 조인 뒤 상태를 기록하고 다음 server로 진행한다.
5. etcd member **3**, Kubernetes node **3**을 모두 확인한다.
6. namespace·CRD·Secret의 **개수만** 기록한다. Secret 이름·값·내용은 기록하지 않는다.
7. Argo CD root application이 Git 정본으로 reconcile됐음을 확인한다.
8. PostgreSQL은 이 복구와 별개로 [PostgreSQL 복구 Runbook](postgresql-recovery.md)에 따라 복구·검증한다.
9. GitOps 정합화 후 대표 사용자 요청이 성공하는지 확인한다.
10. 격리 복구 환경과 임시 credential을 정리하고, 실제 RPO·RTO·수동 작업을 기록한다.

## 증적 검증

`PASS`는 API/단일-member 확인 후 순차 두 server 조인, etcd 3/member·node 3, GitOps reconcile, 사용자 요청 성공, 정리 증적을 모두 요구한다. 복구 대상이 production이거나 원본 token의 오프클러스터 존재 증적이 없으면 거부한다.

```bash
python3 scripts/validate_etcd_recovery.py --result /approved/evidence/issue-33.json
```

실행 결과 구조(값은 예시이며 Secret·token 값은 절대 넣지 않는다):

```json
{
  "issue": 33,
  "status": "PASS|FAIL",
  "snapshot": {"r2_object": "redacted-id", "created_at_utc": "RFC3339 UTC", "size_bytes": 0, "checksum": "sha256:..."},
  "original_token_off_cluster_evidence": {"storage": "off-cluster", "present": true},
  "production_environment": "production",
  "recovery_environment": "isolated-drill",
  "first_server_restore": {"manual_approval": true, "k3s_stopped": true, "cluster_reset_restore_manual": true},
  "api_ready_after_first": true,
  "etcd_members_after_first": 1,
  "sequential_server_joins": ["server-02", "server-03"],
  "etcd_members": 3,
  "nodes": 3,
  "kubernetes_resource_counts": {"namespaces": 0, "crds": 0, "secrets": 0},
  "gitops_reconciled": true,
  "postgresql_restore_runbook": "docs/runbooks/postgresql-recovery.md",
  "user_request_succeeded": true,
  "rpo_seconds": 0,
  "rto_seconds": 0,
  "manual_actions": ["approved action"],
  "cleanup": {"recovery_environment_deleted": true, "temporary_credentials_revoked": true}
}
```
