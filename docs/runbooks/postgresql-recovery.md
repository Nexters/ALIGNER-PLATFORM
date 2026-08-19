# PostgreSQL Failover 및 PITR (Point-in-Time-Recovery) Runbook

## 1. Backblaze B2 원격 백업 아키텍처 (Barman Cloud Plugin v0.14.0)

CloudNativePG (CNPG) v1.30.0과 **Barman Cloud Plugin v0.14.0**을 활용하여 Backblaze B2(S3-compatible API)에 실시간 WAL 연속 아카이빙 및 일일 풀(Base) 백업 체계를 구축합니다. (AWS S3 종속성 전면 배제)

* **S3 Endpoint**: `https://s3.<B2_REGION>.backblazeb2.com` (예: `us-west-004`)
* **Bucket & Prefix**: `s3://aligner-prod-backup/cnpg/`
* **ObjectStore CRD**: `barmancloud.cnpg.io/v1 ObjectStore` (`aligner-b2-backup`)
* **WAL 아카이빙 주기**: `archive_timeout: "300s"` 강제 flush 기반 **RPO < 5분 설계 목표** 달성
* **스케줄 백업**: 매일 19:00 UTC (04:00 KST) 일일 풀 백업 (`ScheduledBackup.spec.method: plugin`)
* **보존 정책**: `retentionPolicy: "30d"` (30일 경과 백업/WAL 자동 라이프사이클 정리)

---

## 2. B2 IAM 자격증명 및 권한 계약 (Least-Privilege Security)

운영 보안 및 재해 복구(DR) 신뢰성을 위해 **Writer 키**와 **Reader 키**를 엄격히 분리합니다.

| 시크릿 이름 | 대상 역할 | 버킷 및 프리픽스 범위 | 필수 B2 IAM 권한 | 비고 |
| :--- | :--- | :--- | :--- | :--- |
| **`aligner-postgresql-b2-writer`** | 운영 Primary WAL 업로드 및 일일 풀 백업 | `aligner-prod-backup`<br>`cnpg/*` | `listFiles`<br>`readFiles`<br>`writeFiles`<br>`deleteFiles` | 30일 retention 만료 파일 정리를 위해 `deleteFiles` 필수 |
| **`aligner-postgresql-b2-reader`** | PITR 복구 드릴 및 재해 복구 검증 | `aligner-prod-backup`<br>`cnpg/*` | `listFiles`<br>`readFiles` | 운영 데이터 오염 방지 (`deleteFiles`/`writeFiles` 절대 금지, 드릴 후 폐기) |

### Kubernetes Secret 주입 예시 (Out-of-band, 0600 안전 멱등 주입)
```bash
# 1. Writer Secret (운영 네임스페이스)
(
  set -euo pipefail
  umask 077
  tmp=$(mktemp)
  trap 'rm -f "$tmp"' EXIT
  cat > "$tmp" <<EOF
ACCESS_KEY_ID=$B2_WRITER_KEY_ID
ACCESS_SECRET_KEY=$B2_WRITER_APPLICATION_KEY
EOF
  kubectl create secret generic aligner-postgresql-b2-writer \
    -n aligner-data \
    --from-env-file="$tmp" \
    --dry-run=client -o yaml | kubectl apply -f -
)

# 2. Reader Secret (격리 복구 네임스페이스 - 드릴 전 임시 생성)
(
  set -euo pipefail
  umask 077
  tmp=$(mktemp)
  trap 'rm -f "$tmp"' EXIT
  cat > "$tmp" <<EOF
ACCESS_KEY_ID=$B2_READER_KEY_ID
ACCESS_SECRET_KEY=$B2_READER_APPLICATION_KEY
EOF
  kubectl create secret generic aligner-postgresql-b2-reader \
    -n aligner-pitr-drill \
    --from-env-file="$tmp" \
    --dry-run=client -o yaml | kubectl apply -f -
)
```

---

## 3. Node-loss Failover 드릴

1. primary Pod 및 위치한 Node(VM)와 Internal IP를 확인한다:
   ```bash
   PRIMARY=$(kubectl get cluster aligner-db -n aligner-data -o jsonpath='{.status.currentPrimary}')
   PRIMARY_NODE=$(kubectl get pod "$PRIMARY" -n aligner-data -o jsonpath='{.spec.nodeName}')
   echo "Primary Pod : $PRIMARY"
   echo "Primary Node: $PRIMARY_NODE"
   kubectl get node "$PRIMARY_NODE" -o wide
   ```
