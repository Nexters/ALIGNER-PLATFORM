# ALIGNER-PLATFORM

<p align="center">
  <img src="https://img.shields.io/badge/Kubernetes-K3s_v1.36-326CE5?logo=kubernetes&logoColor=white" alt="K3s" />
  <img src="https://img.shields.io/badge/CNI-Cilium_v1.17-F58536?logo=cilium&logoColor=white" alt="Cilium" />
  <img src="https://img.shields.io/badge/Database-CloudNativePG_v16.8-336791?logo=postgresql&logoColor=white" alt="CloudNativePG" />
  <img src="https://img.shields.io/badge/GitOps-Argo_CD_v2.14-EF6C00?logo=argo&logoColor=white" alt="Argo CD" />
  <img src="https://img.shields.io/badge/Ingress-Traefik_Gateway_API-2496ED?logo=traefikproxy&logoColor=white" alt="Traefik" />
  <img src="https://img.shields.io/badge/Zero--Trust-Tailscale-24292E?logo=tailscale&logoColor=white" alt="Tailscale" />
  <img src="https://img.shields.io/badge/IaaS-Gabia_gCloud-0080FF" alt="Gabia" />
  <img src="https://img.shields.io/badge/CLI-Go_1.26-00ADD8?logo=go&logoColor=white" alt="Go" />
  <img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License" />
</p>

**ALIGNER-PLATFORM**은 실사용자를 대상으로 9개월간 운영되는 3-노드 고가용(HA) Kubernetes 플랫폼의 **단일 진실 공급원(SSOT, Single Source of Truth)** 저장소입니다.

가비아 gCloud IaaS 프로비저닝(**L1 gabiactl**)부터 OS/스토리지 튜닝 및 K3s 클러스터 부트스트랩(**L2 Ansible**), 선언적 GitOps 배포 및 자가 치유(**L3 Argo CD**)까지 모든 인프라스트럭처를 코드로 관리(IaC / GitOps)합니다.

---

## 🏛️ System Architecture

### 01 · Production Runtime & High Availability
> 사용자 트래픽 인그레스, 워크로드 배치, 읽기/쓰기 복제 분기 라우팅 및 단일 노드 장애 대응 아키텍처

<p align="center">
  <img width="1948" height="1320" alt="Production Runtime & High Availability" src="https://github.com/user-attachments/assets/6326c2b7-a214-483e-ab67-47e403430eab" />
</p>

---

### 02 · Platform Lifecycle, Private Management & GitOps
> 3계층 수명주기, Zero-Trust 보안 관리망 및 GitOps Sync Waves 흐름

<p align="center">
  <img width="1920" height="1008" alt="Platform Lifecycle, Private Management & GitOps" src="https://github.com/user-attachments/assets/e0b09e0d-b81d-43c9-89c3-11e884d3a598" />
</p>

---

## 📐 3-Tier Layered Architecture

| 계층 | 도구 및 기술 | 주요 역할 및 기술 명세 | 핸드오프 산출물 |
| :--- | :--- | :--- | :--- |
| **`L1` IaaS** | `gabiactl` (Go 1.26) | • 가비아 gCloud Gen2 REST API 기반 자원 프로비저닝<br>• VPC (`10.20.0.0/16`), Subnet (`10.20.0.0/24`), Public IP, SG, L4 LB<br>• VM 3대 (4 vCPU / 8GB RAM / 50GB OS SSD)<br>• VM당 필수 2개 독립 블록 디스크 (Data-A: 25GB / Data-B: 40GB) | `.runtime/bootstrap-inventory.yaml` |
| **`L2` OS & Mesh** | `Ansible` 2.18 | • Ubuntu 24.04 커널 파라미터 튜닝, LVM 포맷 및 마운트 가드 (`/mnt/k3s`, `/mnt/aligner`)<br>• UFW 방화벽 및 Tailscale 메시망 구축 (공인망 관리 포트 완전 차단)<br>• K3s 3-Node Embedded etcd 고가용 쿼럼 클러스터 구축 (`v1.36.3+k3s1`)<br>• Minimal Cilium CNI v1.17 (표준 NetworkPolicy 격리) | `.runtime/kubeconfig` |
| **`L3` GitOps** | `Argo CD` 2.14 | • App-of-Apps 패턴 기반 선언적 인프라 및 애플리케이션 자가 치유(Self-Healing)<br>• Traefik Gateway API DaemonSet + cert-manager Let's Encrypt TLS<br>• CloudNativePG PostgreSQL 16.8 HA 클러스터 (Primary/Standby/WAL)<br>• Out-of-band K8s Secret 주입 및 환경 분리 (`aligner` / `aligner-sandbox`) | GitOps Single Source of Truth |

---

## 🖥️ Cluster Topology & Workload Matrix

| 노드명 | 내부 사설 IP | 사양 & 로컬 스토리지 | 배치 워크로드 및 역할 |
| :--- | :---: | :--- | :--- |
| **`k3s-01`** | `10.20.0.194` | 4 vCPU / 8GB RAM<br>50GB OS + 25GB `/mnt/k3s` + 40GB `/mnt/aligner` | • Control Plane (etcd-01)<br>• **PostgreSQL 16.8 Primary** (`aligner-db-1`)<br>• `aligner-api` (Replica 1)<br>• `aligner-sandbox-api` (Dev)<br>• `aligner-redis` (256Mi Cache) |
| **`k3s-02`** | `10.20.0.219` | 4 vCPU / 8GB RAM<br>50GB OS + 25GB `/mnt/k3s` + 40GB `/mnt/aligner` | • Control Plane (etcd-02)<br>• **PostgreSQL 16.8 Standby** (`aligner-db-2`, Sync WAL)<br>• `aligner-api` (Replica 2)<br>• Argo CD Server & HA Redis<br>• **Tailscale Ingress** (`aligner-argocd-ui`) |
| **`k3s-03`** | `10.20.0.23` | 4 vCPU / 8GB RAM<br>50GB OS + 25GB `/mnt/k3s` + 40GB `/mnt/aligner` | • Control Plane (etcd-03)<br>• `aligner-api` (Replica 3)<br>• **Argo CD Application Controller**<br>• **CloudNativePG Controller** & Barman Backup Engine<br>• **Tailscale Operator** |

