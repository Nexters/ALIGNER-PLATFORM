# PostgreSQL failover와 PITR

## Node-loss failover

1. primary가 위치한 VM을 확인한다.
2. 가비아 콘솔에서 해당 VM을 강제 정지한다.
3. CNPG 상태와 새 primary 선출을 관찰한다.
4. 애플리케이션 쓰기 재개 시간을 기록한다.
5. 장애 노드 복구 후 standby가 30분 안에 재구성되는지 확인한다.

합격 기준은 Write RTO 60초 이내이며, 애플리케이션은 `-rw` Service를 사용해야 한다.

## PITR

운영 Cluster를 덮어쓰지 않고 별도 이름의 CNPG Cluster로 복구한다.

실행 전 [PITR 증적 계약](evidence/postgresql-pitr-result.not-executed.json)을 `python3 scripts/validate_postgresql_pitr.py --result <evidence.json>`로 검증한다. `PASS`는 운영 Cluster·namespace·PVC와 모두 다른 복구 대상을 사용하고, WAL 연속성, R2 read-only restore credential, 기준 marker/row count/checksum과 복구 결과, RTO/RPO, 복구 Cluster·PVC·임시 credential 정리 증적이 모두 있어야 한다.

1. 복구 목표 시각과 그 전후의 검증 데이터를 기록한다.
2. R2 restore 전용 credential을 오프클러스터 정본에서 가져온다.
3. base backup과 WAL로 목표 시각까지 복구한다.
4. 행 수, 최신 Session 시각, 핵심 데이터 checksum을 운영 기준과 비교한다.
5. RPO와 RTO를 기록한 뒤 복구 Cluster를 삭제한다.

PITR 성공 전에는 backup 구성을 완료로 처리하지 않는다.

## 배포 전 Gate

1. 세 노드 모두에서 `/mnt/aligner`가 Data-B UUID로 마운트되고
   `/usr/local/libexec/aligner-local-pv-data-b-guard`가 성공해야 한다.
2. `local-path-storage/local-path-config`의
   `storageClassConfigs.aligner-local-path`는 모든 노드에서 `/mnt/aligner`만
   허용해야 한다. 이 ConfigMap은 기존 K3s local-path 설정과 server-side merge로
   적용한다. `setup`은 UUID guard 성공 후 Data-B에 기록된 marker를 PVC 생성마다
   검사하므로 삭제하거나 기본 script로 되돌리지 않는다. 이 항목이 없으면
   `aligner-local-path` PVC는 생성하지 않는다.
3. `aligner-postgresql-app`과 `aligner-postgresql-r2-writer` Secret 이름이
   `aligner-data` namespace에 준비되었는지 확인한다. 값은 Git이나 출력에 기록하지 않는다.
4. R2 writer 정책은 bucket/object 생성·목록·읽기만 허용하고 DeleteObject 계열은
   명시적으로 거부해야 한다. 적용 후 별도 승인 절차로 WAL, weekly base backup,
   delete 거부와 PITR을 시험한다.

## Redis cache recovery

Redis는 `emptyDir` 캐시다. Pod 재생성으로 데이터가 사라지는 것은 정상이다. 별도 승인된
운영 창에서 Pod 재생성 후 API가 cache miss를 다시 채우고 정상 응답하는지 확인한다.