2. 가비아 콘솔 또는 인프라 레벨에서 해당 VM(`PRIMARY_NODE`의 Internal IP 매핑 대상)을 강제 정지한다.
3. CNPG 클러스터 상태와 새 primary 선출을 관찰한다 (`kubectl get pods -n aligner-data -w`).
4. 애플리케이션 쓰기 재개 시간을 기록한다.
5. 장애 노드 복구 후 standby가 30분 안에 정상 재구성되는지 확인한다.

* **합격 기준**: Write RTO 60초 이내, 애플리케이션 `-rw` Service 정상 복구.

---

## 4. Gate B — 결정론적 7단계 운영 PITR (Point-In-Time-Recovery) 드릴 절차

운영 Cluster를 절대 덮어쓰지 않고, **별도 격리 네임스페이스(`aligner-pitr-drill`)의 복구 클러스터(`aligner-db-recovery`)**로 목표 시점까지 복원하여 시간 경계 정합성을 검증합니다.

```
[운영 DB: aligner-db]
   │
   ├── 1단계: Drill Table 생성, Marker A 삽입 & WAL flush ──► pitr_drill_marker 기준값(행 수 1, 체크섬) 기록
   │                                                             │
   │                                                             ├── 2단계: TARGET_TIME (PostgreSQL clock_timestamp()) 기록
   │                                                             │
   ├── 3단계: Marker B 커밋 ➔ WAL switch ➔ TARGET_WAL B2 아카이브 대기 ─► (T > TARGET_TIME)
   │
   └── (B2 s3://aligner-prod-backup/cnpg/ 아카이빙)
                                                                 │
                                                                 ▼
[복구 DB: aligner-db-recovery (aligner-pitr-drill)]
   │
   ├── 4단계: StorageClass, Reader Secret, Recovery ObjectStore 및 Cluster 기동
   │
   ├── 5단계: 결정론적 정합성 검증:
   │         ├── Marker A: 존재 확인 (1건 -> Pass)
   │         ├── Marker B: 부재 확인 (0건 -> Pass: 목표 시점 이후 데이터 미포함 증명)
   │         ├── 행 수 일치: 정확히 1건 (Pass)
   │         └── 테이블 Checksum: 1단계 기준 Checksum과 100% 일치 (Pass)
   │
   ├── 6단계: 복구 클러스터/PVC/네임스페이스 삭제, 운영 DB Marker 테이블 정리, B2 Reader Key 폐기
   │
   └── 7단계: python3 scripts/validate_postgresql_pitr.py 증적 검증
```

### 1단계: 드릴 테이블 생성, 기준 Marker A 삽입 및 기준값 기록
```bash
# 1. Primary Pod 및 Node 동적 식별
PRIMARY=$(kubectl get cluster aligner-db -n aligner-data -o jsonpath='{.status.currentPrimary}')
PRIMARY_NODE=$(kubectl get pod "$PRIMARY" -n aligner-data -o jsonpath='{.spec.nodeName}')
echo "Target Primary: $PRIMARY on $PRIMARY_NODE"

# 2. 드릴 전용 테이블 생성 및 Marker A 삽입
kubectl exec -it "$PRIMARY" -n aligner-data -c postgres -- psql -U aligner_prod_user -d aligner_prod -c "
CREATE TABLE IF NOT EXISTS training.pitr_drill_marker (
    marker TEXT PRIMARY KEY,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO training.pitr_drill_marker (marker, note) VALUES ('drill-marker-A', 'baseline');
"

# 3. 기준 행 수 및 md5 체크섬 기록 (결정론적 검증 기준: training.pitr_drill_marker)
kubectl exec -it "$PRIMARY" -n aligner-data -c postgres -- psql -U aligner_prod_user -d aligner_prod -c "
SELECT count(*) FROM training.pitr_drill_marker;
SELECT md5(string_agg(marker, '' ORDER BY marker)) FROM training.pitr_drill_marker;
"

# 4. WAL 강제 flush
kubectl exec -it "$PRIMARY" -n aligner-data -c postgres -- psql -U aligner_prod_user -d aligner_prod -c "SELECT pg_switch_wal();"
```

