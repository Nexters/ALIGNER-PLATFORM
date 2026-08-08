# 전체 재구축과 종료

## 재구축

1. `gabiactl validate`와 `status`로 목표 정의와 기존 환경을 확인한다.
2. 별도 환경 이름으로 `gabiactl apply`를 실행한다.
3. `.runtime/inventory.yaml`을 생성한다.
4. Ansible로 storage, WireGuard, firewall, K3s, Cilium을 구성한다.
5. Argo CD root application을 부트스트랩한다.
6. K3s token과 etcd snapshot을 복원한다.
7. R2 base backup/WAL로 PostgreSQL을 복원한다.
8. External LB, DNS, TLS, HTTPRoute, 애플리케이션 쓰기를 검증한다.
9. 전체 RTO/RPO와 수동 개입을 기록한다.

## 종료

1. PostgreSQL logical dump, base backup/WAL, etcd snapshot, K3s token을 확보한다.
2. R2와 AWS S3 사본의 checksum과 보존 정책을 확인한다.
3. container image digest 목록과 복구에 필요한 버전을 기록한다.
4. `gabiactl destroy`의 대상과 순서를 dry-run으로 검토한다.
5. 서비스 DNS를 내린 뒤 LB → VM → Volume → Public IP → Network 순서로 제거한다.
6. credential을 폐기하고 최종 비용과 보존 만료일을 기록한다.

운영 환경을 대상으로 첫 destroy를 실행하지 않는다. 별도 재구축 환경의 create/destroy acceptance test를 먼저 통과해야 한다.
