# 노드 교체와 K3s/Cilium 순차 업그레이드

상태: **NOT EXECUTED**. 이 문서는 변경 승인과 secret-free 증적 계약만 제공한다. 이 저장소에서는
K3s/Cilium upgrade, `cordon`/`drain`, 재시작을 실행하지 않는다. `latest` 채널이나 검증되지 않은
binary/chart 명령은 사용하지 않는다.

## 변경 전 승인 조건

1. source/target K3s binary와 Cilium Helm chart의 **exact pin** 및 두 공식 호환 근거를 기록한다.
   target Cilium은 target Kubernetes minor를 지원해야 한다. 현재 binary/chart은 source pin과 일치해야
   한다. 고정 정본은 [platform constraints](../architecture/platform-constraints.md)와 inventory다.
2. 최신 etcd snapshot, CNPG base backup/WAL archive, 현재 K3s binary/Cilium chart 확인이 모두 true여야
   한다. credential, token, snapshot 내용은 기록하지 않는다.
3. 세 노드는 `k3s-01`, `k3s-02`, `k3s-03` 순서로만 처리한다. 대상에 CNPG primary가 있으면 drain 전에
   primary가 아닌 노드로 switchover를 완료하고 기록한다.
4. 승인된 운영자가 한 노드만 cordon/drain/upgrade/uncordon 한다. 각 노드의 작업 후 다음 노드 전에
   세 노드 Ready, etcd healthy member 3, Cilium connectivity, 대표 사용자 요청을 모두 확인한다.

## 중단·복구

다음 하나라도 발생하면 즉시 다음 노드로 진행하지 않는다: quorum/API/Ready 실패, Cilium connectivity
실패, CNPG redundancy 또는 primary switchover 실패, 필수 Pod Pending, 사용자 오류 증가, 시간·CPU·memory
budget 초과. 해당 노드를 source binary와 source Cilium chart로 되돌리고 같은 health gate를 다시 통과시킨다.
모든 세 노드 완료 전 rollback을 실제로 증명하지 못하면 `PASS`가 될 수 없다.

## 증적 검증

초기 증적은 [k3s-cilium-upgrade-result.not-executed.json](evidence/k3s-cilium-upgrade-result.not-executed.json)이며
`NOT_EXECUTED` 그대로 유지한다. 실제 증적은 Git이 아닌 승인된 change/incident evidence 위치에 저장한다.

```bash
python3 scripts/validate_k3s_cilium_upgrade.py --result /approved/evidence/issue-34.json
```

`PASS`는 backup/current-pin check, source/target 공식 호환 근거, 순서가 고정된 3개 노드, 매 단계 quorum,
Ready/etcd/Cilium/user gate, CNPG primary 사전 switchover, rollback demonstration, 오류·시간·resource 변화
기록을 모두 요구한다. 이 중 하나라도 false, 누락, `latest`/unverified pin이면 거부한다.
