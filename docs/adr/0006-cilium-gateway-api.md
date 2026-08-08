# 0006. Cilium 최소 구성과 Gateway API

## 상태

Accepted with Gate

## 결정

- CNI는 Cilium을 Day 1에 설치한다.
- kube-proxy를 유지하고 표준 `NetworkPolicy`를 기본으로 사용한다.
- Hubble Relay/UI, L7/FQDN 정책, 노드 투명 암호화는 사용하지 않는다.
- 외부 HTTP 라우팅은 Traefik이 구현하고 GA `Gateway`와 `HTTPRoute`를 정본으로 사용한다.

## Gate

프로덕션 데이터 투입 전 connectivity, 정책 deny/allow, cilium-agent 재시작, VM 한 대 장애, RSS/CPU 시험을 통과해야 한다. 실패하면 운영 중 교체하지 않고 Flannel로 클러스터를 재생성한다.

## 근거

Gateway API는 신규 구축의 이식 가능한 GA 표준이다. Cilium은 신규 클러스터에서 도입 비용이 가장 낮고 네트워크 정책과 drop/flow 진단을 제공한다. 사용하지 않는 고급 기능을 끄고 실제 자원 Gate로 채택을 확정한다.
