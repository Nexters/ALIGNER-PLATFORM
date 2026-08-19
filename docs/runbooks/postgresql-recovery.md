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
| **`aligner-postgresql-b2-reader`** | PITR 복구 드릴 및 재해 복구 검증 | `aligner-prod-backup`<br>`cnpg/*` | `listFiles`<br>`readFiles` | 운영 데이터 오염 방지 (`deleteFiles`/`writeFiles` 절대 금지) |

### Kubernetes Secret 주입 예시 (Out-of-band)
```bash
# 1. Writer Secret (운영 네임스페이스)
kubectl create secret generic aligner-postgresql-b2-writer \
  -n aligner-data \
  --from-literal=ACCESS_KEY_ID="<B2_WRITER_KEY_ID>" \
  --from-literal=ACCESS_SECRET_KEY="<B2_WRITER_APPLICATION_KEY>"

# 2. Reader Secret (격리 복구 네임스페이스)
kubectl create secret generic aligner-postgresql-b2-reader \
  -n aligner-pitr-drill \
  --from-literal=ACCESS_KEY_ID="<B2_READER_KEY_ID>" \
  --from-literal=ACCESS_SECRET_KEY="<B2_READER_APPLICATION_KEY>"
```

---

## 3. Node-loss Failover 드릴

1. primary가 위치한 노드를 확인한다 (`kubectl get cluster aligner-db -n aligner-data`).
2. 가비아 콘솔 또는 인프라 레벨에서 해당 VM을 강제 정지한다.
3. CNPG 클러스터 상태와 새 primary 선출을 관찰한다 (`kubectl get pods -n aligner-data -w`).
4. 애플리케이션 쓰기 재개 시간을 기록한다.
5. 장애 노드 복구 후 standby가 30분 안에 정상 재구성되는지 확인한다.

* **합격 기준**: Write RTO 60초 이내, 애플리케이션 `-rw` Service 정상 복구.

---

## 4. 결정론적 7단계 PITR (Point-In-Time-Recovery) 드릴 절차

운영 Cluster를 절대 덮어쓰지 않고, **별도 격리 네임스페이스(`aligner-pitr-drill`)의 복구 클러스터(`aligner-db-recovery`)**로 목표 시점까지 복원하여 시간 경계 정합성을 검증합니다.

```
[운영 DB: aligner-db]
   │
   ├── 1단계: Marker A 삽입 & WAL flush ──► 기준 행 수 N_A, 체크섬 C_A 기록
   │                                         │
   │                                         ├── 2단계: TARGET_TIME (UTC) 기록
   │                                         │
   ├── 3단계: Marker B 삽입 & WAL flush ──► (T > TARGET_TIME)
   │
   └── (B2 s3://aligner-prod-backup/cnpg/ 아카이빙)
                                         │
                                         ▼
[복구 DB: aligner-db-recovery (aligner-pitr-drill)]
   │
   ├── 4단계: recoveryTarget.targetTime = TARGET_TIME 복구 클러스터 기동
   │
   ├── 5단계: 정합성 검증:
   │         ├── Marker A: 존재 확인 (Pass)
   │         ├── Marker B: 부재 확인 (Pass - 목표 시점 이후 데이터 미포함 증명)
   │         ├── 행 수 일치: 정확히 N_A (Pass)
   │         └── 테이블 Checksum: 정확히 C_A (Pass)
   │
   ├── 6단계: 복구 클러스터, PVC, 임시 자격증명 정리
   │
   └── 7단계: python3 scripts/validate_postgresql_pitr.py 증적 검증
```

### 1단계: 기준 Marker A 삽입 및 기준값 기록
```bash
# 운영 DB에 Marker A 삽입
kubectl exec -it aligner-db-1 -n aligner-data -c postgres -- psql -U aligner_prod_user -d aligner_prod -c "INSERT INTO training.audit_marker (marker, note) VALUES ('drill-marker-A', 'baseline');"

# 기준 행 수 및 md5 체크섬 확인
kubectl exec -it aligner-db-1 -n aligner-data -c postgres -- psql -U aligner_prod_user -d aligner_prod -c "SELECT count(*) FROM training.session; SELECT md5(string_agg(id::text, '')) FROM (SELECT id FROM training.session ORDER BY id) s;"

# WAL 즉시 아카이빙
kubectl exec -it aligner-db-1 -n aligner-data -c postgres -- psql -U aligner_prod_user -d aligner_prod -c "SELECT pg_switch_wal();"
```

