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

1. 복구 목표 시각과 그 전후의 검증 데이터를 기록한다.
2. R2 restore 전용 credential을 오프클러스터 정본에서 가져온다.
3. base backup과 WAL로 목표 시각까지 복구한다.
4. 행 수, 최신 Session 시각, 핵심 데이터 checksum을 운영 기준과 비교한다.
5. RPO와 RTO를 기록한 뒤 복구 Cluster를 삭제한다.

PITR 성공 전에는 backup 구성을 완료로 처리하지 않는다.
