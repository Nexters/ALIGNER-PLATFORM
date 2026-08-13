# ALIGNER 플랫폼 아키텍처 v8

## 목표와 제약

ALIGNER는 실사용자를 대상으로 9개월 운영하는 사이드 프로젝트다. 서버 운영자는 2명이며 카페·테더링 등 유동 IP 환경에서도 대응한다.

설계 목표는 다음 세 가지다.

1. 노드 한 대가 정지해도 사용자 서비스가 사람 개입 없이 회복한다.
2. 신규 구축에는 GA 표준을 사용하되, 사용하지 않는 고급 기능은 켜지 않는다.
3. 제품 운영보다 큰 플랫폼을 만들지 않는다. 자동화 투자 우선순위는 L2, L3, L1 순이다.

가비아 gCloud 크레딧 300만 원과 9개월 운영 기간을 비용 상한으로 둔다. 가비아의 물리 장애 도메인 분산이 확인되기 전까지 이 구성을 리전 장애를 견디는 HA로 표현하지 않는다.

## 최종 구성

```text
사용자
  │ HTTPS
  ▼
Gabia External LB
  │ NodePort 30443/30080
  ▼
Traefik ×3 ─ Gateway API HTTPRoute ─ ALIGNER API

운영자 노트북 A/B
  │ Tailscale + MagicDNS
  └─ k3s-01/02/03 직접
       └─ OpenSSH 22 / Kubernetes API 6443

k3s-01 ─┬─ K3s server + worker + embedded etcd
k3s-02 ─┼─ K3s server + worker + embedded etcd
k3s-03 ─┴─ K3s server + worker + embedded etcd

Cluster
  ├─ Cilium 최소 구성 + kube-proxy
  ├─ Argo CD
  ├─ Traefik + cert-manager + Gateway API
  ├─ Infisical Cloud + External Secrets Operator
  ├─ CloudNativePG primary + standby
  ├─ Redis emptyDir
  └─ Grafana Alloy → Grafana Cloud

Backup
  ├─ Cloudflare R2: etcd snapshot, PostgreSQL base backup/WAL
  └─ AWS S3: 월간 암호화 사본과 종료 시 최종 사본
```

## 노드와 스토리지

| 항목 | 결정 |
| --- | --- |
| 노드 | `2 vCPU / 8 GB` 동일 사양 3대 |
| 역할 | 세 노드 모두 server와 worker |
| datastore | embedded etcd 3멤버 |
| OS | Ubuntu 24.04 LTS, 검증한 이미지 ID 고정 |
| Root | 노드당 50GB |
| Data-A | 노드당 25GB, `/mnt/k3s` |
| Data-B | 노드당 40GB, `/mnt/aligner` |

Data-A와 Data-B 두 개의 독립 볼륨은 현재 storage role의 필수 계약이다. 가비아 sandbox에서
VM당 데이터 볼륨 두 개의 attach·재조회·detach가 확인되지 않으면 인프라 생성을 중단한다.
검증되지 않은 단일 볼륨 경로로 자동 전환하지 않는다.

필수 워크로드의 request 합계는 한 노드 장애 후 남은 두 노드 allocatable의 85% 이하여야 한다. 계산표가 아니라 실제 VM 한 대를 정지해 필수 Pod `Pending` 0을 확인해야 한다.

## 네트워크와 접근

### 사용자 트래픽

- External LB는 80/443만 수신한다.
- 443은 Traefik NodePort 30443, 80은 30080으로 전달한다.
- Traefik은 노드마다 하나씩 배치한다.
- 라우팅 정본은 Gateway API Standard Channel의 `Gateway`와 `HTTPRoute`다.
- Traefik 전용 `IngressRoute`는 사용하지 않는다.

### 관리 트래픽

- Tailscale Personal의 `tag:aligner-prod`로 세 노드를 등록하고 MagicDNS로 직접 접근한다.
- admin만 태그된 서버의 OpenSSH 22/TCP와 Kubernetes API 6443/TCP에 접근한다.
- Tailscale SSH는 끄고 기존 SSH key를 사용한다.
- 공인망에서 22, 6443, Argo CD UI, 5432, 6379를 차단한다.
- 운영자·장비·노드 변경 시 tailnet membership을 즉시 폐기한다.
- break-glass 절차는 [관리 접근 Runbook](../runbooks/management-access.md)과 [비상 접근 Runbook](../runbooks/break-glass.md)을 따른다.

## 플랫폼 표준

### K3s와 Cilium

- K3s 버전은 stable 채널을 검증한 뒤 명시적으로 고정한다.
- Cilium은 Day 1에 설치하고 K3s 기본 Flannel과 내장 NetworkPolicy controller를 끈다.
- `kubeProxyReplacement: false`로 kube-proxy를 유지한다.
- 표준 `NetworkPolicy`를 기본으로 사용한다.
- Cilium L7/FQDN 정책, 노드 투명 암호화, Hubble Relay/UI는 도입하지 않는다.
- DNS/drop/policy 메트릭만 필요한 범위에서 활성화한다.
- 프로덕션 데이터 투입 전 connectivity, 정책, 노드 장애, 자원 Gate를 통과하지 못하면 Flannel로 재생성한다. 운영 중 CNI를 교체하지 않는다.

