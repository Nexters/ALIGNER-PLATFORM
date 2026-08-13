# ALIGNER 플랫폼 구축·운영 로드맵 v8

## 운영 원칙

- 비프로덕션 서비스는 착수 후 2주, 프로덕션 Gate는 4주 안에 통과하는 것을 목표로 한다.
- Provider 개발, Talos·Longhorn·Cilium 고급 기능 PoC는 일정에 포함하지 않는다.
- 실패 시험은 학습 횟수가 아니라 복구 능력을 증명하는 최소 횟수만 수행한다.
- Gate를 통과하지 못한 기능은 다음 단계의 선행 조건을 막는다.

## Phase 0 — 착수 전

### 확인

- 가비아 Gen2 API 자동화 허용 범위와 endpoint/payload 확인
- VM당 복수 볼륨 지원 여부 확인
- Gen2 웹 콘솔 또는 터미널 접속 지원 여부 확인
- 노드 물리 분산 또는 가용 영역 지원 여부 확인
- R2에서 K3s etcd-s3와 CNPG Barman을 각각 acceptance test
- Infisical 무료 플랜의 Project, Identity, 사용자 한도 확인

### 준비

- 실제 IP, credential, state, inventory의 Git 미추적 확인
- `aligner-infra`, `aligner-runtime` Infisical Project 구성
- K3s token 사전 생성과 오프클러스터 보관
- R2 writer/restore/delete 자격증명 분리
- `gabiactl` sandbox에서 create → 재실행 No changes → inventory → destroy 시험

### Gate

- 미확인 API를 추측해 구현하지 않는다.
- 웹 콘솔 미지원 시 임시 `/32` SSH break-glass 절차를 확정한다.
- R2 acceptance test 실패 시 프로덕션 백업 저장소를 AWS S3로 변경한다.

## 1주차 — L1과 관리 경로

1. `gabiactl apply`로 VPC, Subnet, Router, SG, VM 3대, Volume, Public IP, External LB를 생성한다.
2. 운영자 현재 `/32` SSH를 k3s-01·02·03에 임시 허용한다.
3. public bootstrap inventory로 Tailscale agent를 세 대에 배포한다.
4. MagicDNS로 세 노드의 SSH 접속을 확인한다.
5. Tailscale inventory로 전환하고 임시 SSH 규칙을 닫는다.
6. Tailscale 관리망을 통해 Data-A/B와 나머지 L2를 구성한다.
7. break-glass를 실제 사용하고 공인망 22/6443 차단을 확인한다.

### DoD

- `gabiactl status`가 필수 리소스와 연결 관계 일치를 보고
- Tailscale에서 세 노드 MagicDNS SSH 성공
- 공인망에서 22/6443 연결 실패
- break-glass로 k3s-03 접속 후 원상 복구 성공

## 2주차 — Kubernetes와 진입 경로

1. 첫 K3s server를 부트스트랩하고 나머지 두 server를 순차 조인한다.
2. Cilium 최소 구성을 설치한다.
3. Cilium connectivity와 NetworkPolicy deny/allow를 검증한다.
4. cert-manager, Traefik, Gateway API CRD, Argo CD를 설치한다.
5. root application과 ALIGNER 비프로덕션 HTTPRoute를 동기화한다.
6. External LB → Traefik → HTTPRoute → Service 경로를 검증한다.

### Cilium Gate

- connectivity test 성공
- 표준 NetworkPolicy deny/allow 성공
- cilium-agent 재시작 후 네트워크 회복
- cilium-agent 실제 RSS/CPU 기록
- 한 노드 정지 상태에서 필수 request가 두 노드 allocatable의 85% 이하

Gate 실패 시 프로덕션 데이터 투입 전에 Flannel로 클러스터를 재생성한다.

## 3주차 — 데이터·시크릿·관측

1. Infisical Project와 Identity 경계를 검증한다.
2. ESO, CloudNativePG, Redis, Alloy를 Argo CD로 배포한다.
3. CNPG primary/standby가 서로 다른 노드에 있는지 확인한다.
4. PostgreSQL WAL archive와 주간 base backup을 R2에 연결한다.
5. K3s etcd snapshot을 6시간 주기로 R2에 연결한다.
6. API, JVM, Kubernetes, Cilium, CNPG 핵심 경보를 구성한다.

### DoD

- ESO가 `aligner-infra`를 읽지 못함
- K3s encryption hash가 세 server에서 일치
- R2 writer가 객체를 삭제하지 못함
- WAL archive 실패와 etcd snapshot 실패 경보가 동작
- Grafana Cloud 사용량이 무료 티어 예산 안에 있음

## 4주차 — 프로덕션 Gate

1. 가비아 콘솔에서 노드 한 대를 강제 정지한다.
2. API와 Traefik의 자동 회복, 필수 Pod Pending 0을 확인한다.
3. CNPG primary 노드를 정지해 Write RTO와 standby 재생성을 측정한다.
4. 별도 CNPG Cluster로 PITR을 수행하고 데이터 정합성을 검사한다.
5. 별도 복구 환경에서 etcd snapshot과 K3s token으로 복구한다.
6. 롤링 배포 중 비정상 응답 수를 측정한다.
7. 추정 request/limit을 실측값으로 교체한다.

모든 Gate 통과 후에만 프로덕션 DNS를 전환한다.

## 2~8개월차 — 운영

### 상시 자동화

- 6시간 etcd snapshot
- 연속 WAL archive와 주간 base backup
- 월간 AWS S3 암호화 사본
- Grafana Cloud 경보
- Argo CD drift self-heal

### 정기 작업

- 월 1회: 백업 최신 시각, S3 체크섬, credential 만료 확인
- 분기 1회: PostgreSQL PITR 또는 etcd 복구를 번갈아 수행
- K3s/Cilium 업그레이드 전: snapshot과 rollback 경로 확인 후 한 노드씩 적용
- 팀원·장비 변경 시: Tailscale 사용자·device 폐기

## 9개월차 — 전체 재구축과 종료 결정

1. `gabiactl apply`로 별도 L1 환경을 재현한다.
2. Ansible로 Tailscale, K3s, Cilium을 구성한다.
3. Argo CD root application으로 플랫폼과 앱을 복원한다.
4. R2에서 PostgreSQL과 etcd를 복구한다.
5. External LB, DNS, TLS 경로를 검증한다.
6. 전체 RTO/RPO와 수동 개입을 기록한다.
7. 유료 지속, 타 클라우드 이전, 종료 중 하나를 결정한다.
8. 종료 시 최종 백업을 R2와 AWS S3에 보관한 뒤 의존성 역순으로 리소스를 삭제한다.

### 최종 DoD

- L1 → L2 → L3 전체 재구축 성공
- PostgreSQL과 etcd 복구 및 데이터 정합성 확인
- 최종 RTO/RPO 기록
- 백업 2개 공급자의 체크섬 확인
- 비용 실적과 다음 환경 결정 기록
