# 0008. CNPG local-path와 외부 백업

## 상태

Accepted with Gate

## 결정

- CloudNativePG `instances: 2`를 서로 다른 노드의 local-path 볼륨에 배치한다.
- 비동기 복제와 `-rw` Service를 기본으로 사용한다.
- private Backblaze B2 버킷 하나에 `k3s-etcd/` 6시간 etcd snapshot과 `cnpg/` 연속 WAL·주간 base backup을 저장한다.
- K3s와 CNPG는 서로 다른 prefix-scoped application key를 사용한다. 보존에 필요한 list/delete 권한은 acceptance test로 확인한 뒤에만 부여한다.

## 한계

local-path는 노드에 고정된다. primary 노드 영구 유실 시 standby 승격은 자동이지만 복제본 재구성에는 시간이 필요하다. 두 번째 장애까지 겹치면 외부 백업으로 복구한다.

## Gate

- primary 노드 정지 후 Write RTO 60초 이내
- 별도 Cluster PITR과 데이터 정합성 확인
- 원본 K3s token을 사용한 etcd snapshot 복구
- B2 prefix별 writer 권한, 보존, 객체 checksum 확인
