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
</p>

**ALIGNER-PLATFORM**은 실사용자 서비스 운영을 위한 3-Node K3s High Availability (HA) 플랫폼의 **Single Source of Truth (SSOT)** 저장소입니다.

가비아 gCloud IaaS 프로비저닝(**L1 gabiactl**)부터 OS/스토리지 튜닝 및 K3s 클러스터 부트스트랩(**L2 Ansible**), 선언적 GitOps 배포 및 Self-Healing(**L3 Argo CD**)까지 모든 인프라를 코드로 관리(IaC & GitOps)합니다.

---

## 🏛️ System Architecture

### 01 · Production Runtime & High Availability
> Ingress 트래픽 흐름, Workload 배치, Read/Write Replica Routing 및 Single-Node Failover 아키텍처

<p align="center">
  <img width="1948" height="1320" alt="Production Runtime & High Availability" src="https://github.com/user-attachments/assets/6326c2b7-a214-483e-ab67-47e403430eab" />
</p>

---

### 02 · Platform Lifecycle, Private Management & GitOps
> 3-Tier Lifecycle, Zero-Trust 보안 관리망 및 GitOps Sync Waves 흐름

<p align="center">
  <img width="1920" height="1008" alt="Platform Lifecycle, Private Management & GitOps" src="https://github.com/user-attachments/assets/e0b09e0d-b81d-43c9-89c3-11e884d3a598" />
</p>

---

## 📐 3-Tier Layered Architecture

| Tier | Tools & Stack | Key Responsibilities & Tech Specs | Handoff Artifacts |
| :--- | :--- | :--- | :--- |
| **`L1` IaaS** | `gabiactl` (Go 1.26) | • 가비아 gCloud Gen2 REST API 기반 IaaS 자원 프로비저닝<br>• VPC (`10.20.0.0/16`), Subnet (`10.20.0.0/24`), Public IP, SG, L4 External LB<br>• VM 3대 (4 vCPU / 8GB RAM / 50GB OS SSD)<br>• VM당 필수 2개 독립 블록 디스크 (Data-A: 25GB / Data-B: 40GB) | `.runtime/bootstrap-inventory.yaml` |
| **`L2` OS & Mesh** | `Ansible` 2.18 | • Ubuntu 24.04 커널 파라미터 튜닝, LVM Mount Guard (`/mnt/k3s`, `/mnt/aligner`)<br>• UFW 방화벽 및 Tailscale Private Mesh 구축 (공인망 관리 포트 완전 차단)<br>• K3s 3-Node Embedded etcd HA Cluster 구축 (`v1.36.3+k3s1`)<br>• Minimal Cilium CNI v1.17 (표준 NetworkPolicy 격리) | `.runtime/kubeconfig` |
| **`L3` GitOps** | `Argo CD` 2.14 | • App-of-Apps 패턴 기반 선언적 인프라 & Self-Healing Reconciliation<br>• Traefik Gateway API DaemonSet + cert-manager Let's Encrypt TLS<br>• CloudNativePG PostgreSQL 16.8 HA Cluster (Primary / Standby / Streaming WAL)<br>• Out-of-band Secret Injection 및 Multi-Namespace 격리 (`aligner` / `aligner-sandbox`) | GitOps SSOT |

---

## 🖥️ Cluster Topology & Workload Placement

| Node | Internal IP | Specs & Storage | Workloads & Placement Role |
| :--- | :---: | :--- | :--- |
| **`k3s-01`** | `10.20.0.194` | 4 vCPU / 8GB RAM<br>50GB OS + 25GB `/mnt/k3s` + 40GB `/mnt/aligner` | • Control Plane (etcd-01)<br>• **PostgreSQL 16.8 Primary** (`aligner-db-1`)<br>• `aligner-api` (Replica 1)<br>• `aligner-sandbox-api` (Dev)<br>• `aligner-redis` (256Mi Cache) |
| **`k3s-02`** | `10.20.0.219` | 4 vCPU / 8GB RAM<br>50GB OS + 25GB `/mnt/k3s` + 40GB `/mnt/aligner` | • Control Plane (etcd-02)<br>• **PostgreSQL 16.8 Standby** (`aligner-db-2`, Streaming WAL)<br>• `aligner-api` (Replica 2)<br>• Argo CD Server & HA Redis<br>• **Tailscale Ingress** (`aligner-argocd-ui`) |
| **`k3s-03`** | `10.20.0.23` | 4 vCPU / 8GB RAM<br>50GB OS + 25GB `/mnt/k3s` + 40GB `/mnt/aligner` | • Control Plane (etcd-03)<br>• `aligner-api` (Replica 3)<br>• **Argo CD Application Controller**<br>• **CloudNativePG Controller** & Barman Backup Engine<br>• **Tailscale Operator** (Failover Spare Node) |