---

## 🌊 Declarative GitOps Sync Waves

Argo CD `Root Application`(`gitops/root.yaml`)을 통해 아래 순서(Wave)로 동기화됩니다:

```text
gitops/
├── root.yaml                                # Argo CD App-of-Apps Root
├── infrastructure/
│   ├── controllers/                         # [Wave 0] 핵심 플랫폼 컨트롤러
│   │   ├── cert-manager/                    # ACME Let's Encrypt 인증서 발급
│   │   ├── traefik/                         # Gateway API v1 인그레스 컨트롤러
│   │   ├── cnpg/                            # CloudNativePG 16.8 오퍼레이터
│   │   ├── alloy/                           # Grafana Alloy 원격 텔레메트리
│   │   └── tailscale/                       # Tailscale Kubernetes 오퍼레이터
│   └── configs/                             # [Wave 1] 인프라 기본 설정 리소스
│       ├── gateway/                         # Gateway & HTTPRoute 라우팅 정의
│       ├── certificates/                    # ClusterIssuer & 도메인 인증서
│       └── databases/                       # CloudNativePG Cluster CR (aligner-db)
├── data/                                    # [Wave 2] 상태 저장 데이터 스토어
│   ├── postgresql/                          # PostgreSQL 부가 리소스
│   └── redis/                               # Redis LRU In-Memory 캐시
└── apps/                                    # [Wave 3] 비즈니스 애플리케이션
    ├── aligner-api/                         # 운영 환경 (api.aligneryoga.com, 3-Pod HA)
    └── aligner-sandbox-api/                 # 개발/테스트 환경 (test.aligneryoga.com)
```

---

## 🛡️ Zero-Trust Security & Disaster Recovery

### 1. 보안 격리 (Zero-Trust Network)
* **공인망 완전 차단**: SSH(`22`), K8s API(`6443`), DB(`5432`), Redis(`6379`) 포트는 공인 인터넷에서 100% 닫혀 있으며, Gabia Security Group 및 UFW 방화벽으로 보호됩니다.
* **Tailscale 사설망**: 엔지니어 및 CI/CD 파이프라인은 Tailscale 노드를 통해서만 클러스터 API 및 Argo CD UI에 접근할 수 있습니다.
* **Native Secret Injection**: 시크릿은 Git 저장소에 커밋되지 않으며, `runtime-secret.keys` 템플릿 계약에 따라 Out-of-band로 K8s Secret에 안전하게 주입됩니다.

### 2. 고가용성 및 재해 복구 (HA & DR)
* **단일 노드 무중단 장애 대응**: 3대 중 임의의 1개 노드가 완전히 정전되더라도 etcd 쿼럼 유지, API 2개 레플리카 가동 유지, Standby DB 자동 승격(Failover)이 사람의 개입 없이 즉시 일어납니다.
* **PostgreSQL RPO < 5분 / RTO < 1시간**: CloudNativePG Barman Cloud 엔진이 실시간 트랜잭션 WAL 로그를 Backblaze B2 S3 버킷으로 스트리밍 아카이빙하며, 주 1회 전체 물리 백업을 수행합니다.
* **etcd 자동 스냅샷**: 매 6시간마다 etcd 스냅샷이 Backblaze B2에 백업되어 최악의 재해 발생 시에도 10분 내 클러스터 복원이 가능합니다.

---

## 🚀 Operations Quick Start

### 필수 요구사항
* `go` >= 1.26
* `ansible-core` >= 2.18 (`ansible-lint`, `yamllint`, `shellcheck`)
* `kubectl` >= 1.30 & `kustomize`
* `tailscale` CLI

### 주요 운영 명령어

```bash
# 1. Ansible 필수 Collection 설치
make collections

# 2. L3 Kustomize Overlay 렌더링 및 YAML 문법 검증
make render

# 3. KubeDiagrams 엔진을 통한 아키텍처 다이어그램 최신화 (PNG, SVG, Draw.io)
make diagram

# 4. 인프라 전체 검증 테스트 스위트 실행
make test

# 5. 로컬에서 개발 DB 직접 터널링 접속 (Tailscale 활성화 상태)
kubectl --kubeconfig .runtime/kubeconfig port-forward -n aligner-data svc/aligner-db-rw 5432:5432
```

---

## 📚 Core Documentation

* 📖 [아키텍처 정본 (Architecture Overview v8)](docs/architecture/overview.md)
* 🔌 [가비아 Gen2 REST API 계약 명세](docs/architecture/gabia-gen2-api-contract.md)
* 🗺️ [구축 및 운영 로드맵 & SRE 훈련](docs/roadmap.md)
* 📝 [아키텍처 결정 기록 (ADR Index)](docs/adr/)
* 🛠️ [운영 및 장애 대응 런북 (Operations Runbooks)](docs/runbooks/)
