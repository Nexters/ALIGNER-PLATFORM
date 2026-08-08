# 노드 교체와 순차 업그레이드

## 사전 조건

- 최신 etcd snapshot과 K3s token 확인
- PostgreSQL base backup/WAL archive 정상
- 필수 Pod가 남은 두 노드에 배치 가능한지 확인
- Argo CD sync와 Grafana Cloud 경보 정상

## 계획 작업

1. 대상 노드가 CNPG primary이면 switchover 후 진행한다.
2. 노드를 cordon하고 drain한다.
3. 한 노드만 업그레이드 또는 교체한다.
4. K3s와 Cilium이 정상화될 때까지 다음 노드를 건드리지 않는다.
5. 노드를 uncordon하고 필수 workload와 etcd member 상태를 확인한다.

```bash
kubectl cordon <node>
kubectl drain <node> --ignore-daemonsets --delete-emptydir-data
kubectl get nodes
kubectl get pods -A -o wide
kubectl uncordon <node>
```

## 중단 조건

- etcd quorum 또는 API readiness 실패
- 필수 Pod Pending
- CNPG redundancy 미복귀
- Cilium connectivity 실패
- 사용자 요청 오류율 증가

중단 조건이 발생하면 다음 노드로 진행하지 않고 해당 노드를 복구하거나 검증된 이전 버전으로 되돌린다.
