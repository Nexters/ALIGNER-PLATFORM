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

실행 전 [PITR 증적 계약](evidence/postgresql-pitr-result.not-executed.json)을 `python3 scripts/validate_postgresql_pitr.py --result <evidence.json>`로 검증한다. `PASS`는 운영 Cluster·namespace·PVC와 모두 다른 복구 대상을 사용하고, WAL 연속성, B2 `cnpg/` read-only restore credential, 기준 marker/row count/checksum과 복구 결과, RTO/RPO, 복구 Cluster·PVC·임시 credential 정리 증적이 모두 있어야 한다.

1. 복구 목표 시각과 그 전후의 검증 데이터를 기록한다.
2. B2 `cnpg/` restore 전용 credential을 오프클러스터 정본에서 가져온다.
3. base backup과 WAL로 목표 시각까지 복구한다.
4. 행 수, 최신 Session 시각, 핵심 데이터 checksum을 운영 기준과 비교한다.
5. RPO와 RTO를 기록한 뒤 복구 Cluster를 삭제한다.

PITR 성공 전에는 backup 구성을 완료로 처리하지 않는다.

## 배포 전 Gate

`gitops/data`는 의도적으로 PostgreSQL subtree를 포함하지 않는다. 실제 B2 endpoint로
`object-store.yaml`의 placeholder를 런타임 렌더링하고 두 Secret의 존재를 확인한 뒤에만,
별도 승인 PR에서 `postgresql`을 상위 kustomization에 연결한다. placeholder 상태의
`gitops/data/postgresql`을 직접 apply하지 않는다.

1. 세 노드 모두에서 `/mnt/aligner`가 Data-B UUID로 마운트되고
   `/usr/local/libexec/aligner-local-pv-data-b-guard`가 성공해야 한다.
2. K3s `local-path-provisioner`의 기본 경로가 `/mnt/aligner`인지 확인한다.
   이 설정은 L2(Ansible/K3s)가 `default-local-storage-path`로 관리하며
   L3(ArgoCD)에서 변경하지 않는다. 확인 명령:
   `kubectl get cm local-path-config -n kube-system -o jsonpath='{.data.config\.json}'`
3. `aligner-local-path` StorageClass가 `rancher.io/local-path` provisioner를 사용하고
   `reclaimPolicy: Retain`, `nodePath: /mnt/aligner`인지 확인한다.
   이 StorageClass는 `gitops/data/postgresql/storage-class.yaml`에 정의되어
   PostgreSQL subtree 연결 시 함께 적용된다.
4. `aligner-postgresql-app`과 `aligner-postgresql-b2-writer` Secret 이름이
   `aligner-data` namespace에 준비되었는지 확인한다. 값은 Git이나 출력에 기록하지 않는다.
5. B2 writer 권한은 `cnpg/` prefix에만 제한한다. retention이 요구하는 list/delete 권한은
   별도 승인 절차에서 WAL, weekly base backup, retention, PITR과 함께 시험한다.

## Redis cache recovery

Redis는 `emptyDir` 캐시다. Pod 재생성으로 데이터가 사라지는 것은 정상이다. 별도 승인된
운영 창에서 Pod 재생성 후 API가 cache miss를 다시 채우고 정상 응답하는지 확인한다.
