# 0006. Cilium 최소 구성과 Gateway API

## 상태

Accepted with Gate

## 결정

- CNI는 Cilium을 Day 1에 설치한다.
- kube-proxy를 유지하고 표준 `NetworkPolicy`를 기본으로 사용한다.
- Hubble Relay/UI, L7/FQDN 정책, 노드 투명 암호화는 사용하지 않는다.
- 외부 HTTP 라우팅은 Traefik이 구현하고 GA `Gateway`와 `HTTPRoute`를 정본으로 사용한다.

## Gate

프로덕션 데이터 투입 전 `make verify-cilium`으로 status, 공식 connectivity, DNS/Service,
정책 deny/allow, 노드별 agent 재시작, RSS/CPU/metric series를 기록해야 한다. VM 한 대
정지는 외부 파괴 작업이므로 자동화하지 않는다. [Cilium Gate runbook](../runbooks/cilium-gate.md)의
수동 증적이 승인되기 전에는 Gate가 FAIL이다. 어느 하나라도 실패하면 프로덕션 데이터 투입을
막고, 운영 중 CNI 교체 대신 Flannel로 **클러스터를 재생성**할지 ADR을 갱신해 결정한다.

### Gate record

| Check | Pass evidence | Fail disposition |
| --- | --- | --- |
| Runtime pin | `gate-summary.yml`의 chart `cilium-1.20.0`, CLI version | data blocked; do not upgrade/swap CNI |
| Status/connectivity/DNS/Service/policy | playbook output and `gate-summary.yml` | data blocked; diagnose then rerun |
| Agent restart/resources | per-node restart list, CPU/memory, RSS/series | data blocked; capacity/remediation review |
| VM stop | approved runbook evidence reference | data blocked; Flannel rebuild decision required |

## 근거

Gateway API는 신규 구축의 이식 가능한 GA 표준이다. Cilium은 신규 클러스터에서 도입 비용이 가장 낮고 네트워크 정책과 drop/flow 진단을 제공한다. 사용하지 않는 고급 기능을 끄고 실제 자원 Gate로 채택을 확정한다.