### 2단계: 복구 목표 시각 ($T_{target}$) 기록 (PostgreSQL 시계 도메인 기준)
```bash
# 운영자 로컬 머신 시각 대신 PostgreSQL 서버의 시계에서 기준 시각을 획득
TARGET_TIME=$(kubectl exec "$PRIMARY" -n aligner-data -c postgres -- psql -U aligner_prod_user -d aligner_prod -Atc "SELECT clock_timestamp();")
export TARGET_TIME
echo "Recovery Target Time (PostgreSQL Clock): $TARGET_TIME"
```

### 3단계: 경계 검증용 Marker B 커밋 및 TARGET_WAL 아카이브 완료 대기 (180초 타임아웃)
```bash
# 1. Marker B 커밋 (별도 트랜잭션으로 완료 보장)
kubectl exec -it "$PRIMARY" -n aligner-data -c postgres -- psql -U aligner_prod_user -d aligner_prod -c "
INSERT INTO training.pitr_drill_marker (marker, note) VALUES ('drill-marker-B', 'post-cutoff');
"

# 2. WAL segment 전환 및 정확한 대상 WAL 파일명 캡처
TARGET_WAL=$(kubectl exec "$PRIMARY" -n aligner-data -c postgres -- \
  psql -U aligner_prod_user -d aligner_prod -Atc \
  "SELECT pg_walfile_name(pg_switch_wal());")
echo "Waiting for WAL segment to be archived in Backblaze B2: $TARGET_WAL"

# 3. B2 원격 아카이빙 완료 폴링 대기 (180초 타임아웃)
deadline=$((SECONDS + 180))
while true; do
  LAST_ARCHIVED=$(kubectl exec "$PRIMARY" -n aligner-data -c postgres -- \
    psql -U aligner_prod_user -d aligner_prod -Atc \
    "SELECT last_archived_wal FROM pg_stat_archiver;")
  [[ "$LAST_ARCHIVED" >= "$TARGET_WAL" ]] && break
  if (( SECONDS >= deadline )); then
    echo "ERROR: WAL archive timeout for segment $TARGET_WAL (last_archived_wal: $LAST_ARCHIVED)" >&2
    exit 1
  fi
  sleep 2
done
echo "WAL segment $TARGET_WAL successfully archived to B2 (last_archived: $LAST_ARCHIVED)."
```

### 4단계: 격리 네임스페이스에 Recovery ObjectStore 및 복구 클러스터 기동
```bash
# 1. Gate A 전제조건: StorageClass 배포 (미배포 시)
kubectl apply -f gitops/data/postgresql/storage-class.yaml

# 2. 격리 네임스페이스 생성
kubectl create namespace aligner-pitr-drill --dry-run=client -o yaml | kubectl apply -f -

# 3. 안전하고 멱등한 임시 Reader B2 Secret 생성 (Process argv/shell history 노출 차단)
(
  set -euo pipefail
  umask 077
  tmp=$(mktemp)
  trap 'rm -f "$tmp"' EXIT
  cat > "$tmp" <<EOF
ACCESS_KEY_ID=$B2_READER_KEY_ID
ACCESS_SECRET_KEY=$B2_READER_APPLICATION_KEY
EOF
  kubectl create secret generic aligner-postgresql-b2-reader \
    -n aligner-pitr-drill \
    --from-env-file="$tmp" \
    --dry-run=client -o yaml | kubectl apply -f -
)

# 4. Recovery ObjectStore 배포
envsubst < gitops/data/postgresql/recovery-object-store.template.yaml | kubectl apply -f -

# 5. Recovery Cluster 배포 및 준비 관찰
envsubst < gitops/data/postgresql/recovery-cluster.template.yaml | kubectl apply -f -
kubectl get cluster aligner-db-recovery -n aligner-pitr-drill -w
```