### Gateway API와 GitOps

- Traefik은 Argo CD가 관리한다. K3s 번들 Traefik은 비활성화한다.
- Gateway API는 GA인 Standard Channel 리소스만 사용한다.
- 플랫폼은 `GatewayClass`와 `Gateway`, 앱은 `HTTPRoute`를 소유한다.
- Argo CD root application 하나가 인프라 controller/config와 앱을 동기화한다.
- 실험 기능과 구현체 전용 CRD는 실제 요구가 생기기 전까지 추가하지 않는다.

### 데이터와 시크릿

- CloudNativePG `instances: 2`로 primary와 standby를 서로 다른 노드에 배치한다.
- 기본 연결은 `-rw` Service다. 명시적으로 stale read를 허용한 조회만 `-ro`를 사용한다.
- Redis는 재생성 가능한 캐시이며 `emptyDir`를 사용한다.
- Infisical은 `aligner-infra`와 `aligner-runtime` Project로 나눈다.
- ESO identity는 `aligner-runtime`에만 가입한다.
- K3s Secret encryption을 활성화하고 server 세 대의 encryption hash 일치를 확인한다.

### 관측과 백업

- Alloy는 필요한 메트릭과 로그만 Grafana Cloud로 전송한다.
- 라벨 카디널리티와 무료 티어 사용량을 경보로 관리한다.
- etcd snapshot은 6시간마다 R2에 저장한다.
- PostgreSQL은 연속 WAL archive와 주간 base backup을 R2에 저장한다.
- R2 writer에는 삭제 권한을 주지 않고 보존 정책을 적용한다.
- 월 1회 R2 백업의 암호화 사본을 AWS S3에 복제한다.
- 백업 성공 로그는 복구 증거가 아니다. 복구 시험은 [로드맵](../roadmap.md)의 Gate를 따른다.

## 자동화 경계

```text
L1  gabiactl
    Network, Subnet, Router, SG, VM, Volume, Public IP, LB
        ↓ .runtime/inventory.yaml
L2  Ansible
    OS, storage, Tailscale, firewall, K3s, Cilium bootstrap
        ↓ kubeconfig
L3  Argo CD
    controller, config, database, application
```

`gabiactl`은 구축용 얇은 CLI다. Terraform Provider, 범용 SDK, import, remote state, 완전한 plan/replace 엔진을 만들지 않는다. 세부 계약은 [ADR 0005](../adr/0005-thin-gabiactl.md)를 따른다.

최초에는 운영자 현재 IP의 `/32` SSH를 세 대에 임시 허용하고 public inventory로
Tailscale을 설치한다. 세 노드의 MagicDNS SSH를 검증한 후 Tailscale inventory로 전환하고
임시 SSH 규칙을 닫은 다음 전체 L2를 실행한다.

## 프로덕션 Gate

다음을 모두 통과하기 전에는 실사용자 트래픽을 받지 않는다.

- 3노드 Ready와 etcd 멤버 3개 확인
- Tailscale로 세 노드 SSH/API 접속과 break-glass 실사용
- 공인망 22/6443 차단 확인
- Cilium connectivity와 NetworkPolicy deny/allow 성공
- VM 한 대 강제 정지 후 필수 Pod Pending 0과 서비스 회복
- CNPG node-loss Write RTO 60초 이내
- R2 PostgreSQL PITR 성공과 데이터 정합성 확인
- etcd snapshot과 원본 K3s token으로 복구 성공
- Argo CD self-heal과 HTTPRoute TLS/host/path 검증
- 실제 자원 사용량으로 request/limit 갱신

`make verify`는 위 항목 중 자동으로 읽을 수 있는 상태만 검증한다. 결과는 Git 밖의
`.runtime/production-gate/<UTC timestamp>.json`에 남으며 Secret 또는 kubeconfig 내용은 기록하지
않는다. 현재 GitOps는 앱·Gateway runtime·Certificate runtime을 의도적으로 제외하므로, 해당
객체가 없어 production gate는 정상적으로 **FAIL** 한다. Cilium connectivity와 External LB health는
각각 `.runtime/cilium-gate/gate-summary.yml`과 Git 밖의 승인된 증적 참조가 있어야 한다.

## 정본과 기록

- 이 문서가 현행 아키텍처 정본이다.
- 결정 이유와 대안은 `docs/adr/`에 기록한다.
- 실행 명령은 `docs/runbooks/`에만 둔다.
- 일정과 DoD는 `docs/roadmap.md`에만 둔다.
- 이전 v7 설계는 `docs/archive/`에 보관하며 실행 기준으로 사용하지 않는다.