### 2단계: 복구 목표 시각 ($T_{target}$) 기록
```bash
export TARGET_TIME=$(date -u +"%Y-%m-%d %H:%M:%S.000000+00")
echo "Recovery Target Time (UTC): $TARGET_TIME"
```

### 3단계: 경계 검증용 Marker B 삽입 (목표 시점 이후 데이터)
```bash
# TARGET_TIME 이후 Marker B 삽입
kubectl exec -it aligner-db-1 -n aligner-data -c postgres -- psql -U aligner_prod_user -d aligner_prod -c "INSERT INTO training.audit_marker (marker, note) VALUES ('drill-marker-B', 'post-cutoff');"
kubectl exec -it aligner-db-1 -n aligner-data -c postgres -- psql -U aligner_prod_user -d aligner_prod -c "SELECT pg_switch_wal();"
```

### 4단계: 격리 네임스페이스에 복구 클러스터 기동
```bash
kubectl create namespace aligner-pitr-drill --dry-run=client -o yaml | kubectl apply -f -
envsubst < gitops/data/postgresql/recovery-cluster.template.yaml | kubectl apply -f -
kubectl get cluster aligner-db-recovery -n aligner-pitr-drill -w
```

### 5단계: 시간 경계 정합성 및 무결성 검증
```bash
# Marker A 존재 확인 (반드시 1건)
kubectl exec -it aligner-db-recovery-1 -n aligner-pitr-drill -c postgres -- psql -U aligner_prod_user -d aligner_prod -c "SELECT count(*) FROM training.audit_marker WHERE marker = 'drill-marker-A';"

# Marker B 부재 확인 (반드시 0건 -> TARGET_TIME 경계 이후 데이터가 복원되지 않았음을 증명)
kubectl exec -it aligner-db-recovery-1 -n aligner-pitr-drill -c postgres -- psql -U aligner_prod_user -d aligner_prod -c "SELECT count(*) FROM training.audit_marker WHERE marker = 'drill-marker-B';"

# 행 수 및 md5 체크섬이 1단계 기준값과 100% 일치하는지 확인
kubectl exec -it aligner-db-recovery-1 -n aligner-pitr-drill -c postgres -- psql -U aligner_prod_user -d aligner_prod -c "SELECT count(*) FROM training.session; SELECT md5(string_agg(id::text, '')) FROM (SELECT id FROM training.session ORDER BY id) s;"
```

### 6단계: 복구 클러스터 정리 (Sanitization)
```bash
kubectl delete cluster aligner-db-recovery -n aligner-pitr-drill
kubectl delete pvc -l cnpg.io/cluster=aligner-db-recovery -n aligner-pitr-drill
kubectl delete namespace aligner-pitr-drill
```

### 7단계: PITR 증적 검증 스크립트 실행
```bash
python3 scripts/validate_postgresql_pitr.py --result /path/to/evidence.json
```

---

## 5. 배포 전 Gate (Repository Gate Principle)

1. `gitops/data`는 의도적으로 PostgreSQL subtree를 포함하지 않는다 (`gitops/data/kustomization.yaml`에서 runtime-gated).
2. 실제 B2 application key가 프로비저닝되고, `aligner-postgresql-b2-writer`와 `aligner-postgresql-b2-reader` Secret이 생성된 후에만,
3. 격리 네임스페이스에서 7단계 PITR 드릴 증적(`PASS`)을 확보한 뒤 승인 PR을 통해 `gitops/data/kustomization.yaml`에 `postgresql`을 활성화한다.
4. placeholder 상태의 매니페스트를 운영 kustomization에 직접 연결하지 않는다.

---

## 6. Redis Cache Recovery

Redis는 `emptyDir` 기반 임시 인메모리 캐시다. Pod 재생성으로 데이터가 소멸되는 것은 정상 동작이며, 재기동 후 애플리케이션이 cache miss를 감지하여 DB로부터 정상 재적재하는지 확인한다.