---

## 🌊 Declarative GitOps Sync Waves

Argo CD `Root Application`(`gitops/root.yaml`)을 통해 아래 단계(Sync Wave) 순으로 Reconcile됩니다:

```text
gitops/
├── root.yaml                                # Argo CD App-of-Apps Root
├── infrastructure/
│   ├── controllers/                         # [Wave 0] Platform Controllers
│   │   ├── cert-manager/                    # ACME Let's Encrypt TLS Issuer
│   │   ├── traefik/                         # Gateway API v1 Ingress Controller
│   │   ├── cnpg/                            # CloudNativePG 16.8 Operator
│   │   ├── alloy/                           # Grafana Alloy Telemetry Agent
│   │   └── tailscale/                       # Tailscale Kubernetes Operator
│   └── configs/                             # [Wave 1] Infrastructure Configs
│       ├── gateway/                         # Gateway & HTTPRoute Ingress Rules
│       ├── certificates/                    # ClusterIssuer & Domain Certificates
│       └── databases/                       # CloudNativePG Cluster CR (aligner-db)
├── data/                                    # [Wave 2] Stateful Data Stores
│   ├── postgresql/                          # PostgreSQL Configuration
│   └── redis/                               # Redis LRU In-Memory Cache
└── apps/                                    # [Wave 3] Business Applications
    ├── aligner-api/                         # Production Environment (api.aligneryoga.com, 3-Pod HA)
    └── aligner-sandbox-api/                 # Dev/Sandbox Environment (dev-api.aligneryoga.com)
```

---

## 🛡️ Zero-Trust Security & Disaster Recovery

### 1. Zero-Trust Network Isolation
* **공인망 포트 완전 차단**: SSH(`22`), K8s API(`6443`), DB(`5432`), Redis(`6379`) 포트는 공인 인터넷에서 100% 차단(Blocked)되며, Gabia Security Group 및 UFW 방화벽으로 철저히 보호됩니다.
* **Tailscale Private Mesh**: 엔지니어 및 CI/CD 파이프라인은 Tailscale Mesh VPN을 통해서만 내부 K8s API 및 Argo CD UI에 안전하게 접근합니다.
* **Out-of-band Native Secret Injection**: 시크릿은 Git 저장소에 일체 저장되지 않으며, `runtime-secret.keys` 명세에 따라 Out-of-band 방식으로 클러스터에 직접 주입됩니다.

### 2. High Availability & Disaster Recovery (HA & DR)
* **Zero-Downtime Single-Node Failover**: 3대 중 임의의 1개 노드가 완전히 다운되더라도 etcd 쿼럼 유지, API 2개 Replica 가동 유지, Standby DB 자동 승격(Failover)이 무중단으로 수행됩니다.
* **PostgreSQL RPO < 5분 / RTO < 1시간**: CloudNativePG Barman Cloud 엔진이 트랜잭션 WAL 로그를 Backblaze B2 S3 버킷으로 실시간 Streaming Archiving하며, 주 1회 전체 물리 백업(BaseBackup)을 수행합니다.
* **Automated etcd Backup**: 6시간 주기로 etcd 스냅샷이 Backblaze B2에 자동 백업되어 재해 발생 시 클러스터 상태를 즉시 복원할 수 있습니다.

---

## 🚀 Operations Quick Start

### Prerequisites
* `go` >= 1.26
* `ansible-core` >= 2.18 (`ansible-lint`, `yamllint`, `shellcheck`)
* `kubectl` >= 1.30 & `kustomize`
* `tailscale` CLI

### Key Operations Commands

```bash
# 1. Ansible 필수 Collection 설치
make collections

# 2. L3 Kustomize Overlay 렌더링 및 YAML 문법 검증
make render

# 3. 인프라 전체 검증 테스트 스위트 실행
make test

# 4. 로컬에서 개발 DB 직접 터널링 접속 (Tailscale 활성화 상태)
kubectl --kubeconfig .runtime/kubeconfig port-forward -n aligner-data svc/aligner-db-rw 5432:5432
```

---

## 📚 Core Documentation

* 📖 [Architecture Overview (정본 v8)](docs/architecture/overview.md)
* 🔌 [Gabia Gen2 REST API Contract](docs/architecture/gabia-gen2-api-contract.md)
* 🗺️ [Roadmap & SRE Drills](docs/roadmap.md)
* 📝 [Architecture Decision Records (ADR Index)](docs/adr/)
* 🛠️ [Operations Runbooks](docs/runbooks/)
