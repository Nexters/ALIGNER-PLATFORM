# 노드 장애와 CNPG 자동 전환 드릴

상태: **NOT EXECUTED**. 이 문서는 증빙 수집과 수동 승인 절차만 제공한다. VM 정지, cloud CLI/API 호출, `cordon`/`drain`은 구현하거나 실행하지 않는다.

## 사전 조건

다음 증빙을 같은 드릴 기록에 보관한다. 하나라도 없으면 중단한다.

1. #30 production gate의 최신 **PASS** 결과와 실행 시각
2. 최신 etcd snapshot의 시각·식별자(credential, bucket URL 제외)
3. PostgreSQL base backup과 WAL archive의 최신 성공 시각·식별자(credential 제외)
4. `aligner-db`의 현재 primary Pod/노드와 `-rw` Service endpoint
5. 모든 필수 Pod의 노드 배치와 Pending 0, 남은 두 노드의 수용 가능성
6. 운영 창, 담당자, rollback 담당자 및 관측 채널

```bash
kubectl -n aligner-data get cluster aligner-db -o jsonpath='{.status.currentPrimary}{"\n"}'
kubectl -n aligner-data get pod -o wide
kubectl get pods -A -o wide
kubectl get endpointslice -n aligner-data -l kubernetes.io/service-name=aligner-db-rw
```

## 고정 workload

승인된 운영자만 별도 터미널에서 아래 고정 probe를 시작하고 출력을 드릴 기록으로 저장한다. 이 스크립트는 `aligner-data/aligner-db`와 CNPG `status.currentPrimary`만 사용하며, 임시 테이블에 read/write를 수행한다. secret, password, connection URL을 받거나 출력하지 않는다.

```bash
python3 scripts/tests/postgresql-failover-workload.py --samples 300 --interval-seconds 1
```

쓰기 RTO는 마지막 성공 write부터 장애 뒤 첫 성공 write까지의 경과 시간이다. `-rw` Service 경로의 복구는 아래 관측과 함께 해당 workload의 첫 성공 write로 판정한다. 목표는 **60초 이하**다.

## 승인 후 수동 장애 단계

다음 네 항목을 기록자가 큰 소리로 확인하고, 명시적 승인과 일치할 때에만 가비아 콘솔에서 수동으로 진행한다. 이 저장소에는 그 정지 명령이 없다.

1. 승인 ID와 승인자
2. 환경 이름 (`production` 등)
3. 대상 VM의 정확한 ID와 표시 이름
4. 그 VM이 사전 기록한 CNPG primary Pod가 있는 노드인지

일치하지 않거나 승인 없이 진행할 수 없다. 실행 후 아래만 관측한다.

```bash
kubectl get pods -A -o wide --watch
kubectl get pods -A --field-selector=status.phase=Pending
kubectl -n aligner-data get cluster aligner-db -o yaml
kubectl -n aligner-data get pods -o wide --watch
kubectl -n aligner-data get endpointslice -l kubernetes.io/service-name=aligner-db-rw -o yaml
```

## 복구 판정과 결과

required Pod Pending은 0, CNPG `aligner-db`는 Ready instance 2개여야 한다. 복구 노드가 돌아온 뒤 새 standby가 생성되고 replica가 따라잡은 시각도 기록한다. RTO가 60초 초과하거나 자동 회복에 수동 개입이 필요하면 `FAIL`이다.

기록은 secret-free JSON만 사용한다. 초기 파일은 [node-failover-result.not-executed.json](evidence/node-failover-result.not-executed.json)이며 상태를 **NOT_EXECUTED**로 유지한다. 실제 결과는 Git이 아닌 승인된 incident evidence 위치에 저장한 뒤 검증한다.

```bash
python3 scripts/tests/validate-node-failover-result.py --result /approved/evidence/issue-31.json
```

실행 결과 구조:

```json
{"issue":31,"status":"PASS|FAIL","started_at_utc":"RFC3339 UTC","write_rto_seconds":0,"required_pods_pending":0,"cnpg_instances_ready":2,"manual_intervention":false}
```
