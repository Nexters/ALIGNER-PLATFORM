# PostgreSQL failover와 PITR (Point-in-Time-Recovery)

## 1. Backblaze B2 원격 백업 아키텍처

CloudNativePG (CNPG)의 `barman-cloud` 엔진을 활용하여 Backblaze B2(S3-compatible)에 실시간 WAL 아카이빙 및 일일 풀(Base) 백업을 수행합니다.

* **S3 Endpoint**: `https://s3.<B2_REGION>.backblazeb2.com` (예: `us-west-004`)
* **Bucket Prefix**: `s3://aligner-prod-backup/cnpg/`
* **아카이빙 주기**: `archive_timeout: "300s"` (최대 5분 단위 강제 WAL flush, RPO < 5분 보장)
* **스케줄 백업**: 매일 19:00 UTC (04:00 KST) 일일 풀 백업 (`ScheduledBackup`)
* **보존 정책**: `retentionPolicy: "30d"` (30일 경과 데이터 자동 정리)

---

## 2. B2 자격증명 관리 (Secret Injection)

운영 보안을 위해 **Writer 키**와 **Reader 키**를 철저히 분리합니다.

### Writer Secret (`aligner-postgresql-b2-writer`)
운영 DB의 WAL 업로드 및 백업 전용 (B2 `cnpg/` prefix 쓰기/생성 권한):

```bash
kubectl create secret generic aligner-postgresql-b2-writer \
  -n aligner-data \
  --from-literal=ACCESS_KEY_ID="<B2_APPLICATION_KEY_ID>" \
  --from-literal=ACCESS_SECRET_KEY="<B2_APPLICATION_KEY>"
```

### Reader Secret (`aligner-postgresql-b2-reader`)
PITR 복구 검증 전용 (B2 `cnpg/` prefix 읽기 전용 권한):

```bash
kubectl create secret generic aligner-postgresql-b2-reader \
  -n aligner-data \
  --from-literal=ACCESS_KEY_ID="<B2_READONLY_KEY_ID>" \
  --from-literal=ACCESS_SECRET_KEY="<B2_READONLY_KEY>"
```

---

## 3. Node-loss Failover 드릴

1. primary가 위치한 VM을 확인한다 (`kubectl get cluster aligner-db -n aligner-data`).
2. 가비아 콘솔에서 해당 VM을 강제 정지한다.
3. CNPG 상태와 새 primary 선출을 관찰한다 (`kubectl get pods -n aligner-data -w`).
4. 애플리케이션 쓰기 재개 시간을 기록한다.
5. 장애 노드 복구 후 standby가 30분 안에 재구성되는지 확인한다.

* **합격 기준**: Write RTO 60초 이내, 애플리케이션 `-rw` Service 정상 연결.

---

## 4. PITR (Point-In-Time-Recovery) 시점 복구 절차

운영 Cluster를 절대 덮어쓰지 않고, 별도 이름의 격리 복구 클러스터(`aligner-db-recovery`)로 목표 시점까지 복원합니다.

### 1단계: 복구 목표 시각(UTC) 선정 및 기준 데이터 확인
```bash
# 운영 DB에서 현재 최신 데이터 marker/row count 확인
kubectl exec -it aligner-db-1 -n aligner-data -c postgres -- psql -U aligner_prod_user -d aligner_prod -c "SELECT count(*) FROM training.session;"
```

### 2단계: 복구 클러스터 매니페스트 적용
`gitops/infrastructure/configs/databases/recovery-cluster.template.yaml`를 복사하여 `TARGET_TIME`을 지정한 후 배포합니다:

```bash
export TARGET_TIME="2026-08-19 10:00:00.000000+00"
envsubst < gitops/infrastructure/configs/databases/recovery-cluster.template.yaml | kubectl apply -f -
```

### 3단계: 복구 완료 관찰 및 데이터 정합성 검증
```bash
# 복구 클러스터 준비 완료 확인
kubectl get cluster aligner-db-recovery -n aligner-data -w

# 복구 클러스터 데이터 행 수 및 checksum 비교
kubectl exec -it aligner-db-recovery-1 -n aligner-data -c postgres -- psql -U aligner_prod_user -d aligner_prod -c "SELECT count(*) FROM training.session;"
```

### 4단계: 복구 클러스터 정리 및 증적 검증
```bash
# 복구 클러스터 및 PVC 삭제
kubectl delete cluster aligner-db-recovery -n aligner-data

# PITR 증적 스크립트 검증
python3 scripts/validate_postgresql_pitr.py --result /path/to/evidence.json
```

---

## 5. Redis Cache Recovery

Redis는 `emptyDir` 캐시다. Pod 재생성으로 데이터가 사라지는 것은 정상이며, 재기동 후 애플리케이션이 cache miss를 정상적으로 재적재하는지 확인한다.