### 5단계: 시간 경계 정합성 및 무결성 검증 (결정론적 기준)
```bash
# 1. Marker A 존재 확인 (반드시 1건)
kubectl exec -it aligner-db-recovery-1 -n aligner-pitr-drill -c postgres -- psql -U aligner_prod_user -d aligner_prod -c "SELECT count(*) FROM training.pitr_drill_marker WHERE marker = 'drill-marker-A';"

# 2. Marker B 부재 확인 (반드시 0건 -> TARGET_TIME 경계 이후 데이터가 복원되지 않았음을 증명)
kubectl exec -it aligner-db-recovery-1 -n aligner-pitr-drill -c postgres -- psql -U aligner_prod_user -d aligner_prod -c "SELECT count(*) FROM training.pitr_drill_marker WHERE marker = 'drill-marker-B';"

# 3. 복구 클러스터의 행 수(1건) 및 Checksum이 1단계 기준값과 100% 일치하는지 확인 (pitr_drill_marker 기준)
kubectl exec -it aligner-db-recovery-1 -n aligner-pitr-drill -c postgres -- psql -U aligner_prod_user -d aligner_prod -c "
SELECT count(*) FROM training.pitr_drill_marker;
SELECT md5(string_agg(marker, '' ORDER BY marker)) FROM training.pitr_drill_marker;
"
```

### 6단계: 복구 클러스터 정리 및 Reader 자격증명 폐기 (Sanitization)
```bash
# 1. 복구 클러스터 및 PVC 삭제
kubectl delete cluster aligner-db-recovery -n aligner-pitr-drill
kubectl delete pvc -l cnpg.io/cluster=aligner-db-recovery -n aligner-pitr-drill
kubectl delete namespace aligner-pitr-drill

# 2. 운영 DB의 드릴 임시 테이블 정리
kubectl exec -it "$PRIMARY" -n aligner-data -c postgres -- psql -U aligner_prod_user -d aligner_prod -c "DROP TABLE IF EXISTS training.pitr_drill_marker;"

# 3. Backblaze 콘솔 또는 API에서 드릴 전용 Reader Application Key 삭제/폐기 (restore_credential_revoked=true 보장)
```

### 7단계: PITR 증적 검증 스크립트 실행
```bash
python3 scripts/validate_postgresql_pitr.py --result /path/to/evidence.json
```

---

## 5. 배포 게이트 체계 (Deployment Gates Architecture)

순환 의존성(Chicken-and-Egg)을 방지하고 운영 DB 무중단 안전성을 보장하기 위해 2단계 Gate 프로세스를 준수합니다.

```
[Gate A: Sandbox B2 Acceptance]
   ├── 임시/Sandbox CNPG 클러스터 기동
   ├── B2 WAL 아카이빙 및 Base 백업 검증
   └── 격리 PITR 복구 성공 (PASS 증적 확보)
               │
               ▼ (PASS 통과 시)
[Production Backup Activation]
   ├── 운영 aligner-db에 Barman Plugin 0.14.0 연결
   └── 첫 일일 풀 백업 및 연속 WAL 스트리밍 확보
               │
               ▼
[Gate B: Production PITR Drill & Ownership Migration]
   ├── 운영 aligner-db 백업 기반으로 aligner-pitr-drill 복구 검증 (Section 4 수행)
   ├── RTO/RPO/체크섬 증적 승인 (Refs #81 -> Fixes #81 완료)
   └── gitops/infrastructure/configs/databases/aligner-db를 gitops/data/postgresql/aligner-db로 GitOps 소유권 단일화
```

### 5.1 Gate A — Sandbox B2 연동 및 사전 검증
* B2 버킷 및 Application Key 발급 후, Sandbox 환경에서 Barman Cloud Plugin의 WAL 업로드 및 Base 백업 생성을 선행 검증합니다.

### 5.2 Production Backup Activation (운영 백업 활성화)
* Gate A 통과 후, 운영 `aligner-db`에 Barman Cloud Plugin v0.14.0 설정을 연결하여 첫 일일 풀 백업과 실시간 WAL 아카이빙 스트리밍을 가동합니다.

### 5.3 Gate B — Production PITR Drill & 소유권 단일화
* 본 문서의 **Section 4 (7단계 PITR 드릴 절차)**를 수행하여 운영 백업 기반의 시간 경계 정합성 증적을 확보하고, `gitops/data/postgresql/`로 GitOps 소유권을 완전히 단일화합니다.

---

## 6. Redis Cache Recovery

Redis는 `emptyDir` 기반 임시 인메모리 캐시다. Pod 재생성으로 데이터가 소멸되는 것은 정상 동작이며, 재기동 후 애플리케이션이 cache miss를 감지하여 DB로부터 정상 재적재하는지 확인한다.
