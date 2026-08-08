# [보관됨] 가비아 gCloud 300만 원 크레딧 · 9개월 집중 운영 Kubernetes v7 설계안

> 이 문서는 과거 결정과 검토 이력을 보존하기 위한 읽기 전용 자료다.
> 현재 구축·운영의 정본은 `docs/architecture/overview.md`와 `docs/roadmap.md`다.
> 이 문서의 명령·체크리스트를 실행 기준으로 사용하지 않는다.

## 공개 저장소 운영 원칙

이 문서와 플랫폼 구현은 Public `Nexters/ALIGNER-PLATFORM` 저장소에서 관리한다.

Terraform·Ansible·Kubernetes manifest·네트워크 정책·장애 복구 절차는 **공개를 전제로** 작성한다.
보안은 아키텍처와 포트 구성을 숨기는 것에 의존하지 않고 **인증·최소 권한·방화벽·암호화·키 관리**로
보장한다.

다만 다음 정보는 **Public Git에 저장하지 않는다.**

```text
자격증명
- 가비아 ID·비밀번호·세션 토큰
- GitHub PAT · GitHub App Private Key
- R2 · AWS · Grafana Cloud Access Token
- Tailscale Auth Key
- WireGuard Private Key
- K3s server token
- kubeconfig client certificate · private key
- Infisical Machine Identity credential (ESO Bootstrap)

실행 결과와 상태
- Terraform state · plan
- 실제 terraform.tfvars · backend.hcl
- 클라우드 리소스 ID 가 포함된 generated inventory
- 로컬에서 가져온 kubeconfig
- 복구용 인증정보와 운영자 개인 연락처
```

민감값의 **정본은 Infisical Cloud 하나**다(§2.6). GitHub Actions는 **OIDC로 단기 토큰을 발급**받아
사용하며 **실제 값을 GitHub Secrets에 복제하지 않는다.** 팀 Password Manager는 일상 정본이 아니라
**Bootstrap·복구 예외 저장소**다 — ESO Bootstrap credential과 break-glass 복구 정보만 봉인 보관한다.
Terraform state는 AWS S3 Remote Backend에서 관리한다.

Public Git에 포함할 수 있는 범위는 다음이다.

```text
- Terraform 모듈과 변수 선언
- gabiactl 목표 상태 스키마
- Security Group 정책
- cloud-init · Ansible Playbook 과 Role
- K3s · Cilium 설정 템플릿
- Helm · Kustomize manifest
- normal / degraded / maintenance overlay
- ExternalSecret 정의 (Secret 참조만 — 값은 포함하지 않는다)
- 일반화된 장애 복구 Runbook
- 기술 선택과 트레이드오프를 담은 ADR
```

**`ExternalSecret` 매니페스트는 Public Git에 저장할 수 있다.** 값이 아니라 Infisical 경로 참조만
담기 때문이다. Infisical Machine Identity credential은 오프클러스터에 보관한다(§2.6.7).

```text
Public
├─ Nexters/ALIGNER-SERVER
│  └─ Kotlin/Spring Boot 애플리케이션
│
└─ Nexters/ALIGNER-PLATFORM
   └─ IaC · Ansible · K3s · GitOps · ADR · 일반화된 Runbook   ← 이 문서의 최종 위치

Private
└─ 이동훈/terraform-provider-gabiacloud
   └─ 가비아의 비공식 API 사용 허용 여부 확인 전까지 Private
```

> ⚠️ **Public 전환 전에 실제 값을 placeholder로 바꿔야 한다.** 현재 문서에는 실제 사설 IP
> (`{{ k3s_node_ips[0] }}~13`), 관리 게이트웨이로 지목된 노드, 구체적인 break-glass 대상이 들어 있다.
> **Phase 0의 ②③④가 이 작업이다.** 저장소 공개 여부와 시크릿 보관 여부는 별개 사안이며,
> 실제 운영 값은 Public 여부와 무관하게 Git 밖에서 주입한다.

> 대상: Aligner 서버(Kotlin 2.4.10 / JDK 25 / Spring Boot 4.1.0 / PostgreSQL / Spring Data JDBC)
> 전제: 총 크레딧 3,000,000원, 운영 9개월, 월 예산 약 330,000원(VAT 포함)
> 원본 12개월(월 25만 원) 설계안의 재편성 버전

## 요금 단가 근거

이 문서의 모든 금액은 **가비아 클라우드 공식 요금 계산기(`www.gabiacloud.com/service/estimate`)가
사용하는 실제 단가표**에서 추출한 값이다. 추측값이 아니다. 확인된 VPC(Gen2) 단가는 다음이다.

| 항목 | 단가 (VAT 별도) | 비고 |
| --- | --- | --- |
| micro `1vCPU/2GB` + Root SSD 50GB | 25,750원/월 | |
| high_cpu `2vCPU/4GB` + Root SSD 50GB | 60,750원/월 | 원본 설계안의 노드 |
| high_cpu `4vCPU/8GB` + Root SSD 50GB | 115,750원/월 | |
| **standard `2vCPU/8GB` + Root SSD 50GB** | **74,250원/월** | **본 설계안의 노드** |
| standard `4vCPU/16GB` + Root SSD 50GB | 142,750원/월 | |
| high_memory `2vCPU/16GB` + Root SSD 50GB | 95,750원/월 | |
| Root SSD 50GB → 100GB 변경 | +5,750원/월 | VM 요금에 Root SSD 포함 |
| 블록 스토리지 SSD(VPC) | 1,150원 / 10GB / 월 = **115원/GB** | 10GB 단위, 최소 10GB |
| External Load Balancer (Small) | 15,000원/월 | |
| **NAT 게이트웨이** | **20,000원/월** | + 자동 생성 공인 IP 4,000원 별도 |
| 공인 IP | 4,000원 / 개 / 월 | |
| **VM 간 내부 통신(사설망)** | **무과금** | 서버 페이지 "무료 제공 혜택" |
| 무료 국내 트래픽 | 서버·LB 등 **공인 IP 연동 장비당 1,110GB**(≈1TB) | 고사양은 2,220 / 4,440GB |
| 무료 해외 트래픽 | 장비당 50GB | 초과분 500원/GB |
| 국내 트래픽 초과분 | 100원/GB (1~5TB 구간) | 이후 90 / 80 / 70원 |
| 스토리지 스냅샷 / 이미지 | 건당 2,000원 / 1,000원 (**1회성**) | 점유 용량 스토리지 요금 별도 |
| Windows / MSSQL / Tibero | 별도 · 403,200원 · 50,000~200,000원 | **크레딧 미적용 — 사용하지 않음** |

> 원본 설계안의 “2vCPU/4GB 55,000원 + Root SSD 50GB 5,750원 = 60,750원”은 계산기 단가와
> 정확히 일치한다. 즉 원본의 견적 방식 자체는 검증됐고, 사양만 재배치하면 된다.
> 단 계산기 단가는 변경될 수 있으므로 **생성 직전 계산기에서 최종 확인**한다.

---

# 세션 1. 9개월 예산 최적화 아키텍처 & 노드 스펙

## 1.1 예산 상한 산정

| 구분 | 금액 |
| --- | --- |
| 총 크레딧 | 3,000,000원 |
| 운영 기간 | 9개월 |
| 월 사용 가능액 (VAT 포함) | 333,333원 |
| **월 사용 가능액 (공급가액 환산)** | **303,030원** |

크레딧이 VAT까지 차감된다는 보수적 가정을 유지한다(§1.6 확인 항목). 크레딧을 100% 태우는
설계는 트래픽 초과·스냅샷 같은 변동비 한 번에 초과 결제로 넘어가므로, **소진 목표를 97~98%로
두고 잔액을 Phase 4 이관 리허설 재원으로 계획**한다.

## 1.2 후보안 비교 — 왜 `2vCPU/8GB × 3`인가

JVM 워크로드에서 부족하면 가장 먼저 서비스를 죽이는 자원은 **메모리**다. CPU 부족은 지연
증가로 나타나지만 메모리 부족은 OOMKill로 즉시 장애가 된다. 따라서 “같은 예산이면 메모리
비율이 높은 flavor”가 1차 기준이고, etcd quorum을 위한 **3노드**가 제약이다.

| 안 | 노드 구성 | 총 자원 | 월액(VAT 포함) | 9개월 총액 | 판정 |
| --- | --- | --- | --- | --- | --- |
| **A (채택)** | standard `2/8` × 3 | 6 vCPU / **24GB** | **301,895원** | 2,717,055원 | ✅ 예산 내, 잔액 9.4% |
| B | high_cpu `4/8` × 3 | 12 vCPU / 24GB | 438,845원 | 3,949,605원 | ❌ 32% 초과 |
| C | high_memory `2/16` × 3 | 6 vCPU / 48GB | 372,845원 | 3,355,605원 | ❌ 12% 초과 |
| D | high_memory `2/16` × 2 + high_cpu `2/4` × 1 | 6 vCPU / 36GB | 325,545원 | 2,929,905원 | ⚠️ 조건부 |
| E (원본) | high_cpu `2/4` × 3 | 6 vCPU / 12GB | 249,755원 | 2,247,795원 | ❌ 크레딧 25% 미소진 |

**B 탈락** — CPU 12 vCPU는 매력적이지만 예산이 32% 초과한다. 6노드로 쪼개도 etcd 3 + worker 3
분리는 같은 금액대에서 노드당 사양이 다시 4GB로 내려가 원본 문제로 회귀한다.

**C 탈락** — 48GB는 이 규모에서 쓸 곳이 없다. 공인 IP·스토리지를 최소로 깎아도(320,600원 공급가)
9개월이 성립하지 않는다. 8개월이면 들어가지만 기간 요구를 못 맞춘다.

**D 조건부 대안** — 총 메모리 36GB로 A보다 12GB 많다. `2/16` 두 대에 앱을 올리고 `2/4` 한 대는
Control Plane·etcd·시스템 애드온 전용으로 taint를 건다. 단점이 결정적이다.

- 앱을 배치할 수 있는 노드가 **실질 2개**다. 한 대가 죽으면 전체 워크로드가 단일 노드로 몰린다.
- `topologySpreadConstraints`로 배울 수 있는 분산 시나리오가 2노드로 축소된다.
- 노드 사양이 불균일해 “어느 노드가 죽어도 같다”는 HA의 기본 성질이 깨진다. 장애 훈련 시
  `2/4` 노드 정지와 `2/16` 노드 정지의 영향이 전혀 다르다.
- 공인 IP를 2개로 줄여야 겨우 예산에 들어가므로 예비비가 2.3%밖에 남지 않는다.

**A 채택** — 대칭 3노드는 스케줄링 예측 가능성, 장애 대응 절차의 단일성, 예비비 확보에서
전부 유리하다. 메모리 24GB는 Spring Boot API(heap 1GB급) 여러 개 + PostgreSQL 2대 +
Redis + 시스템 애드온을 수용한다. **메모리 24GB는 필수 워크로드가 `normal` overlay 상태에서
1노드 장애를 자동 생존하도록 설계한다.** 단, 이 판단은 Phase 1의 실제 request 및 스케줄링
검증을 통과해야 확정된다(§3.5).

> ⚠️ **명칭에 대한 단서** — 이 구성을 "3노드 HA"라고 부르지만 정확히는
> **"단일 리전·단일 장애 도메인 가능성이 있는 3노드 고가용성 구성"** 이다.
> `topologySpreadConstraints`의 `kubernetes.io/hostname`은 **VM 간 분산만 보장**하고 물리
> 장애 도메인을 보장하지 않는다. 세 VM이 같은 하이퍼바이저·랙·전원 계통·스토리지 백엔드에
> 있으면 실제 HA가 아니다. §1.6 문의 F 그룹으로 확인한 뒤 명칭을 확정한다.
>
> 그리고 **"DR"은 가비아 전체 장애나 계정 장애에서 복구 가능함을 검증했을 때만 쓴다.**
> 이 설계에서 그 조건을 만족하는 것은 **외부 백업(R2·S3)뿐**이다. Phase 4의 신규 클러스터
> 작업은 DR이 아니라 **재구축·데이터 복원 리허설**이다(§Phase 4).

원본(E) 대비 실질 변화는 다음 세 가지다.

1. 노드당 메모리 4GB → 8GB, 총 12GB → **24GB**
2. 원본이 포기한 **PostgreSQL HA(CloudNativePG 2 instance + PITR)** 를 되살림
3. 크레딧 소진율 75% → **98%** (원본을 9개월로 그냥 줄이면 75만 원이 남아 낭비)

### 1.2.1 Control Plane / Worker 분리 구성은 왜 안 되는가

K3s는 `server`(Control Plane + etcd)와 `agent`(Worker 전용)를 분리할 수 있다. 대규모
프로덕션의 표준 형태이므로 반드시 정량 비교해야 한다. 실제 단가로 계산한다.

**전제** — `server` 3대가 etcd quorum을 이루고 `node-taint`로 워크로드를 배제한다.
`agent`가 앱을 전담한다. `server` 노드에도 아웃바운드용 공인 IP가 필요하고, etcd용
Data SSD(20GB)가 필요하다.

| 안 | 구성 | 공급가액 | 월액(VAT 포함) | 앱 배치 가용 메모리 | **1노드 장애 시 앱 가용** |
| --- | --- | --- | --- | --- | --- |
| **A 통합 3노드 (채택)** | `2/8` × 3 | 274,450 | **301,895** | **~18.0Gi** | **12.0Gi** |
| G 분리 3+1 | micro `1/2` × 3 + `4/16` × 1 | 268,800 | 295,680 | ~14.5Gi | **0Gi (전면 정지)** |
| G2 분리 3+1 저가 | micro `1/2` × 3 + `2/16` × 1 | 221,800 | 243,980 | ~14.5Gi | **0Gi (전면 정지)** |
| I 분리 3+2 | micro `1/2` × 3 + `2/8` × 2 | 285,450 | 313,995 | ~12.9Gi | **6.4Gi** |
| J 분리 3+2 (CP 정상 사양) | `2/4` × 3 + `2/8` × 2 | 330,750 | 363,825 | ~12.9Gi | 6.4Gi |
| K 분리 3+3 (A와 자원 동등) | micro `1/2` × 3 + `2/8` × 3 | 370,600 | 407,660 | ~19.3Gi | 12.9Gi |

**결론 네 가지**

**0) 워커 1대(G·G2)는 예산은 통과하지만 구조적으로 탈락한다.** G2는 오히려 크레딧 80만 원이
남는다. 그런데도 안 되는 이유가 셋이다.

- **워커가 1대면 etcd 3노드 HA가 논리적으로 무의미해진다.** Control Plane이 3중화돼 살아
  있어도 워커가 죽으면 서비스는 죽는다. CP HA에 쓰는 77,250원이 **서비스 가용성에 0을
  기여**한다. 그 돈을 워커에 쓰는 게 합리적이고, 그러면 워커가 2대가 되고, 그러면 CP를
  따로 둘 예산이 없어져 **통합형으로 수렴한다.** 이것이 통합형을 택한 근본 논리다.
- **무중단 배포와 노드 패치가 원리적으로 불가능하다.** 롤링 업데이트 시 old/new 파드가 같은
  노드에 공존해야 해서 순간 메모리가 2배 필요하다. `topologySpreadConstraints`와 PDB가
  무의미해진다(노드 1개를 drain하면 전멸). 커널 패치 재부팅이 곧 서비스 중단이다.
- **워커 1대의 가용성은 docker compose와 같다.** Kubernetes를 쓰는 이유의 절반인 노드 장애
  자동 복구와 무중단 배포가 성립하지 않으므로, 남는 것은 "Control Plane을 운영해 봤다"뿐이다.
  실사용자 대상 서비스를 9개월 운영하고 발표·데모가 있는 이 프로젝트에는 맞지 않는 교환이다.

**A와 G의 차이는 월 6,215원이다. 이 금액으로 서비스 HA를 산다.**

**1) 같은 예산에서 분리형은 워커 자원을 반드시 손해본다.** 후보 I는 통합형보다 **월 12,100원을
더 내고 앱 메모리 5.1Gi와 CPU 1.9 vCPU를 잃는다.** Control Plane 3대의 비용이 순수
오버헤드가 되기 때문이다. 통합형은 그 3대의 남는 자원을 워크로드가 쓴다.

**2) 1노드 장애 내구성이 절반이 된다.** 워커가 2대면 1대 장애 시 앱 가용 메모리가 6.4Gi다.
§3.5에서 계산한 requests 총합 13.0Gi를 전혀 수용하지 못한다. **Control Plane HA를 얻고
Worker HA를 잃는 교환**이므로 순손실이다. 이 클러스터에서 실제로 위험한 것은 Control Plane
과부하가 아니라 워커 자원 부족이다.

**3) micro `1/2`로 etcd HA를 돌리는 것 자체가 역설이다.** etcd는 CPU 지연과 디스크 fsync에
가장 민감한 컴포넌트다. 1 vCPU에서 apiserver의 watch 처리와 etcd compaction이 겹치면
heartbeat 타임아웃 → leader election 반복이 발생한다. **Control Plane을 격리했는데 Control
Plane이 더 불안정해진다.** 이를 피하려고 CP를 `2/4`로 올리면(후보 J) 월 363,825원으로
예산을 넘는다.

**손익분기점** — 분리형이 통합형과 동등한 앱 자원을 갖는 최소 구성은 후보 K로 월 407,660원,
통합형 대비 **+35%** 다. 월 예산이 약 41만 원이 되면 분리형이 타당해진다.

**분리형이 정당해지는 조건** (지금은 해당 없음)

- 노드가 5대 이상으로 늘어 Control Plane 부하가 유의미해질 때
- 워커를 자유롭게 교체·오토스케일해야 할 때 (통합형은 server 노드를 함부로 죽일 수 없다)
- 워커에 신뢰 경계가 다른 워크로드(멀티테넌시, 외부 코드 실행)가 올라올 때
- 예산이 노드 6대를 모두 충분한 사양으로 채울 수 있을 때

### 1.2.2 통합형의 실질 리스크와 완화

통합형을 택하면 **앱 파드가 Control Plane의 CPU·I/O를 빼앗을 수 있다.** 특히 §3.1에서
`limits.cpu: 2000m`(노드 코어 전부)을 권고하므로 이 위험은 실재한다. 정직하게 다룬다.

K3s server 컴포넌트는 파드가 아니라 `k3s.service` systemd 유닛의 프로세스로 실행되고,
파드는 `kubepods` cgroup에 있다. 따라서 **systemd 수준에서 우선권을 준다.**

```ini
# /etc/systemd/system/k3s.service.d/priority.conf
[Service]
CPUWeight=10000        # 기본 100 → CPU 경합 시 Control Plane 우선
IOWeight=10000         # etcd fsync 우선 (etcd 지연의 주 원인)
OOMScoreAdjust=-999    # 메모리 압박 시 가장 마지막에 종료
```

추가 규칙 세 가지.

1. `kubelet-arg`의 `system-reserved`·`kube-reserved`(§2.1)로 allocatable을 낮춰 파드
   requests 총합을 제한한다.
2. **노드당 앱 CPU requests 총합을 1.4 vCPU 이하로 유지**해 정상 상태에서 Control Plane이
   최소 0.5 vCPU를 확보하게 한다(§3.5의 총 2840m ÷ 3노드 ≈ 0.95 vCPU/노드로 충족).
3. **업그레이드·drain은 반드시 1대씩** 진행한다. 통합형은 노드를 비우면 Control Plane 멤버
   하나가 같이 빠져 quorum이 2/3가 된다. 다음 노드로 가기 전에 etcd 멤버가 3개로 복귀했는지
   확인한다(Phase 3 업그레이드 리허설의 핵심 절차).

## 1.3 채택안 월간 견적

| 항목 | 구성 | 공급가액 |
| --- | --- | --- |
| VM (standard `2vCPU/8GB`, Root SSD 50GB 포함) | × 3대 | 222,750원 |
| 블록 스토리지 SSD (Data) | **65GB × 3대 = 195GB** @115원/GB (Data-A 25 + Data-B 40) | 22,425원 |
| External Load Balancer (Small) | 1개 | 15,000원 |
| 공인 IP | 노드 3 + LB 1 = 4개 | 16,000원 |
| **공급가액 합계** | | **276,175원** |
| VAT 10% | | 27,445원 |
| **월 합계** | | **303,793원** |

| 기간 정산 (정액 운용 시) | 금액 |
| --- | --- |
| 9개월 균등 운영 | 2,717,055원 |
| 잔여 크레딧 | 282,945원 (9.4%) |

### Phase별 가변 예산 운용 (권장)

크레딧이 **월 한도 없는 3,000,000원 통합 풀**로 확인됐으므로(§1.6) 예산을 앞뒤로 옮길 수 있다.
자원 필요량은 Phase마다 다르다 — Phase 1~2는 PostgreSQL 데이터가 거의 없고, Phase 4는
클러스터를 두 개 동시에 띄워야 한다. 정액 운용보다 다음 배분이 낫다.

| 시기 | 구성 | 월액(VAT 포함) | 기간 | 소계 |
| --- | --- | --- | --- | --- |
| Phase 1~4 (1~9개월차) | 기본 3노드, **Data 65GB × 3** (Data-A 25 + Data-B 40) | 303,793원 | 9개월 | 2,734,137원 |
| Phase 4 추가 (8개월차 1개월) | **재구축·복원 리허설용 신규 2노드 클러스터** (`2/8` × 2, Data 40GB × 2, 공인 IP 2, LB 없음) | 182,270원 | 1개월 | 182,270원 |
| **합계** | | | | **2,916,407원** |
| **잔여 (예비)** | | | | **83,593원 (2.8%)** |

> **Data-A를 20GB → 25GB로 올렸다**(§1.4). `data-dir: /mnt/k3s`가 컨테이너 이미지까지 Data-A로
> 옮기므로 20GB는 빠듯하다. 월 1,898원 증가(9개월 17,082원)로 예비 안에서 흡수된다.
>
> **초판의 "Phase 1~2는 40GB로 시작해 약 3만 원 절약" 계획을 철회했다.** 40GB는 §2.5.2의
> CNPG 선언과 충돌해 DB 노드의 여유 공간이 0이 되고, **local-path는 PVC 용량을 강제하지 않으므로
> PostgreSQL이 etcd와 같은 파일시스템을 채울 수 있었다.** 절약액보다 손실 위험이 크다.

**재구축·복원 리허설 클러스터를 2노드·LB 없이 구성하는 이유** — 이 리허설에서 검증할 것은
L1 인프라 재현성, Infisical Machine Identity credential 복원, Argo CD 부트스트랩, S3에서 PostgreSQL 복구,
데이터 정합성이다. etcd 3노드 HA와 LB·TLS 경로는 이미 Phase 1~3에서 검증했으므로 반복하지
않는다. 2노드(K3s server 1 + agent 1)로 충분하고 접근은 NodePort 직접으로 한다.
비용이 3노드+LB 구성(301,895원) 대비 **119,625원 저렴**하다.

**예비 83,593원의 용도**

| 우선순위 | 용도 |
| --- | --- |
| 1 | LB 트래픽 초과·스냅샷·이미지 등 변동비 |
| 2 | 요금 인상 또는 견적 오차 흡수 |
| 3 | Data SSD 추가 증설 (10GB당 1,265원/월) |
| 4 | 9개월 이후 축소 사양 연장 (크레딧 만료 2027-07-31까지 약 3개월 여유가 있다) |

**문의 C3(서버 '종료' 시 CPU·메모리 미과금)이 확정되면 이 계획이 더 좋아진다.** 재구축 리허설
기간에 기존 노드를 '종료' 상태로 두고 신규 노드를 띄우는 스왑이 가능해져 추가 비용이
디스크·IP만 남는다. Phase 0에서 답을 받은 뒤 갱신한다.

## 1.4 Data SSD 배분 — 2볼륨 분리, 처음부터 65GB

Root SSD 50GB에는 OS와 최소 시스템 파일만 둔다. **K3s data-dir(etcd·containerd 이미지·kubelet
데이터)는 Data-A로 분리**한다. etcd는 fsync 지연에 민감하므로 이미지 pull·로그 I/O와 같은 디바이스를 쓰지 않는다.

> ⚠️ **초판의 두 가지 오류를 정정한다.**
>
> 1. **"etcd와 이미지 I/O를 분리한다"는 서술은 Root 디스크 대비에서만 맞았다.** 같은 Data SSD에
>    etcd·K3s state·PostgreSQL·WAL·Redis를 전부 올렸으므로, **PostgreSQL의 checkpoint·WAL flush와
>    etcd fsync가 같은 디스크 큐에서 경쟁**한다. 실제 병목 가능성이 가장 큰 조합을 격리하지
>    못했다.
> 2. **Phase 1을 40GB로 시작하는 계획은 §2.5.2의 CNPG 선언과 충돌했다.** `storage: 20Gi` +
>    `walStorage: 5Gi`이면 DB 노드에서 `K3s/etcd 15Gi + PG 25Gi = 40Gi`로 **파일시스템 오버헤드·
>    로그·임시 파일·컨테이너 writable layer의 여유가 0**이다. 그리고 **local-path Provisioner는
>    PVC 선언 용량을 파일시스템 quota로 강제하지 않는다** — 20Gi라고 써도 디렉터리는 같은
>    파일시스템의 남은 공간을 계속 쓴다. 즉 PostgreSQL이 디스크를 채우면 **etcd가 함께 죽는다.**

### 권장: 노드당 블록 스토리지 2개

블록 스토리지는 GB 단가(115원/GB)이므로 **볼륨을 나눠도 총액이 같다.** 장애 격리만 얻는다.

| 볼륨 | 크기 | 마운트 | 용도 |
| --- | --- | --- | --- |
| **Data-A** | **25GB** | `/mnt/k3s` | K3s data-dir — etcd + **컨테이너 이미지** + kubelet |
| **Data-B** | 40GB | `/mnt/aligner` | local-path PV — PostgreSQL(30Gi) 전용. Redis 는 emptyDir |
| 합계 | **65GB** | | 월 7,475원/노드 (VAT 별도) |

> ⚠️ **초판 정정 — `data-dir`은 컨테이너 이미지까지 옮긴다.** 초판은 "Root SSD 50GB에는 OS와
> **컨테이너 이미지만** 둔다"고 썼다. 틀렸다. `data-dir: /mnt/k3s`로 설정하면 다음이 전부
> Data-A로 간다.
>
> ```text
> /mnt/k3s/server/db          etcd
> /mnt/k3s/agent/containerd   ← 컨테이너 이미지 (Root SSD 가 아니다)
> /mnt/k3s/agent/kubelet      ← emptyDir · 컨테이너 로그
> ```
>
> Cilium 이미지가 크고(~700MB) aligner-api·postgres·argocd·alloy·traefik까지 버전 몇 개를
> 유지하면 **8~12GB**다. 20GB는 빠듯하므로 **25GB로 올린다**(+10GB/노드가 아니라 +5GB,
> 월 1,898원 · 9개월 17,082원 — 예비 100,675원 안).
>
> **`imagefs`가 `nodefs`와 같은 파일시스템이다.** 이미지와 kubelet이 같은 Data-A에 있으므로
> kubelet은 imagefs를 별도로 감지하지 않는다. eviction 임계가 Data-A 하나에 걸리며,
> **image GC 설정이 필수다**(§2.1 `kubelet-arg`).

**격리의 목적은 달성된다** — PostgreSQL이 Data-B를 가득 채워도 **etcd는 Data-A에 있어 살아남는다.**
다만 **이미지 pull I/O와 etcd fsync는 같은 디바이스를 공유한다.** 이건 데이터 손실이 아니라
배포 시점의 일시적 성능 문제이며, §2.7의 `etcd_disk_wal_fsync_duration_seconds` p99로 감시한다.
악화가 확인되면 Data-A를 별도 볼륨으로 더 분리하거나 이미지 pull을 배포 창구로 제한한다.

**가비아 Gen2가 VM당 복수 데이터 볼륨을 지원하는지 확인해야 한다**(§1.6 문의 C6).
Gen1 기준으로는 SSD 타입에서 `Root Volume 1개 + Data Volume 3개`가 가능했다.

### 복수 볼륨이 불가하면 — 단일 65GB + LVM 분할

```bash
# 하나의 65GB 디스크를 논리 볼륨으로 나눠 hard quota 효과를 낸다
pvcreate /dev/vdb
vgcreate vg_aligner /dev/vdb
lvcreate -L 25G -n lv_k3s     vg_aligner   # /mnt/k3s  (etcd + 이미지 + kubelet)
lvcreate -L 38G -n lv_aligner vg_aligner   # /mnt/aligner  (2G는 확장 여유)
mkfs.ext4 /dev/vg_aligner/lv_k3s
mkfs.ext4 /dev/vg_aligner/lv_aligner
```

LVM은 **논리 볼륨 단위로 용량이 하드하게 제한**되므로 local-path의 quota 미강제 문제를 우회한다.
PostgreSQL이 `lv_aligner`를 채워도 `lv_k3s`는 영향받지 않는다.

### 마운트 실패 시 루트 디스크 오염 방지

디스크 마운트가 실패한 상태에서 K3s가 기동하면 **루트 디스크에 데이터 디렉터리를 새로 만들고**
etcd를 빈 상태로 시작할 수 있다. 이건 조용히 진행되는 최악의 사고다.

```ini
# /etc/systemd/system/k3s.service.d/mount-guard.conf
[Unit]
RequiresMountsFor=/mnt/k3s
ConditionPathIsMountPoint=/mnt/k3s
```

```ini
# /etc/systemd/system/k3s.service.d/priority.conf  (§1.2.2와 병합)
[Service]
CPUWeight=10000
IOWeight=10000
OOMScoreAdjust=-999
```

`ConditionPathIsMountPoint`가 없으면 마운트 누락 시 K3s가 그냥 뜬다. **있으면 기동을 거부하고
명확히 실패한다.** 조용한 데이터 손실보다 시끄러운 기동 실패가 낫다.

### 용량 운영 규칙

블록 스토리지는 10GB 단위로 **증설만 가능하고 축소는 불가하다**(§1.6 #4). 따라서:

```text
시작    Data-A 25GB / Data-B 40GB (총 65GB)
경보    사용률 75% 도달 시 Warning (§2.7 필수 지표)
증설    10GB 단위. 10GB당 1,265원/월 (VAT 포함)
확장    CNPG는 storage.size 온라인 확장을 지원한다 (AllowVolumeExpansion: true)
감시    inode 사용률도 함께 본다 — WAL 파일이 많으면 용량보다 inode가 먼저 마를 수 있다
```

**초판의 "40GB로 4개월 유지해 약 3만 원 절약"은 철회한다.** 절약액보다 디스크 full로 etcd와
PostgreSQL을 동시에 위험에 빠뜨리는 비용이 크다. 처음부터 65GB로 시작한다.

## 1.5 아키텍처 다이어그램

```text
                            Internet
                                │
        ┌───────────────────────┴───────────────────────┐
        │                                               │
        │  관리 경로 — Phase 1 freeze 시 하나만 선택      │
        │  ├─ Tailscale 승인 → Subnet Router ×2          │
        │  │    out: TCP 443 · UDP 3478 · UDP 41641      │
        │  └─ 미승인       → WireGuard Gateway ×2        │
        │       in: UDP 51820 (유효 키 없으면 무응답)     │
        ▼                                               ▼
┌───────────────────────────────┐    ┌──────────────────────────────────┐
│ Gabia External LB (Small)     │    │  관리 게이트웨이 2대 (k3s-01·02)   │
│  :443 HTTPS → Node:30443      │    │  VPC {{ vpc_cidr }} 라우팅        │
│  :80  HTTP  → Node:30080      │    │  Tailscale: subnet router SNAT    │
│  공인 IP 1개 · 국내 1,110GB 무료│    │  WireGuard: 10.99.0.0/24 + MASQ  │
│  ※ 6443 리스너 없음            │    │  peer/ACL = 관리자 2명만          │
└───────────────┬───────────────┘    └──────────────┬───────────────────┘
                │                                   │
     ┌──────────┴───────────────────────────────────┴──────────┐
     │                                                         │
┌────▼─────────────────┐ ┌──────────────────────┐ ┌────────────▼─────────┐
│ k3s-01  [관리 GW]    │ │ k3s-02  [관리 GW]    │ │ k3s-03               │
│ standard 2vCPU/8GB   │ │ standard 2vCPU/8GB   │ │ standard 2vCPU/8GB   │
│ Ubuntu 24.04 LTS     │ │ 동일                 │ │ 동일                 │
│ Root SSD 50GB        │ │ Root SSD 50GB        │ │ Root SSD 50GB        │
│ Data-A 25GB /mnt/k3s │ │ Data-A 25GB          │ │ Data-A 25GB          │
│ Data-B 40GB /mnt/... │ │ Data-B 40GB          │ │ Data-B 40GB          │
│ 공인 IP (아웃바운드) │ │ 공인 IP              │ │ 공인 IP              │
├──────────────────────┤ ├──────────────────────┤ ├──────────────────────┤
│  K3s server (대칭 3노드 — 역할 동일)                                   │
│  kube-apiserver / scheduler / controller-manager                       │
│  embedded etcd  (quorum 2/3, Data-A)                                   │
│  kubelet / containerd / kube-proxy                                     │
│  Cilium VXLAN (8472/UDP) — Day 1 조건부 채택, Phase 1 Gate (§2.3)       │
│    Gate 실패 시 Flannel 로 클러스터 재생성 (운영 중 교체 없음)           │
├──────────────────────┤ ├──────────────────────┤ ├──────────────────────┤
│ Traefik              │ │ Traefik              │ │ Traefik              │
│ CoreDNS              │ │ CoreDNS              │ │ Argo CD (5 pods)     │
│ Grafana Alloy        │ │ Grafana Alloy        │ │ Grafana Alloy        │
│ cert-manager         │ │ CNPG standby         │ │ CNPG primary         │
│ Aligner API (Pod)    │ │ Aligner API (Pod)    │ │ Aligner API (Pod)    │
│ local-path PV (B)    │ │ local-path PV (B)    │ │ Redis (emptyDir)     │
└──────────┬───────────┘ └──────────┬───────────┘ └──────────┬───────────┘
           │                        │                        │
           └────────── Gabia Private Network (VPC) ──────────┘
              etcd 2379-2380/TCP · API 6443/TCP
              kubelet 10250/TCP · VXLAN 8472/UDP
              ※ VM 간 내부 통신 무과금 (§1.6 #1)

           외부 백엔드 (클러스터 밖 — 클러스터가 죽어도 살아있음)
           ├─ Grafana Cloud   ← Alloy (metrics / logs / traces) + 외부 프로빙
           ├─ Cloudflare R2   ← etcd snapshot · PG WAL·basebackup (Bucket Lock)
           ├─ AWS S3          ← 월 1회 2차 사본 (Object Lock)
           └─ GHCR            → 컨테이너 이미지 (digest 고정)
```

**트래픽 흐름 — 서비스**

```text
사용자 → LB:443 → Node:30443 (Traefik NodePort, externalTrafficPolicy: Local)
       → Gateway(HTTPRoute) → Service → Aligner API Pod
```

`externalTrafficPolicy: Local`은 노드 간 홉을 제거하고 클라이언트 IP를 보존한다. 대신 Traefik이
없는 노드는 LB 헬스 체크에서 빠지므로 **Traefik을 3 replica로 노드마다 하나씩** 두어야 한다
(`topologySpreadConstraints` + `maxSkew: 1`).

### 관리망 — WireGuard 관리 게이트웨이 2대

> ⚠️ **초판의 모순을 정정한다.** 초판은 본문에서 "Tailscale로 22·6443을 인터넷에 노출하지
> 않는다"고 하면서 다이어그램에서는 **External LB가 :6443을 공개**했다. 둘은 동시에 성립하지
> 않는다. 그리고 **Tailscale Personal 플랜은 비상업적 개인 용도로 한정**되므로(§1.5.1)
> 팀 프로젝트의 프로덕션 클러스터 관리망을 무료 전제로 설계할 수 없다.

**LB 6443 리스너를 제거한다.** 두 가지 이유다.

1. **필요하지 않다.** K3s agent와 server는 내장 클라이언트 사이드 로드밸런서
   (`127.0.0.1:6444`)를 가지고 있어, 최초 접속 후 전체 server 목록을 학습해 자동 failover한다.
   **클러스터 내부 HA에 외부 LB가 필요 없다.** 초판이 인용한 K3s 문서의 외부 LB 구성은
   공식 지원 방식이지만 **필수가 아니라 선택**이었다.
2. **IP 제한이 동작하지 않을 수 있다.** L4(TCP) LB가 프록시 모드라면 원본 IP가 소실되어
   보안그룹에서 관리자 IP를 식별할 수 없다. LB 자체 ACL이 없다면 6443이 실질적으로 전체
   공개된다(§1.6 문의 C7).

**구성**

```text
관리자 노트북 A ─┐
                 ├── WireGuard GW: k3s-01  (UDP 51820)
관리자 노트북 B ─┤        └── AllowedIPs = {{ vpc_cidr }}  (VPC CIDR)
                 │
                 └── 예비 GW: k3s-02      (UDP 51820)
                          └── 장애 시 프로필 수동 전환

WireGuard 대역   10.99.0.0/24  (관리자 A: 10.99.0.11, B: 10.99.0.12)
```

**노드 간 통신은 WireGuard로 감싸지 않는다.** etcd·kube-apiserver·VXLAN은 이미 가비아 VPC
사설망을 쓰고 그 트래픽은 무과금이다(§1.6 #1). 관리자 5-peer 풀메시는 불필요한 복잡도다.

**리턴 경로 — MASQUERADE로 해결한다**

`AllowedIPs = {{ vpc_cidr }}`는 관리자 → VPC 방향만 정의한다. k3s-02/03이 `10.99.0.0/24`로
응답을 되돌릴 경로가 없으므로 게이트웨이에서 SNAT한다.

```bash
# 게이트웨이 노드 (k3s-01, k3s-02)
sysctl -w net.ipv4.ip_forward=1
iptables -t nat -A POSTROUTING -s 10.99.0.0/24 -o eth0 -j MASQUERADE
```

정적 라우트(`ip route add 10.99.0.0/24 via <GW 사설IP>`) 방식도 가능하고 원본 IP가 보존되지만,
게이트웨이 2대에서 비대칭 라우팅 위험이 생긴다. **9개월 프로젝트에서는 MASQUERADE가 맞다** —
게이트웨이를 전환할 때 다른 노드를 건드리지 않아도 된다. 대가는 목적지에서 관리자별 원본 IP를
식별할 수 없다는 것이고, kubectl은 인증서·토큰으로 감사되므로 영향이 작다.

**WireGuard 게이트웨이를 2대 두는 이유** — 1대만 두면 그 노드 장애 시 서비스는 살아 있는데
**관리자가 클러스터에 접근할 수 없다.** 관리망이 사용자 트래픽만큼 높은 HA를 요구하지는
않지만, 설정 비용이 거의 없으므로 2대에 둔다. 자동 HA는 구현하지 않고 **관리자 설정에 두 프로필을
두고 수동 전환**한다.

**kubeconfig 엔드포인트**

```yaml
# K3s config.yaml — 세 노드의 사설 IP를 모두 tls-san 에 넣는다
tls-san:
  - {{ k3s_node_ips[0] }}
  - {{ k3s_node_ips[1] }}
  - {{ k3s_node_ips[2] }}
  - k8s-api.aligner.internal      # /etc/hosts 또는 내부 DNS
```

kubeconfig의 `server`를 k3s-01 사설 IP로 두고, k3s-01 장애 시 context를 k3s-02로 전환한다.
**WireGuard 프로필 전환과 같은 패턴**이라 운영 절차가 하나로 통일된다. 자동 failover가 필요해지면
가비아 **Internal LB**(사설 IP, 15,000원/월)로 6443을 받을 수 있으나 Phase 1에는 불필요하다.

**⚠️ break-glass 경로가 반드시 필요하다**

22/TCP를 공인망에서 닫고 WireGuard만 남기면, **WireGuard 설정 실수·커널 모듈 문제·방화벽
오작동 시 세 노드 모두에 들어갈 수 없다.** 재설치밖에 없는 상황이 된다.

```text
1순위  가비아 콘솔의 VNC/웹 콘솔 접속 (Gen2가 OpenStack 기반이므로 Nova 콘솔 존재 가능)
       → §1.6 문의 C5로 확인. 있으면 이것이 break-glass다.
2순위  k3s-03 한 대에만 관리자 고정 IP 대상 22/TCP 허용
       → 완전 차단보다 낫다. 게이트웨이 2대(k3s-01·02)와 겹치지 않는 노드로 둔다.
```

**보안그룹 정책**

| 방향 | 포트 | 허용 대상 |
| --- | --- | --- |
| 인바운드 (외부) | 443, 80 | LB 사설 IP만 → NodePort 30443/30080 |
| 인바운드 (외부) | **51820/UDP** | **전체** (k3s-01·02만). WireGuard는 유효 키 없는 패킷에 무응답 |
| 인바운드 (외부) | 22/TCP | **차단.** break-glass 2순위 채택 시 k3s-03만 관리자 고정 IP |
| 인바운드 (외부) | 6443/TCP | **차단** (LB 리스너 제거) |
| 인바운드 (사설) | 2379-2380, 6443, 10250, 8472/UDP | 노드 사설 대역만 |
| 인바운드 (WG) | 22, 6443, 10250 | `10.99.0.0/24` (MASQUERADE 후에는 GW 사설 IP) |
| 아웃바운드 | 443 | 이미지 레지스트리·Grafana Cloud·R2·S3·ACME |

**공인망에서 닫는 것** — 22/TCP, 6443/TCP, Argo CD UI, PostgreSQL 5432, Redis 6379.
전부 WireGuard 경유로만 접근한다.

**UDP 51820을 전체 공개해도 되는 근거** — WireGuard는 **유효한 키로 서명되지 않은 패킷에
아무 응답도 하지 않는다.** 포트 스캔으로 열려 있는지조차 알 수 없다(silent). SSH를 여는 것과
위험도가 근본적으로 다르다. 관리자 IP가 유동적이어도 화이트리스트 운영이 필요 없다.

**약점 — 키 폐기 UX가 없다.** peer 제거는 게이트웨이 2대의 설정 파일을 편집하고
`wg syncconf`를 다시 적용하는 수동 작업이다. 팀원 이탈 시 누락되면 접근이 유지된다.

```text
운영 규칙
├─ WireGuard 설정을 Ansible로 관리하고 peer 목록을 Git에 둔다 (공개키는 비밀이 아니다)
├─ 개인키는 각자 로컬 + 팀 패스워드 매니저에만 보관
├─ 팀원 이탈 시 해당 peer 공개키를 Git에서 제거하고 Ansible 재적용 (PR로 흔적 남김)
├─ Phase 전환 시점(1→2→3→4)마다 키 로테이션
└─ 게이트웨이 2대의 peer 목록이 동일한지 점검 플레이북으로 대조
```

### 1.5.1 관리망 — Phase 1 시작 시점을 freeze로 두는 시한부 분기

> ⚠️ **3판은 "WireGuard 채택, Tailscale은 선택 개선"이었다.** 그 안의 문제는 **둘 다 만들게
> 된다는 것**이다. 승인 전에도 관리망이 필요하므로 WireGuard를 배포하고, 승인되면 Tailscale로
> 또 바꾼다. 4판은 **freeze 날짜를 두고 하나만 배포**한다.

```text
Phase 0 즉시 (병렬)
├─ ALIGNER-SERVER 루트에 OSI 승인 라이선스(Apache-2.0) 추가
├─ Tailscale Community on GitHub 신청 (Billing 화면에서 즉시 선택 불가 — Support 경유 신청)
└─ WireGuard Ansible Role·키·Runbook 준비  ← 배포는 하지 않는다

Phase 1 시작 = freeze 시점
├─ Community 플랜 활성화 확인됨  → Tailscale 로 시작. WireGuard Role 은 fallback 으로 보관
└─ 미승인 · 보류 · 거절         → WireGuard 배포. 이후 승인돼도 Phase 3 이전에는 바꾸지 않는다
```

**두 관리망을 모두 완성하지 않는다.** freeze 시점에 하나를 골라 배포한다. 관리망 교체는
서비스 영향이 없으므로 나중에 전환할 수 있지만, 같은 것을 두 번 만드는 낭비는 하지 않는다.

| 후보 | 비용 | 판정 |
| --- | --- | --- |
| **Tailscale Community on GitHub** | **0** (승인 시) | **freeze 시점에 승인됐으면 1순위.** subnet router HA·MagicDNS·중앙 ACL을 무료로 얻는다 |
| **WireGuard 직접 구성** | **0** | **미승인 시 채택.** 승인 불필요, 오늘 동작 |
| Tailscale Standard | $8/user/월 × 2 = **$16/월** (약 2.2만 원, 크레딧 미적용 현금) | 예산을 쓸 수 있으면 가장 편리 |
| Tailscale Personal | 0 | **채택하지 않는다.** 아래 참조 |
| Headscale (자체 호스팅) | 0 | 이 규모에서 운영 복잡도가 편익보다 크다. 아래 참조 |
| 관리자 IP 화이트리스트만 | 0 | IP가 고정된 경우에만 가장 단순 |

**Tailscale Community on GitHub 조건** — 공식 문서 기준이다.

```text
□ GitHub Organization              Nexters ✓
□ GitHub 인증 사용                  가능 ✓
□ OSI 승인 라이선스 오픈소스 프로젝트  ← ALIGNER-SERVER 는 Public 이지만 LICENSE 파일이 없다
□ Billing 화면에서 즉시 선택 불가     Tailscale Support 경유 신청·승인 필요
```

`ALIGNER-SERVER`는 `github.com/Nexters/ALIGNER-SERVER`로 **Public이고 Organization 소속**이므로
조건 세 개 중 둘을 충족한다. **저장소 루트에 `LICENSE`를 추가하면 신청 자격이 생긴다**
(`LICENSE.md`도 가능하지만 GitHub 인식과 관례상 `LICENSE`를 권장). 라이선스는 **Apache-2.0**이
팀 단위 프로젝트에 더 명확하다(특허 조항·기여 조건 명시).

> ⚠️ **선행 확인** — NEXTERS 조직과 기존 기여자에게 이 코드를 오픈소스 라이선스로 배포할 권한이
> 있는지 내부 확인이 필요하다. 라이선스 추가는 그 자체의 가치(공개·기여 유도)로 판단하고,
> **VPN 무료 티어를 얻기 위한 수단으로만 결정하지 않는다.**

**공개 범위 — 저장소 공개 여부와 시크릿 보관은 별개다.**

```text
ALIGNER-SERVER                    Public + OSI License
ALIGNER-PLATFORM                  Public + OSI License
terraform-provider-gabiacloud     개인 Private 로 시작
```

`ALIGNER-PLATFORM`은 Terraform·Ansible·K3s·GitOps 구현과 기술 의사결정을 공개하는
**플랫폼 엔지니어링 저장소**다.

**저장소 공개 여부와 시크릿 보관 여부는 별개다.** Public 저장소에도 시크릿, Terraform state,
generated inventory, private key는 저장하지 않는다(§공개 저장소 운영 원칙).

`terraform-provider-gabiacloud`는 비공식 콘솔 API를 사용하므로 **가비아의 자동화 허용 여부와
공개 범위를 확인할 때까지** 개인 Private 저장소에서 개발한다(문의 D7).

### Tailscale 채택 시 구조

```text
관리자 노트북 A ─┐
                 ├─ Tailscale ─→ k3s-01 [subnet router]  ─┐
관리자 노트북 B ─┘                k3s-02 [subnet router]  ─┴─ {{ vpc_cidr }} 광고
```

동일 CIDR을 광고하는 복수 subnet router 간 **자동 failover가 모든 플랜에서 제공**되며 전환에
최대 약 15초가 걸릴 수 있다. subnet router는 기본적으로 SNAT하므로 **WireGuard 구성의 수동
MASQUERADE 스크립트와 프로필 수동 전환이 사라진다.**

보안그룹 변경:

```text
삭제   51820/UDP 인터넷 전체 허용
유지   22/TCP · 6443/TCP 공인망 차단 · 80/443 은 LB 만 · break-glass
추가   아웃바운드 TCP 443 (DERP relay) · UDP 3478 (STUN) · UDP 41641 (direct tunnel)
선택   직접 P2P 최적화가 필요하면 41641/UDP 인바운드 검토
```

**Tailscale Personal을 쓰지 않는 이유** — 현재 조건은 최대 6명·user devices 무제한·tagged
resources 50개로 숫자는 충분하다. 문제는 약관이다. 공식 안내는 Personal을 **"개인이 집에서
사용하는 비상업적 용도"** 로 규정하고 **프로덕션 클러스터·Kubernetes 연결을 대표적인 business
use 사례로 명시**한다. 커스텀 도메인으로 tailnet을 만들면 business로 분류되어 14일 평가판으로
시작하며, **이후 계속 쓰려면 플랜을 선택해야 한다**(자동 청구는 아니다).

Aligner는 개인 홈랩이 아니고, 팀원 여러 명이 공동 운영하며, 실사용자 대상 서비스의 프로덕션
Kubernetes를 관리한다. 개인 계정으로 무료 등록이 기술적으로 가능하더라도 **무료 플랜의 의도에
부합한다고 보기 어렵다.** 관리망 접근 경로를 약관 해석의 모호함 위에 두지 않는다.

**Headscale을 쓰지 않는 이유** — Tailscale 컨트롤 서버의 오픈소스 자체 호스팅 구현으로 기능은
충분하다. 그러나 Headscale 서버·공개 도메인·TLS 인증서·DB와 백업·업그레이드·등록 키·정책 관리가
추가된다. 결정적으로 **Headscale을 같은 K3s 클러스터에 두면 클러스터 전면 장애 시 관리망도 함께
죽는다** — 새 관리자 기기를 등록할 수 없고 복구 관리망이 클러스터에 종속된다. 이는
**관측 백엔드를 외부화한 논리(§2.7)와 정확히 같은 이유로 배제**해야 한다. 공식 FAQ도 Headscale
서버를 자기 tailnet의 클라이언트로 함께 운영하는 구성은 subnet router·MagicDNS에서 문제를
일으키며 지원되지 않는다고 안내한다. 클러스터 밖에 별도 VM을 두면 그 VM의 비용과 운영이 다시 생긴다.

## 1.6 요금·정책 조사 결과

원본 §10의 "확인 필요" 목록을 실제 조사 결과로 대체한다. 근거는 가비아 클라우드 공식
페이지·요금 계산기 데이터·크레딧 관리 화면이다.

### 확정된 사실

| # | 항목 | 결과 | 근거 |
| --- | --- | --- | --- |
| 1 | 사설망(VM 간) 내부 트래픽 | **무과금** | 서버 페이지 "무료 제공 혜택"에 `VM 간 내부 통신 무과금` 명시. 보안그룹·VPC·모니터링도 무료 |
| 2 | 크레딧 구조 | **월 한도 없음. 3,000,000원 통합 풀** | 크레딧 관리 화면: 지급 3,000,000 / 잔액 3,000,000 / 시작 2026-07-16 / **만료 2027-07-31** |
| 3 | NAT 게이트웨이 대체 | **불리. 노드 공인 IP 유지** | 계산기 로직상 NAT GW **20,000원/월** + 자동 생성 공인 IP 4,000원 = 24,000원 > 노드 IP 3개 12,000원 |
| 4 | 블록 스토리지 축소 | **불가 (증설만)** | Data Volume "상향으로 용량 변경 가능"만 기재 |
| 5 | 스냅샷 요금 | **건당 2,000원 1회성 + 점유 용량 스토리지 요금 별도** | 계산기 주석 "월비용이 아닌 1회성 비용", "이미지 저장 공간 비용은 별도" |
| 6 | 청구 주기 | 매월 1일 전월 사용량 청구, **10일까지 납부**. 크레딧은 익월 청구서 반영 | 서버 FAQ + 크레딧 화면 |
| 7 | 미납 시 | **11일 서비스 정지 → 1개월 후 자동 해지 및 데이터 삭제** | 서버 FAQ 체불 정책 |
| 8 | 사양 변경 | **가능**(vCPU·메모리). 다만 **서버 정지 필요 가능성 높음** | "중지 상태에서 사양 변경·IP 추가·스토리지 추가 가능"으로 서술 |
| 9 | **오브젝트 스토리지(S3 호환 버킷)** | **존재하지 않음** | 계산기 전체 서비스 목록에 블록 스토리지·NAS만 있음(아래) |
| 10 | **부분 월 사용 시 과금** | **1개월 미만은 시간제, 1개월 만기는 월 정액(더 저렴)** | FAQ 7261/8100 |
| 11 | Root 스토리지 | **50~300GB** (Windows는 최소 100GB) | 블록 스토리지 FAQ |
| 12 | Data 스토리지 | 10~2,000GB. 1,000GB까지 10GB 단위, 이후 100GB 단위. 프로젝트당 총 20,000GB 한도 | 블록 스토리지 FAQ |

**가비아 Gen2 전체 서비스 목록** (요금 계산기 내부 데이터)

```
서버 / GPU서버 / 베어메탈 / 스냅샷 / 이미지 / 오토스케일링
블록 스토리지 / NAS / NAS스냅샷 / 스토리지스냅샷 / 스냅샷스케줄러
공인IP / 트래픽 / 로드밸런서 / NAT게이트웨이 / CDN
VPC / 서브넷 / 라우터 / 네트워크인터페이스 / 피어링게이트웨이 / 보안그룹 / SSH키페어
SSL인증서 / 웹방화벽 / 백신 / DB보안 / SSL VPN / 웹쉘탐지 / IPS / 모니터링 / HA솔루션
백업 / 이미지백업 / 매니지드 / 기술지원
사용자 스크립트 / 쿠버네티스 서비스 / 컨테이너 레지스트리 / 기타
```

여기서 설계에 영향을 주는 것이 셋이다.

1. **오브젝트 스토리지가 없다.** 백업 대상을 외부에서 골라야 한다 → Cloudflare R2(§2.5.2).
   `/storage/objectstorage/`가 HTTP 200을 반환하지만 본문은 홈페이지다(Nuxt SPA 폴백).
2. **`사용자 스크립트` = cloud-init 지원.** L1에서 VM을 만들 때 노드 초기화까지 함께 넣을 수
   있다(§2.8.6 경로 2).
3. **`컨테이너 레지스트리`가 있다.** GHCR 대신 쓰면 이미지 pull이 내부 트래픽(무과금)이 된다.
   단 크레딧 적용 여부가 불명이므로 문의 항목에 포함한다.

**#10의 함의** — Phase 4 재구축 리허설을 2주만 돌리면 시간제로 계산되어 월 정액의 절반보다 비쌀
수 있다. **정확히 1개월 단위로 생성·삭제**하는 편이 유리하다(§1.3 예산표가 이미 1개월 단위다).

**#2의 함의가 크다.** 월 한도가 없으므로 **Phase별로 사양을 다르게 운용해 예산을 앞뒤로 옮길 수
있다**(§1.3). 또 만료가 2027-07-31이므로 오늘(2026-08) 기준 약 11.8개월이 남아, 9개월 계획
뒤에도 약 3개월의 완충이 있다. 9개월은 상한이 아니라 목표다.

### 크레딧 미적용 항목 — 이 설계는 영향 없음

크레딧 유의사항에 **"서버의 OS, DBMS 요금과 CDN, 웹방화벽, 바이러스 백신, DB 보안, SSL VPN,
웹쉘 탐지, IPS, 모니터링 솔루션, HA 솔루션, 마켓플레이스 서비스는 크레딧이 적용되지 않는다"**
고 명시돼 있다. Gen2 계산기 데이터로 대조한 결과는 다음이다.

| 항목 | Gen2 계산기 상 요금 | 이 설계 |
| --- | --- | --- |
| **Rocky Linux / Ubuntu** | 추가 요금 항목 없음 (VM 요금에 포함) | ✅ 사용 — 영향 없음 |
| Windows Server | 별도 | 미사용 |
| MSSQL | 403,200원 | 미사용 |
| Tibero 7 Standard / Enterprise | 50,000 / 200,000원 | 미사용 |
| PostgreSQL·MariaDB (가비아 서버 이미지) | 0원 | **컨테이너로 운영** (가비아 DBMS 상품 아님) |
| CDN·웹방화벽·백신·DB보안·SSL VPN·웹쉘탐지·IPS·모니터링 솔루션·HA 솔루션 | 크레딧 미적용 | **전부 미사용** |

**결론: Rocky Linux(또는 Ubuntu) + 컨테이너 PostgreSQL 구성이면 크레딧 미적용 항목이 0원이다.**
가비아 관리형 부가서비스를 하나도 쓰지 않는 이 설계의 성질이 크레딧 효율 100%로 이어진다.
Grafana Cloud·Argo CD·cert-manager를 클러스터에서 직접 운영하는 선택이 여기서 비용상 이득으로
돌아온다 — 가비아 "모니터링 솔루션"(20,000원/월)이나 "HA 솔루션"(300,000원/월)은 크레딧
미적용이므로 현금 지출이 된다.

⚠️ 계산기에 OS별 가격 필드 자체가 없어 100% 단정은 불가하다. **첫 청구서에 OS 라인아이템이
있는지 확인**한다.

### 1:1 문의 문안 (그대로 보낼 수 있는 형태)

공식 문서·FAQ·요금 계산기로 확정할 수 없었던 항목이다. FAQ 카테고리 7261(클라우드 요금),
7781(클라우드 개요), 1146(결제), 20802(블록 스토리지), 22300(계정·보안그룹)을 확인했으나
**크레딧 차감 기준과 API 제공 여부는 공개 문서에 없다.**

접수 경로: `customer.gabia.com/ask/onetoone` (클라우드 > 가비아 클라우드 Gen2) 또는
02-3473-3911. **답변을 서면으로 남겨 Phase 0 산출물로 보관한다.**

```text
[제목] 가비아 클라우드 Gen2 크레딧·API·이미지 관련 문의 (Kubernetes 자체 구축 예정)

안녕하세요.
NEXTERS 연합동아리 후원 크레딧 3,000,000원(만료 2027-07-31)으로 Gen2에
Kubernetes 클러스터를 자체 구축해 약 9개월간 운영할 계획입니다.
구성은 Rocky Linux 서버 3대(Standard 2vCPU/8GB) + 블록 스토리지 + External LB이며,
설계 확정 전에 아래 사항을 확인하고자 합니다. 번호별로 답변 부탁드립니다.

■ A. 크레딧 차감·초과 (가장 중요)
A1. 크레딧은 청구서의 공급가액에서 차감됩니까, VAT 포함 총액에서 차감됩니까?
A2. 크레딧 잔액이 청구액보다 적을 경우 부족분이 등록된 결제수단으로 자동 결제됩니까?
    자동 결제를 원하지 않을 경우 차단하는 방법이 있습니까?
A3. 크레딧 잔액 소진 임박 시 알림을 받거나, 잔액 소진 시 신규 자원 생성을
    자동으로 제한하는 기능이 있습니까?
A4. 크레딧 유의사항의 "서버의 OS, DBMS 요금은 크레딧 미적용" 관련입니다.
    Rocky Linux 또는 Ubuntu를 선택하는 경우 OS 요금이 별도로 청구됩니까?
    청구된다면 월 금액과, 크레딧 미적용으로 현금 결제가 발생하는지 알려주십시오.
A5. 컨테이너 레지스트리 서비스는 크레딧 적용 대상입니까?
    (부가서비스·마켓플레이스로 분류되어 미적용인지 확인하고자 합니다)
A6. 관리형 Kubernetes(쿠버네티스 서비스)의 요금 체계와 크레딧 적용 여부를 알려주십시오.

■ B. 트래픽 과금 기준
B1. AWS S3(서울 리전) 또는 Cloudflare R2로 서버에서 데이터를 업로드하는 경우,
    국내 트래픽과 해외 트래픽 중 어느 쪽으로 분류됩니까?
    (백업 용도로 월 수십 GB 업로드가 발생할 예정이라 분류 기준이 필요합니다)
B2. 무료 국내 트래픽 1,110GB는 아웃바운드 기준입니까? 인바운드도 과금됩니까?
B3. 동일 VPC 내 서버 간 사설망 통신이 무과금이라고 안내되어 있습니다.
    이 사설망은 다른 고객(테넌트)과 네트워크 수준에서 격리됩니까?
    (Kubernetes 노드 간 etcd 복제 트래픽이 상시 발생하므로 격리 여부를 확인해야 합니다)

■ C. 서버·이미지 (설계 변경 가능 항목)
C1. 사용자가 직접 만든 커스텀 OS 이미지(ISO 또는 raw 디스크 이미지)를 업로드해
    서버를 생성할 수 있습니까?
    (불가하다면 Rocky Linux 기준으로 설계를 확정하려 합니다)
C2. vCPU·메모리 사양 변경 시 서버 정지가 필요합니까? 소요 시간은 어느 정도입니까?
C3. 서버를 '종료' 상태로 두면 CPU·메모리 요금이 청구되지 않는다고 안내되어 있습니다.
    Gen2에도 동일하게 적용됩니까? 이때 Root 스토리지 요금은 계속 청구됩니까?
C4. 블록 스토리지는 용량 축소가 불가한 것으로 이해했습니다. 맞습니까?
C5. 관리콘솔에서 서버에 VNC 또는 웹 콘솔로 직접 접속할 수 있습니까?
    (SSH를 공인망에서 차단할 계획이라 비상 접근(break-glass) 경로가 필요합니다)
C6. VM 1대에 데이터 블록 스토리지를 여러 개 연결할 수 있습니까? 최대 몇 개입니까?
    (etcd용 20GB와 데이터베이스용 40GB를 물리적으로 분리하려 합니다)
C7. External 로드밸런서의 TCP 리스너는 백엔드 서버에 클라이언트의 원본 IP를
    전달합니까? 로드밸런서 자체에 접근 허용 IP를 설정하는 기능이 있습니까?

■ D. API·자동화 (Infrastructure as Code)
D1. 고객이 직접 호출할 수 있는 공개 API가 있습니까?
    있다면 API 문서(OpenAPI/Swagger)와 인증 키 발급 경로를 안내해 주십시오.
    (콘솔이 사용하는 세션 기반 인증이 아니라, 서비스 계정이나 장기 유효 토큰을
     발급받을 수 있는지가 핵심입니다)
D2. Gen2가 OpenStack 기반 서비스로 보입니다. 관리형 Kubernetes 매뉴얼에
    cinder.csi.openstack.org 와 loadbalancer.openstack.org 어노테이션이 안내되어 있어
    Keystone·Nova·Neutron·Cinder·Octavia가 동작하는 것으로 이해했습니다.
    일반 Gen2 프로젝트 고객에게 다음 중 하나를 제공합니까?
      - clouds.yaml 또는 openrc.sh 다운로드
      - Keystone v3 인증 엔드포인트(auth_url)
      - Application Credential 발급 기능
      - Nova / Neutron / Cinder / Octavia API 접근 권한
    제공한다면 auth_url, region, project ID, external network ID,
    지원 서비스 카탈로그를 함께 안내해 주십시오.
D3. 가비아에서 공식 제공하거나 권장하는 Terraform / OpenTofu / Ansible 연동 수단이
    있습니까?
    (NHN Cloud와 카카오클라우드는 공식 Terraform Provider를 제공하고 있어,
     Gen2에도 동등한 수단이 있는지 확인하고자 합니다)
D4. 서버 생성 시 '사용자 스크립트'는 cloud-init 형식을 지원합니까?
    지원 형식과 크기 제한을 알려주십시오.
D5. 자동화용 서비스 계정 또는 API Key(장기 유효 토큰)를 발급받을 수 있습니까?
    현재 identity-api 세션은 2시간 만료이고 ID/PW 인증만 확인되어,
    자동화를 위해 계정 비밀번호를 저장해야 하는 상황입니다.
D7. 관리콘솔이 사용하는 API(identity-api, cloud-api)를 고객이 자동화 목적으로
    직접 호출하는 것이 약관상 허용됩니까? 호환성 유지·변경 통보 정책이 있습니까?
    (Infrastructure as Code 도구를 자체 개발할 계획이라 공식 입장이 필요합니다)

■ E. 오브젝트 스토리지
E1. S3 호환 오브젝트 스토리지 상품이 있습니까?
    (현재 블록 스토리지와 NAS만 확인되어, 없다면 외부 스토리지를 사용할 계획입니다)
E2. 없다면 향후 출시 계획이 있습니까?

■ F. 물리 장애 도메인 (HA 설계 검증)
F1. 서버 3대를 서로 다른 물리 호스트(하이퍼바이저)에 배치하도록 지정할 수 있습니까?
    anti-affinity 또는 placement policy 기능이 있습니까?
F2. 지정할 수 없다면, 동일 프로젝트에 생성한 서버들이 같은 물리 호스트에 배치될
    가능성이 있습니까?
F3. '서비스 존'(Zone A / Zone B)은 물리적으로 분리된 장애 도메인입니까?
    전원 계통·네트워크·스토리지 백엔드가 독립적입니까?
F4. 관리형 Kubernetes 문서에 KR1-Zone1-LB 라는 가용 영역 명칭이 있습니다.
    일반 Gen2 서버에도 가용 영역 개념이 적용됩니까?
F5. External 로드밸런서 자체는 이중화되어 있습니까? 장애 시 어떻게 처리됩니까?
F6. 블록 스토리지의 복제 범위와 SLA를 알려주십시오.
    서버가 있는 물리 호스트의 장애가 블록 스토리지에도 함께 영향을 줍니까?

감사합니다.
```

### 답변별 설계 영향

| 답변 | 설계 변경 |
| --- | --- |
| **A1이 "공급가액만"** | 실질 운영 가능 기간이 약 10개월로 늘어난다. §1.3 예산표를 여유 있게 재편 |
| **A2가 "자동 결제됨"** | 크레딧 소진 시점 알림을 직접 만든다. 8개월차부터 매주 잔액 확인을 운영 항목에 추가 |
| **A4가 "Linux OS 요금 있음"** | 크레딧 미적용 현금 지출이 발생한다. 금액에 따라 운영 기간 단축 검토 |
| **A5가 "미적용"** | 컨테이너 레지스트리를 쓰지 않고 GHCR 유지 |
| **B1이 "해외"** | 무료 50GB를 넘는 순간 500원/GB. 백업 압축·주기 조정 또는 NAS 1차 + 외부 월 1회로 변경 |
| **B3이 "격리 미보장"** | K3s `flannel-backend=wireguard-native`로 노드 간 암호화(§2.3) |
| **C1이 "가능"** | **설계를 Talos Linux로 전환 검토**(§2.1). L2(Ansible)가 사라지고 IaC가 단순해진다 |
| **C3이 "적용됨"** | Phase 4 재구축 리허설 비용이 거의 0. 기존 노드를 '종료'로 두고 스왑 가능(§1.3) |
| **C5가 "VNC 있음"** | 그것이 break-glass 경로. 22/TCP를 세 노드 모두에서 완전 차단 가능(§1.5) |
| **C5가 "없음"** | k3s-03 한 대에만 관리자 고정 IP 대상 22/TCP를 남긴다 |
| **C6이 "2개 이상 가능"** | Data-A 25GB / Data-B 40GB 2볼륨 분리(§1.4). etcd와 PG의 디스크 장애 격리 |
| **C6이 "1개만"** | 단일 65GB + LVM 논리 볼륨 분할로 hard quota 확보(§1.4) |
| **C7이 "원본 IP 미보존"** | LB 6443을 절대 열지 않는다(이미 제거). 관리 접근은 WireGuard 전용 |
| **D1·D2가 "제공"** | L1을 OpenTofu로. D2(OpenStack)면 `terraform-provider-openstack` 사용(§2.8.7) |
| **D1이 "세션 인증만"** | 콘솔 최소 부트스트랩 + YAML 인벤토리 + Ansible L2 자동화(§2.8.7 Fallback) |
| **E1이 "있음"** | 백업 1차를 가비아 오브젝트 스토리지로. 내부 트래픽 무과금으로 비용 0 |
| **F1·F3이 "분산 불가·단일 도메인"** | HA 명칭을 "단일 장애 도메인 3노드 구성"으로 낮추고, 진짜 DR은 외부 백업으로만 주장한다 |
| **F1이 "분산 가능"** | 노드를 서로 다른 물리 호스트·존에 배치. `topologySpreadConstraints`가 실제 물리 격리와 일치하게 된다 |

**우선순위** — A1·A2는 예산 안전장치라 착수 전 필수다. C1·D1·D2는 설계를 바꿀 수 있어
Phase 1 시작 전에 답을 받아야 한다. B1은 Phase 2 백업 구성 전까지 받으면 된다.

---

# 세션 2. 기술 스택 제로베이스 재검토

## 2.0 재검토 결과 요약

| 영역 | 원본 선택 | **재검토 결론** | 변경 |
| --- | --- | --- | --- |
| K8s 배포 도구 | K3s | **K3s** (2순위 RKE2, Talos는 가비아 이미지 제약으로 배제) | 유지 · 근거 교체 |
| Control Plane DB | embedded etcd ×3 | **embedded etcd ×3** (Data SSD 분리) | 유지 · 배치 개선 |
| GitOps | Flux CD | **Argo CD** | **변경** |
| CNI | Flannel VXLAN | **Cilium Day 1 최소 구성** (Phase 1 Gate, 실패 시 Flannel로 재생성) | **변경** |
| Service Proxy | kube-proxy | **kube-proxy 유지** (`kubeProxyReplacement: false`) | 유지 |
| Ingress 구현체 | Traefik (K3s 번들) | **Traefik (번들 해제 후 Argo CD 관리)** | 관리 주체 변경 |
| **Ingress 리소스** | Ingress / IngressRoute | **Gateway API `HTTPRoute`** | **변경** |
| Secret | SOPS + age | **Infisical Cloud + External Secrets Operator** (6판) | **변경** |
| TLS | cert-manager | **cert-manager** | 유지 |
| Storage | local-path | **local-path** (Longhorn 미도입) | 유지 · 근거 갱신 |
| Database | PG 단일 + 백업 | **CloudNativePG 2 instance + Barman PITR** | **변경** |
| **백업 저장소** | AWS S3 | **Cloudflare R2 1차** (가비아 오브젝트 스토리지 없음) | **변경** |
| Observability | Alloy → Grafana Cloud | **Alloy → Grafana Cloud** | 유지 · 근거 강화 |
| 관리 접근 | 고정 IP 화이트리스트 | **Phase 1 freeze 시 Tailscale Community 또는 WireGuard 하나만** (LB 6443 제거) | **변경** |
| **IaC (L1 인프라)** | Terraform (provider 미검증) | **초기 `gabiactl`(Go) + Ansible → 안정화 후 Terraform + `terraform-provider-gabiacloud`** (§2.8.5) | **변경** |
| **IaC (L2 노드)** | 언급 없음 | **Ansible (k3s-ansible)** | 추가 |
| 정책 엔진 | PSA + NetworkPolicy | **PSA + NetworkPolicy** | 유지 |

변경 3건은 모두 **월 예산이 25만 → 33만 원으로 늘어 메모리가 12GB → 24GB가 된 결과**다.
원본의 Flux·SOPS·PG 단일 Primary 선택은 “12GB 메모리”라는 제약의 산물이었고, 그 제약이
사라지면 결론이 달라진다. 예산이 늘었는데 스택이 그대로면 재검토를 하지 않은 것이다.

---

## 2.1 Kubernetes 배포 도구 — K3s vs kubeadm vs k0s vs RKE2

### 비교

**2026-08-06 기준 실측** — K3s 33,661 stars / k0s 6,408 / **Talos 10,886** / RKE2 2,298
(모두 2026-08-05 활성). 별점만 보면 K3s가 압도적이고 Talos가 2위다.

| 기준 | K3s | RKE2 | k0s | kubeadm |
| --- | --- | --- | --- | --- |
| 설치 형태 | 단일 바이너리, `curl \| sh` | 단일 바이너리, upstream 컴포넌트를 static pod로 | 단일 바이너리, `k0sctl`로 선언적 구성 | upstream 표준 도구, 수동 |
| Control Plane 실행 방식 | 단일 프로세스에 통합 | **static pod (kubelet 관리)** — upstream과 동일 | 단일 프로세스 | static pod |
| HA etcd | embedded etcd 3서버 | embedded etcd 3서버 | embedded etcd 3컨트롤러 | 수동 구성 (stacked/external) |
| 번들 컴포넌트 | CoreDNS, Traefik, ServiceLB, local-path, metrics-server, Helm controller | CoreDNS, Canal(Calico+Flannel), NGINX Ingress, metrics-server, Helm controller | CoreDNS, kube-router 또는 Calico | **없음** — 전부 직접 |
| 메모리 오버헤드(서버 노드) | 가장 낮음 (~0.5GB) | 중간 (~1.0GB, static pod 다중 프로세스) | 낮음 (~0.6GB) | 중간 (~1.0GB) |
| 보안 하드닝 | 기본 수준 | **CIS Benchmark 프로파일 · FIPS 140-2 내장** | 기본 수준 | 직접 (kube-bench 등) |
| 업그레이드 | `system-upgrade-controller` 또는 바이너리 교체 | 동일 | `k0sctl apply` | `kubeadm upgrade` 수동 순차 |
| 인증서 갱신 | 재시작 시 자동 (만료 90일 이내) | 동일 | 자동 | **수동** (`kubeadm certs renew`, 1년 만료) |
| 학습 전이성 | 높음 (kubectl·API 동일), 컴포넌트 내부 구조는 다름 | **가장 높음** (upstream 구조 그대로) | 높음 | **최고** (CKA 시험 환경과 동일) |
| 실무 채택 맥락 | 엣지·소규모·개발, 국내 스타트업 자체운영 | 금융·공공·규제 환경 온프레미스 | 상대적으로 사례 적음 | 대기업 온프레미스, 시험 |

### Talos Linux — 2026년의 정석이지만 가비아에서 막힌다

**먼저 인정한다. 초판에서 Talos를 검토하지 않았다.** 2026년 자체 운영 Kubernetes의 사실상
정석은 Talos이므로 이건 누락이었다.

| Talos의 장점 | 이 설계에 주는 의미 |
| --- | --- |
| 불변(immutable) OS. **SSH·셸·패키지 매니저가 없다** | 공격면이 극적으로 작다. §1.5의 Tailscale·SSH 통제 설계 상당 부분이 불필요해진다 |
| 머신 설정 전체가 선언형 YAML, gRPC API로 적용 | **L2(Ansible)가 아예 사라진다.** §2.8의 3층 구조가 2층으로 줄어든다 |
| 공식 `siderolabs/talos` Terraform provider | L1·L2를 하나의 IaC로 다룰 수 있다 |
| etcd·kubelet·인증서 전부 API로 관리 | 업그레이드·노드 교체가 선언적 조작이 된다 |

**가비아에서 쓸 수 없는 이유** — Talos는 전용 디스크 이미지로 부팅해야 한다. 가비아 Gen2의
서비스 목록에서 `이미지`는 **자기 서버 스냅샷 파생만** 가능하고, OS 카탈로그는
Rocky Linux / Ubuntu / Windows뿐이다. **ISO·raw 디스크 이미지 업로드 항목이 존재하지 않는다.**

따라서 결론은 "Talos가 나쁘다"가 아니라 **"가비아의 이미지 카탈로그 제약으로 배제"** 다.
§1.6 문의 항목에 **커스텀 이미지 업로드 가능 여부**를 넣었고, 가능하다면 설계를 Talos로
바꾸는 편이 2026 기준으로 더 낫다. 판단을 뒤집을 만한 항목이므로 Phase 0에서 확인한다.

### 판단: K3s 유지 — 단, 근거를 바꾼다

원본은 “번들 컴포넌트가 있어 편하다”를 주된 근거로 삼았다. 이건 약한 논거다. 편의성은
아키텍처 결정의 근거가 되기 어렵고, 실제로 이번 설계에서는 번들 Traefik·ServiceLB를
**둘 다 끄고** GitOps로 관리한다(§2.4). 진짜 근거는 셋이다.

**1) 9개월의 병목은 도구 학습이 아니라 운영 사이클 완주다.**
크레딧 만료가 확정된 9개월 안에 프로비저닝 → 배포 → 관측 → 백업 → 장애 훈련 → 이관까지
한 바퀴를 돌아야 한다. kubeadm HA는 여기서 순수 오버헤드를 만든다. Control Plane 앞단 LB
구성, stacked etcd 관리, **1년 만료 인증서 수동 갱신**, `kubeadm upgrade` 순차 절차를 직접
설계·문서화하는 데 최소 3~4주가 든다. 그 시간은 Aligner 서비스 운영 경험으로 치환되지 않는다.

**2) “실무 K8s 관리 경험”의 핵심은 배포 도구가 아니라 그 위의 운영이다.**
etcd 백업·복구, 노드 교체, 무중단 업그레이드, RBAC, NetworkPolicy, 스케줄링·자원 압박 대응,
PVC 노드 종속성 — 이 전부가 K3s에서 동일하게 발생하고 동일하게 배운다. kubectl과 API는
upstream과 같으므로 워크로드 레벨 경험은 100% 전이된다. K3s가 감춰주는 건 “컴포넌트를
프로세스로 어떻게 띄우는가”뿐이고, 그건 아래 3)으로 해결한다.

**3) Control Plane 오버헤드 절감분이 그대로 JVM heap이 된다.**
총 24GB에서 노드당 0.5GB(K3s) 대 1.0GB(RKE2/kubeadm)의 차이는 클러스터 전체로 1.5GB,
즉 **Spring Boot 파드 1개분**이다. 6 vCPU 환경에서 Control Plane CPU 절감도 무시할 수 없다.

**kubeadm 학습은 분리한다.** 운영 클러스터를 학습 실험장으로 쓰지 않는다는 원칙은 원본이
CNI에 적용한 것과 같다. `kubernetes-the-hard-way`(kelseyhightower)는 컴포넌트를 손으로
조립하며 CA·kubeconfig·etcd·apiserver 플래그를 이해하는 데 최적이고, **로컬 노트북의
멀티패스/VM 3대 또는 무료 티어에서 비용 0으로 수행 가능**하다. 크레딧을 여기에 태울 이유가 없다.
Phase 2 여유 시간에 별도 트랙으로 진행할 것을 권한다.

**RKE2 전환 조건** — 다음 중 하나가 생기면 RKE2가 더 낫다.

- CIS Benchmark 준수나 보안 감사 요구가 생김 (RKE2는 프로파일 하나로 적용)
- upstream 컴포넌트 구조를 그대로 다뤄야 하는 요구 (static pod, `/etc/kubernetes/manifests`)
- 노드 메모리가 16GB 이상으로 올라가 오버헤드 차이가 무의미해짐

**k0s 탈락** — 기술적으로 K3s와 대등하고 `k0sctl` 선언적 구성은 매력적이지만, 국내 운영 사례와
한국어/영어 트러블슈팅 자료가 K3s·RKE2에 비해 얇다. 9개월 단기전에서 “막혔을 때 검색해
나오는 양”은 실질적인 선정 기준이다.

### K3s 부트스트랩 설정

```yaml
# /etc/rancher/k3s/config.yaml (모든 server 노드)
data-dir: /mnt/k3s                # Data-A 볼륨 — etcd fsync를 앱 I/O와 물리 격리 (§1.4)
secrets-encryption: true          # ★ etcd 저장 시 Secret 암호화 (§2.6)
tls-san:                          # 관리자는 WireGuard 경유 사설 IP로 접근 (§1.5)
  - {{ k3s_node_ips[0] }}
  - {{ k3s_node_ips[1] }}
  - {{ k3s_node_ips[2] }}
  - k8s-api.aligner.internal
node-taint: []                    # 통합형: server도 워크로드 실행
disable:
  - traefik                       # Argo CD가 Helm으로 관리 (§2.4)
  - servicelb                     # 가비아 External LB와 역할 중복
etcd-snapshot-schedule-cron: "0 */6 * * *"   # 6시간마다
etcd-snapshot-retention: 28                  # 로컬 7일치
etcd-s3: true                                # Cloudflare R2 hot/etcd/ (S3 호환)
kubelet-arg:
  - "system-reserved=cpu=200m,memory=1Gi"    # K3s server 프로세스 실사용 ~700Mi 반영
  - "kube-reserved=cpu=200m,memory=512Mi"
  # ★ eviction-hard 는 일부만 지정하면 나머지 기본값이 유지되지 않는다 — 전 항목 명시
  - "eviction-hard=memory.available<300Mi,nodefs.available<10%,nodefs.inodesFree<5%,imagefs.available<15%,imagefs.inodesFree<5%"
  # ★ 이미지가 Data-A(25GB)에 쌓이므로 GC 임계를 명시한다 (§1.4)
  - "image-gc-high-threshold=75"
  - "image-gc-low-threshold=60"
kube-apiserver-arg:
  - "audit-policy-file=/etc/rancher/k3s/audit-policy.yaml"   # 정책 없이 전량 기록 금지
  - "audit-log-path=/var/log/k3s-audit.log"
  - "audit-log-maxage=7"
  - "audit-log-maxbackup=5"
  - "audit-log-maxsize=100"                                  # MB — 회전 없으면 디스크가 찬다
```

> **`node-taint: []`는 설정하지 않는다.** 통합형이므로 taint를 안 걸면 되고, 빈 배열을 명시해서
> 얻는 이점이 없다. (4판 초안에서 삭제)

> **`imagefs`는 별도 파일시스템이 아니다.** `data-dir: /mnt/k3s`이므로 이미지와 kubelet이
> 같은 Data-A에 있다. 위 `imagefs.*` 임계는 실질적으로 `nodefs`와 같은 볼륨에 걸린다(§1.4).
> Phase 1에서 `kubectl describe node`의 `imagefs` 감지 여부를 실제로 확인한다.

> **`audit-policy.yaml`은 최소 정책으로 시작한다.** 정책 파일 없이 모든 이벤트를 남기면
> 2 vCPU 노드에서 I/O 비용이 크다. `RequestResponse`는 Secret·RBAC 변경에만, 나머지는
> `Metadata` 수준으로 둔다.

K3s의 **etcd snapshot S3 직접 업로드는 내장 기능**이다. R2는 S3 API 호환이므로
`etcd-s3-endpoint`만 R2 엔드포인트로 지정하면 그대로 동작한다. 원본이 계획한 "로컬 스냅샷 후
주 1회 수동 업로드" 대신 처음부터 외부로 보내고 로컬은 복구 속도용 캐시로만 둔다. 별도 CronJob이
필요 없다.

> ⚠️ **스냅샷만으로는 복구되지 않는다.** `/var/lib/rancher/k3s/server/token`을 함께 백업해야
> 한다. 이것이 데이터스토어 내부의 기밀 데이터를 암호화하는 키다. §2.5.2 참조.

`system-reserved` 메모리를 **1Gi**로 잡은 이유는 통합형 노드에서 kube-apiserver·etcd·scheduler·
controller-manager가 `k3s.service` 프로세스로 약 700Mi를 쓰기 때문이다. 512Mi로 잡으면 예약이
부족해 초과분이 파드 공간을 침식한다. 이 값이 §3.5 자원 검증의 전제다.

> ⚠️ `system-reserved`·`kube-reserved`는 **allocatable 계산에만 반영되고 자원을 전용으로
> 확보하지 않는다.** 실제 격리에는 `--enforce-node-allocatable`과 reserved cgroup 지정이
> 필요하다. §1.2.2의 `CPUWeight`도 경합 시 상대적 우선순위이지 보장이 아니다.
> **Phase 1에서 다음을 실측해 검증한다.**
>
> ```text
> - cgroup v2 활성 여부 (stat -fc %T /sys/fs/cgroup)
> - k3s.service의 실제 cgroup 경로 (systemctl show k3s -p ControlGroup)
> - kubepods 와 system.slice 간 CPU 경쟁 실험 (stress-ng + API 부하)
> - 그 상태에서 etcd WAL fsync p99 열화 정도
> - kubectl describe node 의 Allocatable 실측값으로 §3.5 표 교체
> ```

---

## 2.2 GitOps — Flux CD vs Argo CD → **Argo CD로 변경**

### 비교

| 기준 | Flux CD | Argo CD |
| --- | --- | --- |
| 구성 요소 | source / kustomize / helm / notification controller | api-server, repo-server, application-controller, redis, (dex) |
| 메모리 (최소 구성) | 약 150~250MB | **미확정 — 초기 request 300Mi, Phase 1 실측** |
| UI | 없음 (`flux` CLI, 별도 Weave GitOps) | **내장 Web UI** — 리소스 트리·live diff·sync 이벤트 |
| 동기화 모델 | pull, 컨트롤러별 CR (`GitRepository` + `Kustomization` + `HelmRelease`) | pull, `Application` CR (app-of-apps 패턴) |
| SOPS 복호화 | **kustomize-controller에 내장** | **내장 없음** — ksops·avp 등 플러그인 필요 |
| Helm 처리 | helm-controller가 실제 Helm 릴리스로 설치 | 기본은 `helm template` 렌더링 (릴리스 아님) |
| 이미지 자동 갱신 | image-reflector/automation controller (선택) | Argo CD Image Updater (별도) |
| 점진 배포 | Flagger | **Argo Rollouts** (카나리·블루그린) |
| 공격면 | 노출 엔드포인트 없음 | api-server 노출 시 인증·RBAC 관리 필요 |
| 팀 협업 | Git·CLI 숙련자 중심 | 비운영 파트도 배포 상태 확인 가능 |

### 판단: Argo CD 채택

원본의 Flux 선택 근거는 “단일 클러스터·소수 운영자에서 더 단순하고 가볍다”였다. 이 문장은
사실이지만 결론을 뒤집는 요인이 세 개 있다.

**1) 프로젝트 정본 문서가 이미 Argo CD를 명기하고 있다.**
`README.md`의 기술 스택에 “인프라 — K3s 기반 HA Kubernetes (3 노드), **ArgoCD**”가 적혀 있다.
원본 인프라 보고서(Flux)와 프로젝트 정본(Argo CD)이 **불일치 상태**다. `AGENTS.md`는
“정본과 다르면 정본을 따른다”를 규칙으로 두고 있으므로, 인프라 보고서 쪽을 정본에 맞추는 것이
맞다. 반대로 Flux로 가려면 README를 먼저 고쳐야 한다.

**2) 원본이 Flux를 고른 물리적 이유(메모리)가 사라졌다.**
차이는 약 350MB다. 12GB 클러스터에서 350MB는 3%로 유의미했지만, 24GB에서는 1.5%다.
반면 UI가 주는 값은 규모와 무관하게 일정하다.

**3) 팀 구성이 UI를 요구한다.**
Server 2명(이강혁·이동훈), Web 3명, PM·Design 2명이다. 배포 상태를 확인해야 하는 사람이
kubectl 사용자보다 많다. “API가 배포됐는지”를 Web 파트가 직접 확인할 수 있으면
커뮤니케이션 비용이 줄고, 이건 5인 이상 팀에서 실측되는 이득이다. 또한 K8s 학습 국면에서
**live manifest와 Git 사이의 diff를 눈으로 보는 것**은 GitOps 개념 습득에 큰 차이를 만든다.

**Argo CD 채택의 대가는 정직하게 인정한다** — SOPS 내장 지원 상실이다. Flux
`kustomize-controller`는 SOPS를 내장하지만 Argo CD는 없다. 이것이 §2.6에서 Secret 전략을
바꾸는 직접 원인이다. 두 결정은 독립적이지 않다.

### 구성

```text
GitHub Actions (CI)
├─ ./gradlew build + ktlintCheck + integrationTest (TestContainers)
├─ 컨테이너 이미지 빌드 (Paketo buildpack, CDS 활성화 — §3.2)
├─ Trivy 취약점 스캔 (HIGH·CRITICAL에서 실패)
├─ GHCR push  →  ghcr.io/.../aligner-api@sha256:...
└─ GitOps 저장소의 kustomization.yaml 이미지 digest 갱신 (PR 또는 직접 커밋)
                            ↓
Argo CD (app-of-apps)
├─ infrastructure/controllers/ : traefik · cert-manager · external-secrets · cloudnative-pg · alloy
├─ database/   : CNPG Cluster, Redis                                          (sync-wave 2)
└─ aligner/    : API Deployment, Service, HTTPRoute, HPA, PDB                 (sync-wave 3)
                            ↓
Kubernetes (automated sync · prune · selfHeal)
```

- 자체 애플리케이션은 **Kustomize**, 외부 솔루션은 **Helm**(Argo CD가 렌더링)으로 관리한다.
  `AGENTS.md`의 “Kustomize + Helm” 방침을 그대로 유지한다.
- 이미지는 **digest 고정**. `latest` 금지. Argo CD Image Updater는 초기에 쓰지 않는다 —
  “Git이 유일한 진실”을 흐리고, 배포 시점 통제가 필요한 P0 단계에 적합하지 않다.
- `syncPolicy.automated.prune: true`, `selfHeal: true`. 수동 `kubectl apply`를 되돌려
  드리프트를 원천 차단한다.
- **Argo CD UI 보안** — api-server를 인터넷에 그대로 노출하지 않는다. 기본은 Tailscale 경유
  접근(`kubectl port-forward` 또는 Tailscale Ingress)이고, 팀 공유가 필요하면 Traefik
  `HTTPRoute` + **GitHub OAuth(Dex) + RBAC + `admin` 계정 비활성화**를 필수로 함께 적용한다.
  인증 없는 Argo CD 노출은 클러스터 전체 권한 유출과 동등하다.

---

## 2.3 CNI — Flannel VXLAN vs Cilium (eBPF)

| 기준 | Flannel VXLAN | Cilium (eBPF) |
| --- | --- | --- |
| 데이터패스 | VXLAN 오버레이 + iptables | eBPF, kube-proxy 대체 가능 |
| 노드당 리소스 | ~50MB / 거의 0 CPU | **실사용량 미확정.** 공식 Helm 기본값은 `resources: {}` → 초기 request 300Mi, **Phase 1 실측 후 교체** |
| NetworkPolicy | 표준 `NetworkPolicy` (K3s 내장 컨트롤러) | 표준 + `CiliumNetworkPolicy` (L7·DNS·FQDN) |
| 관측성 | 없음 (tcpdump 수준) | **Hubble** — 흐름 단위 가시성 |
| K3s 통합 | **기본 제공** | `flannel-backend=none` + `disable-network-policy` + (선택) `disable-kube-proxy` 후 수동 설치 |
| 장애 시 진단 | 이해할 표면이 좁음 | eBPF·커널 버전·맵 상태까지 봐야 함 |
| 교체 리스크 | — | CNI는 클러스터 생애 전체의 기반. 사후 교체 비용 최대 |

### 판단: **Cilium을 Day 1부터 최소 구성으로 채택한다**

> ⚠️ **3판에서 "Flannel 9개월 고정"으로 정했던 것을 4판에서 다시 뒤집는다.** 번복이 잦았으므로
> 각 판의 근거를 남긴다.
>
> | 판 | 결론 | 근거 | 문제 |
> | --- | --- | --- | --- |
> | 1판 | Flannel 고정 | "eBPF 이득이 이 규모에서 계측되지 않음" | 자원 수치를 출처 없이 인용 |
> | 2판 | Phase 3에 Cilium 전환 | GitHub 별점, "2026 표준", 채용 시장 | **아키텍처 근거가 아니다** |
> | 3판 | Flannel 9개월 고정 | 운영 중 데이터플레인 교체 위험 | 교체 위험은 맞지만 **Day 1 채택을 검토하지 않았다** |
> | **4판** | **Day 1 Cilium** | 아래 | — |
>
> **결정적 논거는 "신규 클러스터"라는 사실이다.** 3판이 옳게 지적한 것은 "운영 중 CNI를 바꾸지
> 말라"였고, 그 지적은 **"그럼 처음부터 무엇으로 시작할 것인가"** 를 남겼다. Cilium으로 갈
> 가능성이 있다면 `Flannel → 나중에 Cilium`보다 `처음부터 Cilium`이 안전하다.
>
> **유보를 풀어준 실측 근거 — OS 커널 버전.** Cilium은 커널 5.10+를 권장한다. Rocky 8.10은
> 4.18이라 eBPF 기능이 제한된다. 가비아 `/api/v1/images`를 조회한 결과 선택지가 충분하다.
>
> ```text
> Rocky-9.6 / Rocky-9.5   커널 5.14   ✓  ← 채택
> Ubuntu-24.04            커널 6.8    ✓
> Ubuntu-22.04            커널 5.15   ✓
> Rocky-8.10              커널 4.18   ✗  선택하지 않는다
> ```
>
> **1판의 자원 수치를 정정한다.** "Cilium agent 400~600MB" 및 "250~350MB"는 출처 없는 값이었다.
> Cilium 공식 Helm 기본값은 agent `resources: {}`로 **강제 request가 없다.** 실사용량은 측정해
> 직접 설정해야 한다. 본 설계는 초기값을 보수적으로 잡고 Phase 1에서 실측 교체한다.

### 채택 근거

| # | 근거 | 평가 |
| --- | --- | --- |
| 1 | **신규 클러스터** — 마이그레이션 리스크를 아예 만들지 않는다 | **결정적** |
| 2 | NetworkPolicy가 Phase 1 필수 요구 | Flannel + K3s 내장 kube-router 컨트롤러도 표준 L3/L4 정책은 지원한다. **이것만으로는 Cilium 근거가 약하다.** 다만 L7·DNS·FQDN 확장 경로가 열려 있는 것은 이득 |
| 3 | **Hubble 네트워크 관측성** — 장애 훈련이 이 프로젝트의 명시 목표 | **조건부.** Hubble을 끄면 이 근거는 성립하지 않는다. 아래 구성에서 **agent 메트릭만 켠다** |
| 4 | 최소 구성이면 현재 사양에서 감당 가능 | 자원 영향 §3.5 참조 (degraded 여유 80% → 87%) |

### 채택할 최소 구성

```yaml
# files/cilium-values.yaml — 켜지 않는 것을 명시하는 것이 핵심이다
routingMode: tunnel
tunnelProtocol: vxlan              # 기본 8472/UDP — Flannel 과 같은 포트다
ipam:
  mode: cluster-pool
  operator:
    clusterPoolIPv4PodCIDRList: ["10.42.0.0/16"]   # ★ K3s cluster-cidr 과 일치. 사후 변경 불가
    clusterPoolIPv4MaskSize: 24
kubeProxyReplacement: false        # kube-proxy 유지 (deprecated 'partial' 표기 삭제)
prometheus:
  enabled: true
operator:
  replicas: 2
  prometheus: { enabled: true }
  resources:
    requests: { cpu: 50m, memory: 128Mi }
hubble:
  enabled: true
  relay: { enabled: false }        # Relay·UI 는 끈다
  ui:    { enabled: false }
  metrics:
    enableOpenMetrics: true
    enabled:                       # ★ agent 메트릭만 — 채택 근거 3번을 실제로 회수한다
      - dns
      - drop
      - policy:sourceContext=workload-name|reserved-identity;destinationContext=workload-name|reserved-identity
      # tcp · flow · port-distribution 은 Phase 1 에서 켜지 않는다 (카디널리티, 아래 참조)
encryption:
  enabled: false                   # 문의 B3(사설망 테넌트 격리) 답변 후 결정
clustermesh:
  useAPIServer: false
l7Proxy: false                     # 초기 미사용
resources:                         # 공식 기본값은 {} — 실측 전 보수적 초기값
  requests: { cpu: 100m, memory: 300Mi }
```

> ⚠️ **초판의 metrics 설정 문자열이 틀렸다.** `"policy:sourceContext=app|dest_pod"`에서
> **`dest_pod`는 존재하지 않는 context 키다.** 유효한 키는 `sourceContext`,
> `destinationContext`, `labelsContext`이고 값으로 `pod`, `workload-name`, `namespace`,
> `app`, `reserved-identity` 등을 쓴다.
>
> **Helm values의 문자열 escaping이 도구에 따라 달라질 수 있으므로**(`;`와 `|`가 포함된다)
> Phase 1에서 실제 적용 결과를 `cilium config view`와 `kubectl get cm cilium-config`로
> 확인한다. 문제가 생기면 **dynamic metrics ConfigMap** 방식으로 전환한다 — 설정 검증과
> 카디널리티 제어가 쉽다.

**카디널리티 통제 — Grafana Cloud 무료 티어와 직결된다**

Hubble flow 메트릭은 고카디널리티가 되기 쉽다. §2.7에서 Spring Boot 메트릭 카디널리티를
통제한 것과 같은 이유로 Hubble도 제한한다.

```text
Phase 1 에 켜는 것       dns · drop · policy
                        context 는 workload-name (pod 아님 — 파드 재생성마다 새 시리즈)
Phase 1 에 켜지 않는 것  flow · tcp · port-distribution · httpV2
                        flow 는 파드 조합 수만큼 시리즈가 생긴다
확장 조건               Grafana Cloud 활성 시리즈 여유를 확인한 뒤 하나씩 추가
```

**스크레이프 경로** — `metrics.enabled`가 비어 있지 않으면 Cilium이 **`hubble-metrics`
headless Service**를 생성한다. Alloy는 그 Service의 scrape annotation을 발견하도록 설정한다.
초판이 "pod annotation으로 스크레이프"라고 단정한 것은 부정확했다. `serviceMonitor`를 쓰지
않으므로 Alloy의 `discovery.kubernetes` role을 `service`(또는 `endpoints`)로 두고
`hubble-metrics`를 대상으로 잡는다. Phase 1에서 실제 수집 여부를 확인한다.

**정책은 표준 `NetworkPolicy`만 쓴다.** `CiliumNetworkPolicy`는 L7·FQDN이 실제 요구가 될 때만
도입한다. 벤더 CRD를 초기부터 쓰면 이식성을 잃는다.

```yaml
# /etc/rancher/k3s/config.yaml
flannel-backend: none
disable-network-policy: true
# disable-kube-proxy 는 설정하지 않는다 (kube-proxy 유지)
```

### 부트스트랩 순서 — Cilium은 Ansible이 클러스터 밖에서 설치한다

`flannel-backend: none`이면 클러스터가 **CNI 없이 뜨고 노드가 `NotReady`** 상태다. 이 상태에서는
일반 파드가 스케줄되지 않는다.

> ⚠️ **4판 초안의 "HelmChart CR로는 구조적으로 불가능하다"는 서술을 철회한다. 사실이 아니었다.**
>
> K3s helm-controller의 `HelmChart` CRD에는 **`spec.bootstrap: true`** 가 있고 주석이 용도를
> 명시한다 — *"Set to True if this chart is needed to bootstrap the cluster (Cloud Controller
> Manager, CNI, etc)."* 설치 Job이 다음으로 실행된다.
>
> ```go
> // helm-controller pkg/controllers/chart/chart.go
> if chart.Spec.Bootstrap {
>     job.Spec.Template.Spec.NodeSelector[...ControlPlane] = "true"
>     job.Spec.Template.Spec.HostNetwork = true                      // ← CNI 없이 동작
>     job.Spec.Template.Spec.Tolerations = []corev1.Toleration{
>         { Key: corev1.TaintNodeNotReady, Effect: TaintEffectNoSchedule }, ... }
> ```
>
> `hostNetwork: true` + `node.kubernetes.io/not-ready` toleration이 **CNI 부트스트랩을 위해
> 의도적으로 설계돼 있다.** `bootstrap: true`인 HelmChart로 Cilium을 설치할 수 있다.
> 단 **`bootstrap: true`를 빠뜨리거나 커스텀 taint를 쓰면 실패한다.**

**그럼에도 Ansible + helm을 택한다. 근거는 기술적 불가능이 아니라 운영 책임이다.**

| 근거 | 내용 |
| --- | --- |
| 공식 절차 일치 | Cilium 공식 K3s 가이드가 `KUBECONFIG` 설정 후 클러스터 밖에서 설치하는 방식을 제시한다 |
| **실패 시 즉시 중단** | helm 실패가 Ansible 태스크 실패로 드러난다. HelmChart CR은 Job 로그를 따로 봐야 한다 |
| 파일 동기화 불필요 | auto-deploy 매니페스트는 server 간 자동 동기화되지 않아 3노드 checksum 관리가 필요하다 |
| 책임 분리 | K3s helm-controller는 번들 컴포넌트용으로 남기고 플랫폼은 Ansible(L2)·Argo CD(L3)가 소유 |
| values 단일 소스 | `files/cilium-values.yaml`이 Git에 하나만 존재한다 |

**`bootstrap: true` HelmChart로 전환할 조건** — 노드 교체를 자동화해 **CNI 자동 재적용**이
더 중요해지면 검토한다. 현재는 노드 교체가 수동 절차이므로 Ansible이 낫다.

**채택: Ansible이 컨트롤 노드에서 helm을 실행한다.**

```yaml
# ansible/roles/cilium/tasks/main.yml
- name: kubeconfig 를 컨트롤 노드로 가져온다
  ansible.builtin.fetch:
    src: /etc/rancher/k3s/k3s.yaml
    dest: "{{ playbook_dir }}/../.tmp/kubeconfig"
    flat: true
  delegate_to: "{{ groups['k3s_first_server'][0] }}"

- name: Cilium 설치 (컨트롤 노드 실행 — CNI 없이도 동작한다)
  delegate_to: localhost
  kubernetes.core.helm:
    name: cilium
    chart_ref: cilium/cilium
    chart_version: "{{ cilium_version }}"        # Git 에 고정
    release_namespace: kube-system
    values: "{{ lookup('file', 'files/cilium-values.yaml') | from_yaml }}"
    kubeconfig: "{{ playbook_dir }}/../.tmp/kubeconfig"
    wait: true
    wait_timeout: 10m
```

**부수 이득 — 3노드 manifest 동기화 문제가 사라진다.** 초안이 요구한
"세 노드에 동일 `cilium.yaml` 배포 + SHA-256 checksum 대조 + drift 점검"이 **불필요해진다.**
`files/cilium-values.yaml`이 Git의 단일 소스이므로 노드별 drift가 구조적으로 발생할 수 없다.

**부트스트랩 순서**

```text
1. k3s-01 만 cluster-init 으로 설치 (flannel-backend: none)
      → NotReady, CoreDNS Pending. 정상이다.
2. kube-apiserver 응답 확인 (kubectl get --raw='/readyz')
3. ★ Ansible → helm 으로 Cilium 설치 (컨트롤 노드에서)
4. k3s-01 Ready 확인 → CoreDNS 기동
5. k3s-02·03 을 server 로 조인 → etcd 멤버 3개 확인
6. cilium status --wait / cilium connectivity test
7. 자원 Gate 실측 (§도입 Gate) → 통과 후에만 다음 단계
8. LB → Traefik → cert-manager → Argo CD → NetworkPolicy → CNPG → API → Alloy
```

**Cilium은 L2(Ansible) 소유로 남긴다.** CNI를 GitOps가 관리하면 잘못된 sync 한 번이 클러스터
네트워크 전체를 끊고, 그 상태에서는 Argo CD로 되돌릴 수도 없다. "IaC는 kubeconfig가 나오는
지점까지, 그 이후는 GitOps"라는 §2.8의 원칙에서 **CNI는 예외**다.

### ⚠️ Pod CIDR은 Day 1에 확정해야 하고 사후 변경이 불가능하다

`ipam.mode: cluster-pool`은 **Cilium operator가 `v2.CiliumNode`로 per-node PodCIDR을 독자
관리**한다. Kubernetes가 per-node PodCIDR을 배분하는 것에 의존하지 않으므로 **K3s의
`cluster-cidr`을 자동으로 따라가지 않는다.** Cilium 기본값은 `10.0.0.0/8`이다.

우리는 **kube-proxy를 유지**하므로(`kubeProxyReplacement: false`) K3s가 kube-proxy·
controller-manager에 전달하는 `cluster-cidr`과 실제 Pod IP가 어긋나면 masquerade 판단이 틀어진다.
**반드시 일치시킨다.**

```yaml
# files/cilium-values.yaml — Day 1 에 확정. 이후 변경 불가
ipam:
  mode: cluster-pool
  operator:
    clusterPoolIPv4PodCIDRList: ["10.42.0.0/16"]   # K3s cluster-cidr 과 동일
    clusterPoolIPv4MaskSize: 24                    # 노드당 254 IP · /16 안에 256 블록
```

> **공식 문서가 사후 변경을 금지한다.**
> "Don't change any existing elements of the `clusterPoolIPv4PodCIDRList` list, as changes cause
> unexpected behavior. (…) Changing `clusterPoolIPv4MaskSize` is also not possible."
>
> 풀이 소진되면 **기존 요소를 수정하지 않고 새 요소를 추가**해야 한다. 3노드 × /24 = 762 Pod IP로
> 현재 규모(파드 33개)에 충분하며, 노드 증설 여유도 253 블록이 남는다.

**Gate 실패로 Flannel로 재생성할 때도 같은 `10.42.0.0/16`을 쓴다.** CIDR 계획은 CNI 선택과
무관하게 재사용된다.

**VXLAN 포트** — Cilium VXLAN도 기본 **8472/UDP**다. Flannel과 같은 포트이므로 "Flannel을 안 쓰니
8472를 닫아도 된다"는 판단은 틀렸다. 포트는 그대로 필요하고 사용 주체만 바뀐다.
보안그룹에서 **노드 사설 대역 한정**으로 유지한다(§1.5).

### Phase 1의 NetworkPolicy는 미루지 않는다

```text
default-deny-ingress + default-deny-egress (모든 애플리케이션 namespace)
├─ aligner-api      ← Traefik namespace 에서만 인바운드 허용
├─ postgres (CNPG)  ← aligner-api, cnpg-operator 에서만 5432 허용
├─ redis            ← aligner-api 에서만 6379 허용
├─ management(8081) ← kubelet(probe), Alloy(scrape) 에서만
└─ egress           → 아래 참조
```

> ### ⚠️ 표준 NetworkPolicy로는 FQDN을 제한할 수 없다 — 초판 오류 정정
>
> 초판은 egress를 "CoreDNS(53), 외부 443만 허용"이라 쓰고 다른 절에서 `*.grafana.net`·
> `*.r2.cloudflarestorage.com` 같은 **도메인 단위 제한을 시사**했다. **표준 Kubernetes
> NetworkPolicy는 목적지를 Pod·Namespace·IP CIDR로만 선택한다. FQDN 허용 기능이 없다.**
> 포트(443) 제한은 되지만 "어느 도메인으로"는 통제할 수 없다.
>
> **Phase 1은 단순안을 택한다.**
>
> ```yaml
> # 단순안 — 표준 NetworkPolicy 만 사용 (Phase 1 채택)
> egress:
>   - to: [{ namespaceSelector: { matchLabels: { kubernetes.io/metadata.name: kube-system } } }]
>     ports: [{ protocol: UDP, port: 53 }, { protocol: TCP, port: 53 }]
>   - to:
>       - ipBlock:
>           cidr: 0.0.0.0/0
>           except: [ {{ vpc_cidr }}, 10.0.0.0/8, 172.16.0.0/12 ]   # 사설망 제외
>     ports: [{ protocol: TCP, port: 443 }]
> ```
>
> **장점** — 표준 정책만 쓰므로 Gate 실패로 Flannel로 되돌려도 그대로 동작한다.
> **단점** — 모든 외부 HTTPS 목적지가 허용된다. 침해된 파드가 임의 서버로 데이터를 보낼 수 있다.
>
> **엄격안은 `CiliumNetworkPolicy`의 `toFQDNs`가 필요하다**(R2·Grafana Cloud·GHCR·ACME만 허용).
> 즉 **"초기에는 CiliumNetworkPolicy를 쓰지 않는다"는 결론과 FQDN 통제는 양립하지 않는다.**
> 현재 규모에서는 단순안으로 시작하고, **데이터 유출 통제가 실제 보안 요구가 될 때** Cilium
> 정책으로 확장한다. 그 시점에 이 트레이드오프를 다시 결정한다.

**Gate 실패로 Flannel로 되돌려도 표준 정책은 그대로 동작한다.** 이식성을 위해 Phase 1에서는
벤더 CRD를 쓰지 않는다.

**노드 간 암호화** — 문의 B3(사설망 테넌트 격리) 답변 후 결정한다. 격리가 보장되지 않으면
Cilium의 WireGuard 투명 암호화를 켠다(`encryption.enabled: true, encryption.type: wireguard`).
관리망 WireGuard(§1.5)와는 별개 계층이다.

### 도입 Gate — Phase 1에서 통과하지 못하면 Flannel로 재생성

문서상 채택으로 끝내지 않는다. 다음을 Phase 1 완료 조건에 넣는다.

```text
[기능]
□ cilium connectivity test 전체 통과
□ LB → NodePort → Traefik 경로 정상
□ externalTrafficPolicy: Local 에서 클라이언트 IP 보존 확인
□ default-deny + 명시적 허용 NetworkPolicy 정상 동작
□ CoreDNS·metrics-server·CNPG·Argo CD 전부 정상

[장애]
□ 노드 1대 정지 시 서비스 복구 (Flannel 때와 동일 기준)
□ cilium-agent 재시작 중 기존 TCP 연결 영향 측정
□ cilium-operator 2 replica failover 확인

[자원]
□ 노드별 cilium-agent RSS·CPU 실측 → §3.5 표의 300Mi 초기값 교체
□ **1노드 장애 시 필수 워크로드 request 가 2노드 allocatable 의 85% 이하** (사람 개입 없는 생존)
□ etcd WAL fsync p99 악화 여부 (Flannel 대비)
```

**Gate 실패 시 대응은 "Flannel로 롤백"이 아니라 "클러스터를 다시 생성해 Flannel로 확정"이다.**
운영 시작 후 CNI 교체는 하지 않는다는 원칙은 유지한다. Phase 1에서는 아직 프로덕션 데이터가
없으므로 재생성 비용이 낮다 — 이것이 Day 1에 결정해야 하는 또 하나의 이유다.


## 2.4 Ingress — Traefik vs NGINX Ingress Controller

**이 비교는 2026년 3월에 종료됐다.** `kubernetes/ingress-nginx`는 2026년 3월 은퇴했고 저장소는
read-only다. 이후 릴리스·버그 수정·**보안 취약점 패치가 전혀 없다**. 2026년 8월 시점에 신규
클러스터의 인그레스로 선택하는 것은 알려진 미패치 취약점을 받아들이는 결정이다. 후보에서 제외한다.

### 남은 후보 비교

| 후보 | 평가 |
| --- | --- |
| **Traefik** | K3s 생태계 표준, Ingress·Gateway API·CRD(IngressRoute) 모두 지원, 단일 Go 바이너리(~100MB), 미들웨어(rate limit·헤더·인증)를 CRD로 선언 |
| Envoy Gateway | Gateway API 정통 구현, 기능·성능 우수하나 컨트롤 플레인 + Envoy 프록시 2계층으로 리소스·개념 부담 |
| Cilium Gateway | Cilium을 이미 쓸 때만 타당. §2.3에서 Cilium을 안 쓰므로 탈락 |
| InGate | ingress-nginx 후속 SIG-Network 프로젝트. 성숙도가 아직 프로덕션 기준 미달 |
| NGINX Gateway Fabric | F5 주도, nginx 기반 Gateway API 구현. 대안이나 Traefik 대비 이점 없음 |

### 판단: Traefik — 리소스는 **Gateway API `HTTPRoute`** 로 작성한다

도구 선택은 Traefik이 맞다. **2026-08-06 실측 64,292 stars**로 후보 중 압도적이고
(Envoy Gateway 2,935), K3s 생태계 표준이며 단일 Go 바이너리로 가볍다.

**바꾸는 것은 리소스 종류다.** ingress-nginx 은퇴 이후 2026년 표준은 **Gateway API**이고
`Ingress`는 레거시다. 초판이 Traefik CRD인 `IngressRoute`를 쓴 것은 **벤더 종속**이다.

```text
✗ IngressRoute (Traefik CRD)  → Traefik에 묶인다
✗ Ingress (레거시)             → 기능 표현에 annotation 남용이 필요하다
✓ HTTPRoute (Gateway API)      → 구현체를 갈아탈 때 매니페스트가 그대로 간다
```

`HTTPRoute`로 쓰면 §2.3의 Cilium 전환 시 **Cilium Gateway로 인그레스까지 통합**하거나
Envoy Gateway로 옮길 때 매니페스트를 다시 쓰지 않는다. 두 결정이 맞물린다.

```yaml
# Gateway는 플랫폼 팀이, HTTPRoute는 앱 팀이 소유 — 역할 분리가 스펙에 내장돼 있다
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata: { name: aligner-gw, namespace: traefik }
spec:
  gatewayClassName: traefik
  listeners:
    - name: https
      protocol: HTTPS
      port: 8443                      # NodePort 30443으로 노출
      hostname: "*.aligner.example.com"
      tls:
        certificateRefs: [{ name: aligner-tls }]   # cert-manager가 채운다
      allowedRoutes:
        namespaces: { from: Selector, selector: { matchLabels: { gateway-access: "true" } } }
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata: { name: aligner-api, namespace: aligner }
spec:
  parentRefs: [{ name: aligner-gw, namespace: traefik }]
  hostnames: ["api.aligner.example.com"]
  rules:
    - matches: [{ path: { type: PathPrefix, value: /api } }]
      backendRefs: [{ name: aligner-api, port: 8080 }]
```

Traefik 미들웨어(rate limit 등)가 필요하면 `HTTPRoute`의 `filters`로 표현 가능한 것은
표준으로 쓰고, Traefik 고유 기능만 `ExtensionRef`로 분리한다. 벤더 종속을 한 곳에 격리한다.

### K3s 번들을 끄고 Argo CD가 관리한다

원본은 “K3s 기본 패키지에 포함되어 추가 설치가 필요 없다”를 근거로 삼았다. 이 부분은 바꾼다.
K3s 번들 Traefik은 `HelmChartConfig` CR로만 설정을 덮어쓸 수 있고 **버전이 K3s 버전에 묶인다**.
GitOps를 도입하는 이상 인그레스 버전과 설정이 Git에 없는 상태는 일관성 위반이다.

```text
K3s config.yaml:  disable: [traefik]
Argo CD platform/traefik:  Helm chart (버전 고정) + values.yaml (Git)
```

이렇게 하면 Traefik 업그레이드가 Git PR이 되고, 롤백이 `git revert`가 된다. K3s 업그레이드와
Traefik 업그레이드를 분리할 수 있는 것도 이득이다(Phase 4 업그레이드 리허설에서 중요).

**핵심 설정**

```yaml
deployment:
  replicas: 3                          # 노드당 1개 — externalTrafficPolicy: Local의 전제
providers:
  kubernetesGateway:
    enabled: true                      # ★ Gateway API 활성화
  kubernetesIngressRoute:
    enabled: false                     # 벤더 종속 CRD 비활성화 — HTTPRoute만 쓴다
gateway:
  enabled: false                       # Gateway 리소스는 Git에서 직접 관리 (차트에 위임 안 함)
topologySpreadConstraints:
  - maxSkew: 1
    topologyKey: kubernetes.io/hostname
    whenUnsatisfiable: DoNotSchedule
service:
  type: NodePort
  externalTrafficPolicy: Local         # 클라이언트 IP 보존 + 노드 간 홉 제거
ports:
  web:      { nodePort: 30080, redirectTo: { port: websecure } }
  websecure: { nodePort: 30443 }
podDisruptionBudget:
  enabled: true
  minAvailable: 2                      # 업그레이드 중에도 2노드가 LB 헬스체크 통과
```

`PodDisruptionBudget minAvailable: 2`가 중요하다. Traefik이 1개만 남으면 LB 뒤 정상 노드가
1개로 줄어 단일 장애점이 된다.

**TLS는 cert-manager** — Traefik 내장 ACME는 replica 간 인증서 저장소를 공유하지 못해
3 replica에서 중복 발급·rate limit 문제가 생긴다. cert-manager + Let's Encrypt로 인증서를
Secret에 중앙 관리하고 Traefik이 참조한다. 원본 판단과 동일하다.

---

## 2.5 Storage & Database

### 2.5.1 local-path vs Longhorn

| 기준 | local-path Provisioner | Longhorn |
| --- | --- | --- |
| 노드 요구 사양 | 없음 | **프로덕션 권장 노드당 4 vCPU / 4GiB (V1 Data Engine)** |
| 리소스 점유 | 거의 0 | manager + instance-manager, 복제 동기화 시 CPU·네트워크 상시 소모 |
| 복제 | 없음 — PV가 노드에 고정 | 블록 레벨 replica 2~3, 노드 장애 시 자동 재연결 |
| 장애 시 | 해당 노드 복구까지 PVC 사용 불가 | 다른 노드에서 즉시 attach |
| 백업 | 직접 구성 | S3 백업·스냅샷 내장 |

**판단: local-path 유지.** 메모리는 8GB로 늘었지만 **CPU는 2 vCPU 그대로**이고, Longhorn의
프로덕션 권장 사양(4 vCPU)에 미달한다. instance-manager의 replica 동기화는 CPU 바운드 작업이라
2 vCPU 노드에서 JVM과 정면 경합한다. 스토리지 복제를 얻으려고 애플리케이션 성능을 내주는
교환이다.

**대신 복제를 애플리케이션 계층에서 해결한다** — 이게 이번 설계의 핵심 전환이다.

```text
Longhorn (블록 레벨 복제)          →  PostgreSQL 스트리밍 복제 (논리 계층)
  CPU 비용 큼, 범용                    CPU 비용 작음, DB에 특화
  2 vCPU 노드에서 JVM과 경합            PostgreSQL이 원래 하는 일
```

상태를 가진 워크로드는 사실상 PostgreSQL과 Redis뿐이다. PostgreSQL은 스트리밍 복제로,
Redis는 캐시로만 쓰고 유실을 허용하면(또는 AOF + 재구성) 범용 분산 스토리지가 필요 없다.

**Longhorn 실험은 Phase 4로.** 비핵심 namespace, replica 2, 테스트 데이터로만 검증하고 결과를
문서화한다. 운영 StorageClass로 승격하지 않는다.

### 2.5.2 PostgreSQL — 단일 Primary에서 CNPG HA로

원본은 “12GB 메모리에서 Control Plane·앱·관측성까지 확보해야 하므로 PG 3 replica를 하지
않는다”고 했다. 정확한 판단이었다. **24GB에서는 전제가 바뀐다.**

**채택: CloudNativePG Operator, `instances: 2` — 정확한 명칭은 "single-failure automatic failover"**

> ⚠️ **초판 정정** — 초판은 이 구성을 "PostgreSQL HA"로 불렀다. 과장이다. `instances: 2` +
> local-path PVC는 **노드 1대 장애에서 자동 failover가 되는 구성**이지 완전한 노드 장애
> 내구성이 아니다. §2.5.3에서 한계를 명시한다.

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: aligner-db
spec:
  instances: 2                    # primary 1 + hot standby 1
  imageName: ghcr.io/cloudnative-pg/postgresql:17   # 버전 고정
  primaryUpdateStrategy: unsupervised               # switchover 후 롤링 업데이트

  storage:
    size: 30Gi                    # 데이터 + WAL 하나의 볼륨 (아래 설명)
    storageClass: local-path
  # walStorage 를 쓰지 않는다 — 아래 "WAL 별도 PVC를 제거한 이유"

  affinity:
    enablePodAntiAffinity: true
    topologyKey: kubernetes.io/hostname   # primary와 standby를 다른 노드로 강제

  postgresql:
    parameters:
      max_connections: "120"
      shared_buffers: "512MB"
      effective_cache_size: "1536MB"
      work_mem: "8MB"
      maintenance_work_mem: "128MB"
      wal_compression: "on"
      min_wal_size: "256MB"
      max_wal_size: "1GB"         # checkpoint 빈도 조절용 soft target — 디스크 상한이 아니다
      archive_timeout: "300s"     # ★ RPO 5분 목표의 전제. 저트래픽에서 segment switch 강제

  resources:
    requests: { cpu: 250m, memory: 2Gi }
    limits:   { cpu: 1000m, memory: 2Gi }   # 메모리 requests = limits (QoS는 Burstable)

  # Barman Cloud Plugin → R2: WAL 아카이빙 + 주간 basebackup + PITR
  plugins:
    - name: barman-cloud.cloudnative-pg.io
      parameters:
        barmanObjectName: aligner-r2-backup
```

**WAL 별도 PVC(`walStorage`)를 제거한 이유** — 초판은 `storage: 20Gi` + `walStorage: 5Gi`로
분리했다. 두 가지가 잘못이었다.

1. **같은 물리 SSD면 성능 격리가 되지 않는다.** PVC를 나눠도 디스크 큐는 하나다. WAL flush와
   데이터 파일 write가 여전히 같은 큐에서 경쟁한다. 격리라는 목적을 달성하지 못한다.
2. **5Gi WAL PVC가 새로운 장애 지점이 된다.** 아카이빙이 실패하면 WAL이 누적되는데, 5Gi가
   먼저 차면 **PostgreSQL이 쓰기를 멈춘다.** 데이터 볼륨에는 공간이 남아 있는데도 그렇다.

**진짜 별도 물리 디스크를 붙일 수 있을 때만** WAL 분리를 재검토한다(§1.4 확인 항목).

### ⚠️ `max_wal_size`는 디스크 사용량 상한이 아니다 — 초판 오류 정정

초판은 `max_wal_size: 1GB`를 "누적 상한", "아카이빙 실패 시 무한 증가를 막는 1차 방어선"이라고
썼다. **사실이 아니다.**

```text
max_wal_size 의 실제 의미
  - checkpoint 발생 시점에 영향을 주는 soft target
  - 디스크 사용량의 하드 리밋이 아니다
  - archive_command 가 실패하면 과거 WAL 은 제거되지 않고 pg_wal 에 계속 쌓인다
  - 파일시스템이 가득 차면 PostgreSQL 이 PANIC 으로 종료될 수 있다
```

즉 **아카이빙이 실패하면 `max_wal_size`가 무엇이든 pg_wal이 볼륨을 채운다.** Data-B(40GB)에
PostgreSQL과 Redis가 함께 있으므로 그 볼륨 전체가 마비된다. Data-A 분리(§1.4) 덕분에 etcd는
살아남지만 DB는 죽는다.

**필수 방어선은 파라미터가 아니라 경보와 훈련이다.**

| 방어선 | 내용 | 임계 |
| --- | --- | --- |
| `pg_wal` 실제 사용량 | 디렉터리 크기 직접 감시 | 볼륨의 30% 초과 시 Warning |
| `pg_stat_archiver.failed_count` | 증가 감지 | 1회 증가에도 Warning, 5회 연속 Critical |
| 마지막 WAL archive 성공 시각 | `pg_stat_archiver.last_archived_time` | **15분 경과 시 Critical** (RPO 5분 목표의 3배) |
| Data-B 여유 공간 | 3단 경보 | **60% Info / 75% Warning / 85% Critical** |
| inode 사용률 | WAL 파일 수가 많으면 용량보다 먼저 마른다 | 75% Warning |
| **아카이빙 강제 중단 훈련** | R2 자격증명을 일부러 무효화해 failed_count 증가와 경보 발화, pg_wal 증가 속도를 실측 | Phase 2 필수 |

**`archive_timeout: 300s`을 명시한 이유** — RPO 목표가 5분인데 저트래픽에서는 16MB WAL segment가
오랫동안 완성되지 않아 아카이브가 늦어진다. `archive_timeout`으로 segment switch를 강제해야
RPO가 성립한다. 다만 너무 짧게 잡으면 부분적으로 채워진 segment가 매번 전량(16MB) 업로드되어
R2 저장량과 Class A 연산이 늘어난다. **300초로 시작하고 Phase 2 장애 테스트에서 실제 RPO를
측정해 조정한다.** "RPO 5분"은 설정이 아니라 실측으로 증명해야 하는 값이다.

### 2.5.3 `instances: 2`의 한계와 degraded 절차

```text
정상        노드A: primary(local PVC)   노드B: standby(local PVC)   노드C: PG 없음
노드A 영구 장애
  1. 노드B standby → primary 승격 (자동, 수 초~수십 초)
  2. 노드A의 local PVC는 다른 노드로 attach되지 않는다
  3. CNPG가 노드C에 새 instance를 생성하고 pg_basebackup으로 동기화
     → 데이터 크기에 비례한 시간이 걸린다 (10GB 기준 수 분~수십 분)
  4. 그 사이 클러스터는 단일 PostgreSQL 인스턴스 상태다
```

즉 **failover는 자동이고 redundancy 회복은 자동이지만 즉시가 아니다.** 그 구간에 두 번째
장애가 오면 R2의 basebackup + WAL로 복구해야 하고 RTO는 1시간이 된다.

**degraded 상태의 DB 운영 규칙**

```text
금지  — 스키마 변경, PG 마이너 업그레이드, 노드 drain
필수  — standby 재생성 완료 확인 후 normal overlay로 복귀 (§3.5.2)
측정  — Phase 2 훈련 #3에서 "노드 영구 유실 → standby 재생성 완료" 시간을 실측해 기록
```

**`instances: 3` 검토 조건** — 노드마다 하나씩 두면 1대 장애 후에도 standby가 남는다.
현재 2 × 2Gi = 4Gi이므로, **부하 테스트에서 1.25~1.5Gi로 동작함이 검증되면** 총메모리를
늘리지 않고 3 instances가 가능하다(1.33Gi × 3 = 4Gi). 단 PostgreSQL 메모리는 추정으로 줄이지
않는다. 실제 데이터 크기·쿼리·커넥션 수로 검증한 뒤 Phase 3에서 판단한다.

### ⚠️ Query 서비스를 `-ro`로 보내지 않는다

CNPG는 `-rw`, `-ro`, `-r` 서비스를 자동 생성한다. `docs/architecture.md`의 Command/Query
분리와 맞물려 Query를 `-ro`로 보내고 싶어지지만, **비동기 복제이므로 read-your-writes가
깨진다.**

```text
사용자가 Session을 기록  → -rw (primary)
직후 진행도 조회         → -ro (standby, 복제 지연 수십 ms~수 초)
                          → 방금 기록한 Session이 보이지 않는다
```

Aligner의 핵심 루프(`Screening` 응답 → `Cause` 판별 → `Course` 처방 → `Session` 기록 →
진행도 확인)는 **쓰기 직후 읽기가 연속된다.** 따라서:

```text
기본       모든 트래픽을 -rw 로 보낸다
예외 허용  일관성 요구가 낮은 조회만 명시적으로 -ro
           (예: 운동 정보 마스터 데이터, 코스 템플릿 목록 — 변경 빈도가 낮고 사용자 쓰기와 무관)
금지       Session·Stamp·Course 인스턴스 등 사용자 쓰기 직후 조회되는 데이터
```

**설계 판단**

- **`instances: 2`이고 3이 아닌 이유** — 3 인스턴스는 노드 3개 모두에 PG가 올라가 앱 스케줄링
  여유가 줄고, 현재 요청량(2Gi × 3 = 6Gi)이 §3.5 자원표에서 감당되지 않는다. 2 인스턴스로
  **자동 failover**를 얻고, 세 번째 사본은 R2의 basebackup + WAL이 담당한다.
  **부하 테스트 후 인스턴스당 1.33Gi로 동작하면 3 instances로 전환한다**(§2.5.3).
- **비동기 복제를 쓴다.** standby 1대에 동기 복제(`synchronous_commit=on` +
  `synchronous_standby_names`)를 걸면 standby 장애 시 **primary의 쓰기가 멈춘다**.
  가용성이 오히려 내려간다. Aligner의 데이터 특성(세션 기록·스탬프)은 수 초의 RPO를 허용한다.
- **메모리 `requests = limits = 2Gi`** — PostgreSQL은 `shared_buffers`를 미리 잡고 반납하지
  않으므로 실사용이 request를 초과하면 eviction 순위가 올라간다. JVM과 같은 이유다(§3.1 원칙 1).
  **QoS는 Burstable이다**(CPU가 250m → 1000m).
- **`shared_buffers 512MB`** — 컨테이너 limit 2Gi의 25%. 일반 권장(RAM 25%)을 따르되
  나머지를 OS 페이지 캐시와 work_mem에 남긴다.
- **`max_wal_size 1GB` + `archive_timeout 300s`** — `max_wal_size`는 **checkpoint 빈도를 조절하는
  soft target이고 디스크 상한이 아니다.** 아카이빙 실패 시 pg_wal 증가를 막지 못한다.
  누적 방어는 경보와 훈련으로 한다(위 표). `archive_timeout`은 RPO 5분 목표의 전제다.
- 서비스 라우팅은 **`-rw` 기본**이다. `-ro`는 일관성 요구가 낮은 조회만 명시적으로 쓴다
  (§2.5.3 마지막 항목).

**백업 저장소 선정 — 가비아에는 오브젝트 스토리지가 없다**

가비아 Gen2 전체 서비스 목록에 **오브젝트 스토리지(S3 호환 버킷)가 존재하지 않는다**(§1.6).
파일 저장은 블록 스토리지와 NAS뿐이므로 백업 대상은 외부에서 골라야 한다.

| 후보 | egress(복구 시) | 무료 티어 | S3 API | 재해 격리 | 판정 |
| --- | --- | --- | --- | --- | --- |
| **Cloudflare R2** | **무료** | 10GB | 호환 | ✅ 외부 | **1차 권장** |
| AWS S3 (서울) | 유료 | — | 원본 | ✅ 외부 | 2차 사본 |
| Backblaze B2 | 저장량 3배까지 무료 | 10GB | 호환 | ✅ 외부 | 대안 |
| 가비아 NAS | 내부 무과금 | — | ✗ (NFS) | ❌ 동일 DC | 보조만 |

**Cloudflare R2를 1차로 쓴다.** 근거 셋이다.

1. **egress가 무료다.** 백업은 평소 쓰지 않고 사고 때 대량으로 내려받는 워크로드다. 복구
   비용이 0이면 **복구 훈련을 자주 할 수 있다** — 이 설계의 핵심 원칙(§검증하지 않은 백업은
   백업이 아니다)과 직결된다.
2. **S3 API 호환**이라 K3s `etcd-s3-endpoint`와 CNPG Barman Cloud를 연동할 수 있다(§2.5.4 검증 전제).
3. 가비아 → R2 업로드가 해외 트래픽으로 분류되더라도(§1.6 문의 B1) 백업 업로드량은
   증분 WAL 기준 월 수 GB 수준이므로 무료 50GB 안에 들어갈 여지가 있다. 주간 basebackup이
   커지면 압축·보관 주기로 조절한다.

**가비아 NAS는 1차 저장소로 쓰지 않는다.** 내부 트래픽 무과금은 매력적이지만 같은
데이터센터에 있어 3-2-1 규칙의 "off-site"를 만족하지 못한다. 데이터센터 단위 사고에서
운영 데이터와 백업이 같이 사라진다. 복구 속도용 2차 캐시로만 검토한다.

### 2.5.4 ⚠️ "S3 호환이니 endpoint만 바꾸면 된다"고 가정하지 않는다

초판은 "R2는 S3 API 호환이므로 K3s `etcd-s3-endpoint`와 CNPG Barman Cloud가 엔드포인트·
자격증명만 바꾸면 그대로 동작한다"고 썼다. **과한 단정이다.**

Barman Cloud Plugin은 S3 호환 엔드포인트를 지원하지만 **모든 호환 구현과 인증 조합을 독립적으로
검증하지는 않는다.** 공식 문서도 일부 구현만 테스트됐고, S3 호환 서비스에서는 **checksum 관련
호환 설정이 필요할 수 있다**고 안내한다. R2는 특히 다음에서 AWS S3와 다르게 동작할 수 있다.

```text
□ multipart upload 의 ETag 형식
□ x-amz-checksum-* / trailing checksum 헤더 처리
□ ListObjectsV2 의 페이지네이션·delimiter 동작
□ 조건부 요청(If-Match 등)과 sigv4 서명 세부
□ Bucket Lock 이 걸린 prefix 에 대한 Put·Delete 응답 코드
```

**정확한 표현으로 바꾼다.**

> 프로토콜상 연동 가능하지만, **채택한 CNPG·Barman Plugin·boto3·R2 버전 조합으로 upload,
> WAL archive, list, retention, PITR restore를 acceptance test한 후 확정한다.**

**Phase 1에서 통과해야 하는 R2 acceptance test — 두 개로 분리한다.**

**CNPG Barman 이 통과했다고 K3s 의 S3 클라이언트까지 검증된 것이 아니다.** 서로 다른 구현이므로
따로 시험한다.

```text
[테스트 1] CNPG Barman Cloud → R2
□ basebackup upload 성공 (multipart 경로 포함 — 1GB 이상 파일로 시험)
□ WAL archive 연속 성공 (archive_timeout 300s 하에서 10회 이상)
□ barman-cloud-backup-list 가 목록을 정상 반환
□ barman-cloud-backup-delete 로 retention prune 이 실제 삭제 (hot/cnpg/)
□ PITR restore 성공 — 임의 시점 지정 후 데이터 시점 일치 확인
□ Barman 공식 검증 목록에 R2 가 명시돼 있지 않으므로 checksum 호환 옵션 필요 여부 확인

[테스트 2] K3s etcd snapshot → R2
□ etcd-s3 업로드 성공 (6시간 스케줄 + 수동 save 양쪽)
□ k3s etcd-snapshot ls 로 R2 상의 스냅샷 목록 조회
□ R2 에서 스냅샷 다운로드
□ ★ server token 을 함께 복원해 실제 --cluster-reset-restore-path 복구 성공
   (token 없이 시도해 실패를 재현하는 것도 1회)

[공통]
□ immutable/ prefix 에서 backup-writer 의 Delete 가 거부됨을 확인
□ archiver 자격증명으로 hot/ → immutable/ 복제 성공
□ 위 전부를 통과한 버전 조합(CNPG · Barman Plugin · boto3 · K3s)을 docs/adr 에 기록
```

**실패 시 대안** — AWS S3(서울 리전)를 1차로 올린다. egress 비용이 생기지만
"검증되지 않은 백업 경로"보다 낫다. 그 경우 복구 훈련 빈도를 비용과 함께 재검토한다.

**백업·복구 전략 (RPO / RTO 명시)**

| 대상 | 방식 | 주기 | 보관 | RPO | RTO 목표 |
| --- | --- | --- | --- | --- | --- |
| etcd | K3s 내장 snapshot → **R2** | 6시간 | 로컬 28개(7일) / R2 7일 + 월간 1개 | 6h | 30분 |
| **K3s server token** | **`/var/lib/rancher/k3s/server/token` → 오프클러스터** | 1회 + 변경 시 | 영구 | 0 | — |
| PostgreSQL WAL | Barman Cloud → **R2** | 연속 아카이빙 | 14일 | **5분 이내** | 1시간 |
| PostgreSQL basebackup | Barman Cloud → **R2** | 주 1회 | 4~8개 | — | 1시간 |
| 월 1회 2차 사본 | R2 → AWS S3 복제 (Object Lock) | 월 1회 | 3~6개월 | — | — |
| K8s Manifest | Git (GitOps 저장소) | 커밋마다 | 영구 | 0 | 15분 (Argo CD sync) |
| Infisical Machine Identity credential | 오프라인 암호화 보관 | 1회 + 로테이션 시 | 영구 | 0 | — |
| Secret 원본 | 팀 패스워드 매니저 | 변경 시 | 영구 | 0 | — |
| 컨테이너 이미지 | GHCR (digest 고정) | 빌드마다 | — | 0 | — |

### ⚠️ K3s server token 없이는 etcd 스냅샷을 복구할 수 없다

초판 백업 목록에 이 파일이 없었다. **치명적 누락이었다.** K3s 공식 문서
(`docs.k3s.io/datastore/backup-restore`)의 경고다.

> In addition to backing up the datastore itself, you must also back up the server token file at
> `/var/lib/rancher/k3s/server/token`. You must restore this file, or pass its value into the
> `--token` option, when restoring from backup. **If you do not use the same token value when
> restoring, the snapshot will be unusable, as the token is used to encrypt confidential data
> within the datastore itself.**

즉 스냅샷을 6시간마다 성실히 올려도 **token이 없으면 복구가 불가능**하다. "백업은 도는데
복구가 안 되는" 상태다. Phase 1 완료 조건에 넣고, Phase 4 리허설에서 token 복원부터 시작한다.

### 클러스터 밖에 보관해야 하는 것 — 순환 의존 제거

**클러스터가 죽으면 Kubernetes Secret을 읽을 수 없다.** 그런데 복구에 필요한 R2 자격증명이
클러스터 안 Secret에만 있으면 복구가 시작되지 않는다. 초판에 이 순환 의존이 있었다.

```text
오프클러스터 필수 보관 목록 (팀 패스워드 매니저 + 오프라인 암호화 사본 2중)
├─ K3s server token                          ← 없으면 etcd 복구 불가
├─ Infisical Machine Identity credential           ← ESO Bootstrap. 재발급 가능 (§2.6.7)
├─ K3s secrets-encryption 키 설정            ← §2.6, etcd 암호화 키
├─ 복구용 R2 / S3 자격증명 (restore 권한)     ← 클러스터에 배포하지 않는다
├─ Argo CD 부트스트랩 매니페스트 + repo 접근 토큰
├─ DNS / TLS / LB / 보안그룹 인벤토리
└─ 가비아 콘솔 접근 정보 (2FA 백업 코드 포함)
```

### 백업을 삭제 불가능하게 만든다 — 단, 자동 보존 정리와 충돌하지 않게

외부 저장소에 두는 것만으로는 부족하다. **클러스터가 침해되면 백업을 쓰는 그 자격증명으로
백업을 지울 수 있다.** 그리고 R2에서 **`DeleteObject`는 무료 연산**이므로 공격자에게 비용
부담조차 없다.

> ⚠️ **초판 설계에 모순이 있었다.** 다음 넷을 같은 prefix에 동시에 요구했다.
>
> ```text
> backup-writer 의 DeleteObject 금지  +  R2 Bucket Lock 적용
> CNPG 의 오래된 백업 자동 정리       +  WAL 14일 / basebackup 4~8개 보관
> ```
>
> **성립하지 않는다.** CNPG Barman Cloud의 retention 정책은 내부적으로
> `barman-cloud-backup-delete`로 **실제 삭제를 수행**한다. R2 Bucket Lock은 잠긴 객체의 삭제·
> 덮어쓰기를 막고 lifecycle 삭제보다 우선한다. 같은 prefix에 둘을 걸면 **retention 작업이
> 실패하거나 잠금 만료까지 삭제되지 않아 저장량이 계속 증가한다.**

**해결: prefix를 분리해 역할을 나눈다.**

```text
R2 (aligner-backup)
├─ hot/                          ← 운영 복구용. 짧은 보존. 자동 prune 허용
│  ├─ cnpg/                        CNPG 가 직접 관리 (WAL + basebackup)
│  └─ etcd/                        K3s snapshot retention 이 관리
│     · Bucket Lock 적용하지 않는다
│     · backup-writer 에 Delete 권한을 준다 (이 prefix 에 한정)
│     · 삭제가 실제로 동작하는지 acceptance test 필수
│
└─ immutable/                    ← 침해·랜섬웨어 대비. 별도 복제 작업이 생성
   ├─ monthly/cnpg/
   └─ monthly/etcd/
      · Bucket Lock (WORM 보존 3~6개월)
      · 운영 클러스터 자격증명에 Delete 권한 없음
      · 복제는 클러스터 밖 CronJob 또는 GitHub Actions 가 수행

AWS S3 (aligner-backup-cold)
└─ monthly/                      ← 최종 독립 사본. Object Lock. 다른 CSP·다른 계정
```

**자격증명 3분할**

| 자격증명 | 배치 | 권한 |
| --- | --- | --- |
| `backup-writer` | 클러스터 안 (CNPG·K3s) | `hot/**` 에 Put·List·**Delete 허용** (retention 동작에 필요) |
| `archiver` | 클러스터 **밖** (별도 스케줄러) | `hot/**` Get + `immutable/**` Put. **Delete 없음** |
| `restore` | 클러스터 **밖**, 오프라인 보관 | 전체 Get·List. Put·Delete 없음 |

초판의 "backup-writer는 DeleteObject 금지"는 **`hot/`에는 적용할 수 없다.** 대신 침해 시
`hot/`이 지워져도 `immutable/`과 S3 사본이 남는다는 계층 방어로 목적을 달성한다.
**클러스터 안의 자격증명으로는 `immutable/`을 건드릴 수 없다는 것이 핵심이다.**

**보존 정책**

| 대상 | 위치 | 보존 | 관리 주체 |
| --- | --- | --- | --- |
| WAL | `hot/cnpg/` | 14일 | CNPG retention |
| basebackup | `hot/cnpg/` | 주간 4~8개 | CNPG retention |
| etcd snapshot | `hot/etcd/` | 7일 | K3s `etcd-snapshot-retention` |
| 월간 사본 | `immutable/monthly/` | 3~6개월 | 외부 복제 작업 + Bucket Lock |
| 최종 사본 | S3 `monthly/` | 6개월 | Object Lock |

**반드시 실제로 시험해야 하는 것** — Phase 2 DoD에 넣는다.

```text
□ 백업 생성 성공
□ 오래된 백업 prune 이 실제로 삭제됨 (hot/ 에서 Bucket Lock 이 방해하지 않음)
□ immutable/ 의 잠긴 객체는 backup-writer 로 삭제가 실패함
□ archiver 자격증명으로 hot/ → immutable/ 복제 성공
□ restore 자격증명으로 PITR 복원 성공 (WAL 복원 포함)
□ Bucket Lock 적용 상태에서 retention job 이 오류 없이 완료됨
```

**크레딧 밖 현금 비용** — R2·S3·Grafana Cloud는 가비아 크레딧이 적용되지 않는다.

| 항목 | 예상 사용량 | 월 비용 |
| --- | --- | --- |
| R2 저장 (무료 10 GB-month 초과분) | 20~40 GB-month | $0.15 ~ $0.45 |
| R2 Class A 연산 (무료 100만/월) | 약 2,000회/월 | $0 |
| AWS S3 월간 2차 사본 | 10~20GB | 약 $0.5 |
| Grafana Cloud Free | 한도 내 유지 | $0 |
| **합계** | | **월 약 $1 (1,500원) 내외** |

금액은 작지만 **크레딧으로 결제되지 않는 별도 현금**이므로 항목으로 관리한다. R2 저장량이
50GB를 넘으면 보존 기간을 재검토한다.

**복구 리허설을 하지 않은 백업은 백업이 아니다.** 월 1회 복구 훈련을 Phase 2부터 정례화하고,
결과(소요 시간·문제점)를 기록한다. 이게 Phase 4 리허설의 기반이 된다.

---

## 2.6 Secret 관리 — Infisical Cloud + External Secrets Operator

> **6판에서 Sealed Secrets를 철회하고 외부 Secret Manager로 전환한다.** 근거는 아래 §2.6.1이다.

### 2.6.1 왜 Sealed Secrets를 철회하는가 — 범위가 좁았다

5판까지의 설계는 **Kubernetes Secret만** 다뤘다. 그런데 이 프로젝트가 실제로 관리해야 하는
시크릿은 Kubernetes 밖에 더 많다.

| 시크릿 | 5판의 보관 위치 | 문제 |
| --- | --- | --- |
| 가비아 ID/PW (gabiactl·Terraform) | 환경변수 + 패스워드 매니저 | Kubernetes와 무관 |
| R2 · AWS S3 백업 자격증명 | "자격증명 3분할" (위치 미정) | 어디에 두는지 정하지 않았다 |
| Grafana Cloud 토큰 | 패스워드 매니저 | 수동 주입 |
| K3s server token | 패스워드 매니저 + 오프라인 | 수동 |
| GitHub Actions 시크릿 | GitHub Secrets | 또 다른 정본 |
| 애플리케이션 DB·OAuth 시크릿 | Sealed Secrets (Git) | Kubernetes 전용 |

**정본이 네 곳(패스워드 매니저 · GitHub Secrets · Git의 SealedSecret · 환경변수)으로 흩어져
있었다.** 값 하나를 바꾸면 네 곳을 확인해야 하고, 어디가 최신인지 알 수 없다. 이건 도구 선택
문제가 아니라 **설계 결함**이다.

**Best Practice는 "Infisical을 쓰는 것"이 아니라 다음 패턴이다.**

```text
1. Secret 을 소스 코드와 Git 에서 분리
2. 외부 Secret Manager 를 단일 정본으로 사용
3. 사용자 Identity 와 머신 Identity 를 분리
4. 가능한 경우 단기 Credential 사용
5. 각 실행 주체에 최소 권한 부여
6. Kubernetes etcd 저장 시 암호화
7. Secret 조회·변경·복구 절차를 문서화
```

Infisical Cloud는 이 패턴의 구현체로 ALIGNER 규모에 맞는다 — 사람용 UI, CLI 로컬 주입,
GitHub Actions OIDC, Kubernetes 연동, 경로 기반 분리, Machine Identity를 한 플랫폼에서 제공한다.

### 2.6.2 Sealed Secrets 대비 실질 이득 — 재해 복구 리스크가 낮다

이게 가장 중요한 차이다.

```text
Infisical Machine Identity credential 를 분실
  → Git 의 모든 SealedSecret 이 영구히 복호화 불가
  → 모든 시크릿을 사람이 다시 만들어야 한다  ← 복구 불가능한 손실

Infisical Machine Identity credential 을 분실
  → Infisical 콘솔에서 새 credential 을 발급
  → ESO 에 다시 주입하면 끝                  ← 재발급 가능
```

5판은 "봉인 키 오프라인 백업"을 Phase 1 필수 조건으로 두어 이 위험을 관리했다. **Infisical은
그 위험 자체를 제거한다.** 백업해야 하는 것이 "잃으면 끝나는 키"에서 "재발급 가능한 자격증명"으로
바뀐다.

### 2.6.3 최종 구조

```text
                    Infisical Cloud
                   Secret Source of Truth
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    Developer CLI    GitHub Actions      Kubernetes
    infisical run       OIDC                ESO
    (Terraform·                              │
     Ansible·                        Kubernetes Secret
     gabiactl)                                │
                                   K3s secrets-encryption
                                     (etcd at rest)
```

| 계층 | 인증 방식 | 장기 자격증명 |
| --- | --- | --- |
| 개발자·Terraform·Ansible·gabiactl | Infisical CLI (`infisical run`) | 사람 로그인 (2FA) |
| GitHub Actions | **OIDC** — 단기 Access Token 발급 | **없음** |
| Kubernetes (ESO) | Universal Auth Machine Identity | Bootstrap credential 1개 (§2.6.7) |

**Infisical 자체 Operator 대신 External Secrets Operator를 쓴다.**

```text
- Infisical 전용 CRD 종속성 감소
- 다른 Secret Manager 로 이전 가능 (Provider 교체)
- Kubernetes Secret 참조 방식 유지 (앱 코드 변경 없음)
- ESO 의 namespace 격리·보안 옵션 활용

현재   ExternalSecret → Infisical
향후   ExternalSecret → AWS Secrets Manager / Vault / OpenBao
```

이 이전 가능성은 **§2.6.9의 SaaS 의존 리스크에 대한 실질적 대비책**이다.

### 2.6.4 Infisical 구조 — **Project 2개로 권한 경계를 만든다**

> ⚠️ **6판 초안의 "경로별 최소 권한"은 유료 기능에 의존했다.** Infisical의 **경로 단위 제한은
> RBAC Custom Role의 조건으로 구현되고, Role-based Access Controls는 Pro 기능**이다.
> 무료 플랜에서 `/prod/apps`만 읽는 Identity를 만들 수 있다고 가정하면 안 된다.
>
> **보안 경계를 요금제 기능에 의존하게 두는 것 자체가 설계 결함이다.** 경로가 아니라
> **Project 경계로 나눈다** — Project 멤버십은 플랜과 무관하게 강제된다.

```text
Infisical Organization
│
├── Project: aligner-infra          ← 인프라·복구 시크릿
│   /prod/gabia
│   ├── GABIACLOUD_USERNAME          GABIACLOUD_PASSWORD
│   ├── GABIACLOUD_PROJECT_ID
│   └── GABIACLOUD_IDENTITY_ENDPOINT  GABIACLOUD_CLOUD_ENDPOINT
│   /prod/k3s
│   ├── K3S_TOKEN                     ← 없으면 etcd 복구 불가 (§2.5.2)
│   └── CLUSTER_RECOVERY_PASSPHRASE
│   /prod/backup
│   ├── R2_ACCESS_KEY_ID              R2_SECRET_ACCESS_KEY
│   ├── AWS_BACKUP_ROLE_ARN
│   └── BACKUP_ENCRYPTION_KEY
│
└── Project: aligner-runtime        ← 클러스터 워크로드가 쓰는 시크릿
    /prod/database
    ├── DB_USERNAME                   DB_PASSWORD
    /prod/aligner-api
    ├── JWT_SECRET
    └── OAUTH_CLIENT_ID               OAUTH_CLIENT_SECRET
    /prod/observability
    └── GRAFANA_CLOUD_USERNAME        GRAFANA_CLOUD_TOKEN
```

**Identity 구성 — 무료 한도 안에서 구조적 격리를 얻는다**

| Identity | aligner-infra | aligner-runtime | 비고 |
| --- | --- | --- | --- |
| 이동훈 (사람) | Admin | Admin | Infisical 2FA 적용 |
| 이강혁 (사람) | Admin | Admin | Infisical 2FA 적용 |
| `github-platform-deploy` | Viewer | Viewer (필요 시) | **OIDC** — 장기 토큰 없음 |
| `k3s-production-eso` | **미가입** | Viewer | ★ 가입 자체를 하지 않는다 |
| **합계** | | | **Identity 4개 · Project 2개** |

**`k3s-production-eso`를 `aligner-infra`에 가입시키지 않는다.** 이것이 핵심이다.
Kubernetes 워크로드가 가비아 관리 비밀번호·K3s token·백업 복호화 키를 읽을 수 있는 경로가
**애초에 존재하지 않는다.** Role 설정 실수나 플랜 변경으로 뚫릴 여지가 없다.

> **Phase 0에서 무료 티어 한도를 실제로 확인한다**(⑦). 현재 알려진 한도는 Identity 5개·
> Project 3개 수준이며 위 구성(4·2)은 그 안에 들어간다. **한도가 다르거나 Project 분리가
> 불가하면** Pro 전환(경로 기반 Custom Role) 또는 Organization 분리를 검토하고 **크레딧 밖
> 현금 비용으로 §2.5.2 표에 추가**한다.
>
> **Pro를 쓸 경우** Project 하나 + path-scoped Custom Role로 단순화해도 된다. 현재 규모에서는
> 무료 플랜 + Project 2개가 더 적합하다.

**`x-cloud-session`은 저장하지 않는다.**

```text
Gabia ID/PW → 실행 시 identity-api 호출 → 2시간 세션 발급
→ 프로세스 메모리에만 보관 → 실행 종료 또는 만료 시 폐기
```

### 2.6.5 Identity 분리와 최소 권한

```text
사람 계정 (Platform Admin 2명)          Infisical 로그인 + 2FA
  이동훈 · 이강혁                        두 Project Admin

github-platform-deploy  (OIDC)          Project 멤버십으로 범위 제한
  단기 Access Token. 장기 토큰을 GitHub Secrets 에 저장하지 않는다

k3s-production-eso  (Universal Auth)    aligner-runtime 만 가입
  aligner-infra 에 미가입 → 가비아 ID/PW · K3S_TOKEN · 백업 키에 접근 경로 없음
```

> **Infisical 사람 계정에는 2FA를 적용한다.** 가비아 계정의 2FA 미사용(§2.8.6)은 가비아가
> API Key·Service Account를 제공하지 않는 제약에 따른 **명시적 예외**이며, Infisical 로그인과는
> 무관하다. 두 결정을 혼동하지 않는다.

### 2.6.6 ESO 구성 — 공격 표면을 줄인다

여러 namespace에서 Secret이 필요하므로 `ClusterSecretStore` 하나를 쓰되 **허용 namespace를
label로 제한**한다. ESO 공식 보안 가이드도 이를 권장한다.

```yaml
apiVersion: external-secrets.io/v1
kind: ClusterSecretStore
metadata:
  name: infisical
spec:
  conditions:
    - namespaceSelector:
        matchLabels:
          secrets.aligner.io/enabled: "true"
```

```yaml
# 허용 namespace 에만 label 을 붙인다
metadata:
  labels:
    secrets.aligner.io/enabled: "true"
```

**사용하지 않는 cluster-wide reconciler와 CRD를 비활성화한다.**

```yaml
# gitops/infrastructure/controllers/external-secrets/values.yaml
processClusterExternalSecret: false
processPushSecret: false
crds:
  createClusterExternalSecret: false
  createPushSecret: false
resources:
  requests: { cpu: 50m, memory: 150Mi }
```

`ClusterSecretStore`만 유지한다.

**변경 권한을 Secret 접근 권한과 동등하게 취급한다.** `ClusterSecretStore`·`ExternalSecret`에
쓰기 권한이 있으면 임의 경로의 Secret을 Kubernetes로 끌어올 수 있다. ESO 위협 모델도 이를
경고한다.

```text
# .github/CODEOWNERS — Platform Owner 승인 없이 merge 불가
gitops/infrastructure/controllers/external-secrets/**   @move-hoon @TODO-kanghyeok-github-id
gitops/infrastructure/configs/secret-stores/**          @move-hoon @TODO-kanghyeok-github-id
gitops/**/external-secret*.yaml                         @move-hoon @TODO-kanghyeok-github-id
```

### 2.6.7 Secret Zero — Bootstrap Credential

ESO가 Infisical에 최초 로그인하기 위한 자격증명 한 쌍은 **Kubernetes Secret으로 수동 주입**한다.

```bash
kubectl -n external-secrets create secret generic infisical-machine-identity \
  --from-literal=clientId="$INFISICAL_CLIENT_ID" \
  --from-literal=clientSecret="$INFISICAL_CLIENT_SECRET"
```

```text
□ Git 에 저장하지 않는다
□ Infisical 내부에서도 ESO 전용 Identity 로 분리 (§2.6.5)
□ 필요한 Secret 경로만 Read 허용
□ K3s secrets-encryption 으로 etcd 저장 시 암호화 (§2.6.8)
□ 로그 출력 금지
□ 노출 시 즉시 폐기·재발급
□ 클러스터 재구축 시 운영자 로컬에서 최초 1회 주입
□ ★ 오프클러스터 보관 목록에 포함 (§2.5.2)
```

**Secret Zero는 두 번째 정본이 아니다.** 외부 Secret Manager에 접근하기 위한 Bootstrap
Credential이며, 그 자체로는 어떤 값도 담지 않는다.

### 2.6.8 ⚠️ ESO가 만든 Secret은 etcd에 저장된다 — 암호화 필수

ESO는 Infisical의 값을 읽어 **native Kubernetes Secret을 생성**한다. 그 Secret은 etcd에 들어가고,
etcd 스냅샷은 R2로 올라간다. 따라서 **encryption at rest가 없으면 백업 파일이 평문 자격증명
덩어리가 된다.**

```yaml
# /etc/rancher/k3s/config.yaml — 모든 server 노드에서 동일해야 한다
secrets-encryption: true
```

**키 회전 절차** — 현재 K3s는 단일 명령을 쓴다.

```bash
k3s secrets-encrypt status              # 회전 전 상태 확인
sudo k3s etcd-snapshot save             # ★ 반드시 먼저 스냅샷
k3s secrets-encrypt rotate-keys         # 회전 + 재암호화를 한 번에
k3s secrets-encrypt status
#   Current Rotation Stage: reencrypt_finished
#   Server Encryption Hashes: All hashes match     ← 3노드 전부 확인
```

> **5판의 `prepare → rotate → reencrypt` 3단계 절차는 legacy다.** 현재 문서화된 절차는
> `rotate-keys` 한 번이며 재암호화까지 포함한다(약 5 secrets/초). 3노드 HA에서는 **모든 server의
> hash가 일치하는지** 확인해야 한다.
>
> 회전 중에는 §3.5.2의 `maintenance` overlay를 적용하고, **회전 전 etcd 스냅샷을 반드시 확보**한다
> — 구 키로 암호화된 스냅샷은 구 키가 있어야 복구된다.

### 2.6.9 SaaS 의존 리스크와 대비

Infisical Cloud는 **외부 SaaS이며 부트스트랩 경로에 있다.** 정직하게 다룬다.

| 장애 시나리오 | 영향 | 대비 |
| --- | --- | --- |
| Infisical 일시 장애 | **기존 Kubernetes Secret은 그대로 유지된다.** 실행 중 워크로드 무영향. 새 Secret 동기화만 지연 | 우아한 열화. 별도 조치 불필요 |
| Infisical 장애 중 클러스터 재구축 | ESO가 Secret을 채우지 못해 앱 기동 실패 | 재구축은 계획 작업이므로 Infisical 상태 확인 후 시작 |
| Infisical 서비스 종료·정책 변경 | 정본 이전 필요 | **ESO Provider 교체로 대응**(§2.6.3). CRD와 앱 코드는 무변경 |
| 계정 탈취 | 전체 시크릿 노출 | 사람 계정 2FA + Machine Identity 최소 권한 + 감사 로그 |

**Phase 0에서 확인할 것** — Infisical Cloud **무료 티어 한도**(사용자 수·프로젝트 수·시크릿
버전 보관·감사 로그 기간)를 실제로 확인한다. 2명 · 1프로젝트 규모로 충분할 것으로 보이지만
가정하지 않는다. 유료 전환이 필요하면 **크레딧 밖 현금 비용**으로 §2.5.2 표에 추가한다.

### 2.6.10 제거하는 시크릿 도구

```text
Sealed Secrets                     → Infisical + ESO 로 대체
운영 Secret 용 ansible-vault        → infisical run 으로 환경변수 주입
운영값을 복사한 GitHub Secrets       → OIDC 로 대체
평문 .env                          → 사용 금지
Git 에 암호화 파일을 저장하는 SOPS    → 정본을 Git 밖으로
```

**이 도구들이 나빠서 제외하는 것이 아니다.** 목표가 *"Terraform·Ansible·GitHub Actions·
Kubernetes에서 쓰는 모든 시크릿을 한곳에서 수정하는 것"* 이므로 외부 Secret Manager가 더 맞는다.
단일 클러스터·Kubernetes 전용이라면 Sealed Secrets가 여전히 합리적 선택이다.

### 2.6.11 Terraform · Ansible · gabiactl에서의 사용

```bash
# Terraform
infisical run --projectId=$ALIGNER_INFRA --env=prod --path=/gabia -- terraform apply

# gabiactl
infisical run --projectId=$ALIGNER_INFRA --env=prod --path=/gabia -- \
  gabiactl apply --file infra/bootstrap/desired-infrastructure.yaml

# Ansible
infisical run --projectId=$ALIGNER_INFRA --env=prod --path=/k3s -- \
  ansible-playbook -i .runtime/inventory.yaml ansible/playbooks/site.yml
```

```hcl
provider "gabiacloud" {}   # HCL 에 자격증명을 쓰지 않는다 (환경변수를 읽는다)
```

```yaml
# ansible — group_vars 에 실제 값을 저장하지 않는다
k3s_token: "{{ lookup('env', 'K3S_TOKEN') }}"
```

### 보안 기준선 (정책 엔진 없이)


원본의 “PSA + NetworkPolicy, Kyverno/OPA 미도입”은 유지한다. 다만 항목을 구체화한다.

| 항목 | 설정 |
| --- | --- |
| Pod Security Admission | 애플리케이션 namespace에 `restricted` (enforce). 시스템 namespace는 예외 라벨 |
| 컨테이너 | `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`, 모든 capability drop |
| NetworkPolicy | default-deny ingress/egress + 명시적 허용만 (§2.3) |
| ServiceAccount | `automountServiceAccountToken: false` (필요한 것만 예외) |
| 이미지 | digest 고정, Trivy 스캔 게이트, GHCR private |
| RBAC | Argo CD `Application`마다 최소 권한, cluster-admin 상시 사용 금지 |
| 감사 | K3s audit log 활성화(`kube-apiserver-arg: audit-log-path`), Alloy가 Grafana Cloud로 전송 |

Kyverno·Gatekeeper를 넣지 않는 이유는 리소스가 아니라 **운영 주체가 2명**이라는 점이다.
정책 엔진은 정책을 작성·검토·예외 관리할 인력이 있을 때 가치가 있다. 위 기준선을
`kustomize` base에 넣어 모든 앱이 상속하게 하면 같은 효과의 90%를 인력 비용 없이 얻는다.

---

## 2.7 Observability — Alloy(외부) vs 클러스터 내 Prometheus/Loki

메모리가 24GB로 늘었으니 내부 스택을 재검토할 조건이 생겼다. 실제로 계산해 본다.

| 구성 요소 (클러스터 내 스택) | 메모리 | 디스크 |
| --- | --- | --- |
| Prometheus (retention 15일, 3노드 + 25 pods) | 1.5~3GB | 20~40GB |
| Grafana | 200~300MB | 1GB |
| Alertmanager (HA 2 replica) | 200MB | — |
| Loki (single binary + filesystem) | 500MB~1GB | 30~60GB |
| kube-state-metrics + node-exporter ×3 | 250MB | — |
| **합계** | **2.7~4.8GB (24GB의 11~20%)** | **50~100GB** |

| 구성 요소 (Alloy 외부 전송) | 메모리 | 디스크 |
| --- | --- | --- |
| Grafana Alloy DaemonSet ×3 | 3 × 200MB = 600MB | 0 (WAL 소량) |
| kube-state-metrics | 150MB | — |
| metrics-server (HPA용, 필수) | 100MB | — |
| **합계** | **약 850MB (3.5%)** | **거의 0** |

### 판단: Alloy → Grafana Cloud 유지. 근거를 강화한다

**1) 관측성 백엔드를 관측 대상과 같은 클러스터에 두면 장애 시 진단 수단을 동시에 잃는다.**
이게 결정적 논거다. 9개월 계획의 후반 3개월이 장애 훈련과 DR이다. 노드를 강제로 죽이고
etcd를 복구하는 훈련에서 **Prometheus가 그 클러스터 안에 있으면 훈련 중 대시보드가 함께
사라진다.** 무엇이 언제 어떻게 죽었는지 기록이 남지 않으면 훈련의 절반이 무의미해진다.
게다가 Prometheus PVC를 local-path에 두면 그 노드가 죽는 순간 메트릭 이력까지 잃는다.

**2) 절감된 3~4GB와 50~100GB 디스크가 곧 JVM heap과 PG standby다.**
디스크 100GB는 Data SSD 기준 11,500원/월(공급가)이다. 9개월이면 약 10만 원 — 잔여 크레딧의
36%를 관측성 저장소가 먹는다.

**3) 클러스터 전체 다운을 외부에서 감지할 수 있다.**
Grafana Cloud의 alerting과 외부 프로빙(Synthetic Monitoring)을 쓰면 클러스터가 완전히 죽어도
Slack·Discord로 알림이 온다. 내부 Alertmanager는 클러스터와 함께 침묵한다.

### 구성

```text
Spring Boot Pod
├─ Actuator /actuator/prometheus  (Micrometer)  ─┐
├─ OTel Java Agent → OTLP :4317              ─┤
└─ stdout (JSON 구조화 로그)                  ─┤
                                              │
Kubernetes 노드 (DaemonSet)                    │
  Grafana Alloy ◄────────────────────────────┘
  ├─ prometheus.scrape        (pod annotation 기반 자동 발견)
  ├─ loki.source.kubernetes   (컨테이너 로그)
  ├─ otelcol.receiver.otlp    (트레이스)
  ├─ prometheus.relabel       ★ 카디널리티 제어 (아래)
  └─ *.write / *.exporter → Grafana Cloud (Mimir / Loki / Tempo)

클러스터 내부에 두는 것:  metrics-server(HPA 필수), kube-state-metrics
클러스터 내부에 두지 않는 것:  Prometheus TSDB, Loki, Grafana, Alertmanager, Elasticsearch
```

**Free tier 한도 관리 — Spring Boot 특화 주의점**

Grafana Cloud 무료 티어는 활성 시리즈 수에 제한이 있다. Spring Boot의 기본 메트릭이 이 한도를
가장 빨리 태우는 원인이므로 **Alloy에서 relabel로 잘라낸다.**

| 문제 | 대응 |
| --- | --- |
| `http_server_requests_seconds`의 `uri` 라벨이 실제 경로별로 폭발 (`/courses/12345`) | Spring MVC는 기본적으로 `@PathVariable` 템플릿(`/courses/{id}`)을 사용한다. 커스텀 `MeterFilter`로 미매칭 요청(`uri="/**"`)을 묶고, `exception` 라벨은 제거 |
| `jvm_buffer_*`, `tomcat_*`, `logback_*` 등 저활용 메트릭 다수 | Alloy `prometheus.relabel`에서 `drop` |
| histogram 버킷 수 (`percentiles-histogram`) | SLO 측정에 필요한 엔드포인트만 활성화 |
| 파드 재생성마다 `pod` 라벨이 새 시리즈 생성 | `pod` 라벨을 유지할 메트릭을 선별 (JVM 메트릭은 유지, HTTP 메트릭은 `deployment` 단위 집계) |

**반드시 유지해야 할 메트릭** — 이 설계의 자원 튜닝 근거가 되는 것들이다.

```text
jvm_memory_used_bytes{area="heap"}        → limits.memory 적정성 판단
jvm_memory_committed_bytes               → MaxRAMPercentage 검증
jvm_gc_pause_seconds                     → heap 부족 징후 (GC 빈도·시간 증가)
jvm_threads_live_threads                 → 스레드 스택 메모리 추정
process_cpu_usage / system_cpu_usage     → requests.cpu 실측
container_cpu_cfs_throttled_seconds_total → ★ CPU limit 스로틀링 탐지 (§3.1)
http_server_requests_seconds{quantile}   → p95·p99 지연
hikaricp_connections_pending             → 커넥션 풀 포화
```

`container_cpu_cfs_throttled_seconds_total`은 JVM 워크로드에서 가장 중요한 메트릭인데 자주
누락된다. 이 값이 올라가면 CPU limit이 낮아 JIT·GC 스레드가 강제로 멈추고 있다는 뜻이다.

**인프라 계층 필수 지표** — 이 설계의 실제 실패 모드를 감지하는 것들이다.

```text
[디스크 — §1.4의 장애 시나리오]
etcd_disk_wal_fsync_duration_seconds{quantile="0.99"}   → etcd 지연. 100ms 초과면 위험
node_disk_io_time_weighted_seconds_total                → await / queue depth
node_filesystem_avail_bytes{mountpoint="/mnt/k3s"}      → Data-A (etcd)
node_filesystem_avail_bytes{mountpoint="/mnt/aligner"}  → Data-B (PG·Redis)
node_filesystem_files_free                              → ★ inode. WAL이 많으면 용량보다 먼저 마른다

[스케줄링 — §3.5의 CPU·메모리 부족]
kube_pod_status_unschedulable                           → ★ Pending 파드. CPU 부족의 1차 신호
kube_pod_status_phase{phase="Pending"}
container_cpu_cfs_throttled_periods_total / periods_total
kube_node_status_allocatable                            → 실측 allocatable (문서값 검증)

[데이터베이스 — §2.5.2·2.5.3]
cnpg_pg_replication_lag                                 → 복제 지연. 60s 초과 Warning
cnpg_pg_stat_archiver_failed_count                      → ★ WAL 아카이빙 실패. 누적되면 PG 정지
cnpg_collector_last_available_backup_timestamp          → ★ 마지막 성공 백업 시각
pg_stat_bgwriter_checkpoints_req                        → 강제 체크포인트 빈도

[백업 — §2.5.2]
마지막 etcd snapshot 성공 시각                           → K3s 로그 파싱 또는 R2 객체 목록
R2 / S3 객체 수·총 용량 증가량                            → 비용 관리 + 백업 중단 감지
Bucket Lock 보존 정책 적용 여부                           → 월 1회 수동 점검

[비용 — 크레딧 관리]
가비아 크레딧 잔액                                       → 주 1회 수동 확인 (API 없음)
R2 / S3 / Grafana Cloud 사용량                           → 크레딧 밖 현금 비용
```

**`kube_pod_status_unschedulable`과 `마지막 성공 백업 시각`이 특히 중요하다.** §3.5에서 드러난
CPU·메모리 부족은 **Pending 파드로 나타나고**, §2.5.2의 K3s token 누락 같은 문제는
**"백업은 도는데 복구가 안 되는" 상태**를 만든다. 후자는 지표로 잡히지 않으므로 월 1회
실제 복구 훈련이 유일한 검증 수단이다.

---

## 2.8 L1 IaC — 가비아 Gen2 자체 REST API 기반

> **이 절은 4판에서 전면 재작성했다.** 이전 판들은 "OpenTofu 1순위" → "Ansible 1순위" →
> "OpenStack provider 1순위"라는 **세 결론이 문서 안에 동시에 존재**했다. 실측으로 사실이
>확정됐으므로 단일 경로로 정리한다.

### 2.8.1 확정된 사실 — 실측 결과

**① 가비아 클라우드용 Terraform provider는 존재하지 않는다** (Terraform Registry 조회)

```text
filter[name]=gabia       → total-count: 0
filter[name]=gabiacloud  → total-count: 0
filter[name]=gcloud      → total-count: 0
(방법 검증) filter[name]=ncloud → 1  NaverCloudPlatform/ncloud
```

**② 그러나 비대화형 세션 인증과 리소스 API가 실재한다** (실제 호출로 검증)

| 항목 | 검증 결과 |
| --- | --- |
| 세션 생성 | `POST identity-api.gabiacloud.com/api/v1/sessions` |
| 인증 방식 | **HTTP Basic (ID/PW)**, 요청 body `{}`. 브라우저 쿠키 불필요 |
| 응답 | `201 Created` |
| 세션 scope | `project` |
| **세션 수명** | **2시간** (`created_at` / `expired_at` 차) |
| Cloud API 인증 | `x-cloud-session: <session.id>` 헤더 |
| 세션 응답 필드 | `auth_domains`, `auth_projects`, `domain`, `id`, `is_2fa_auth`, `mfas`, `plan`, `project`, `scope`, `session_type`, `token`(빈 문자열), `user` |

**③ 확인된 리소스 경로** (세션 인증 후 GET)

| 경로 | 응답 | 비고 |
| --- | --- | --- |
| `/api/v1/subnets` | **200** | `Default-Subnet {{ vpc_cidr }}`. 필드: `cidr`, `gateway_ip_address`, `is_external`, `network`, `nics`, `peering_gateways`, `router`, `routing_table`, `project_id`, `is_deleted`, `deleted_at` |
| `/api/v1/networks` | **200** | `total_cnt=1` |
| `/api/v1/servers` | **200** | `total_cnt=0` — Compute 목록 API 존재 |
| `/api/v1/images` | **200** | `total_cnt=115`. 필드: `os`, `os_distro`, `os_version`, `min_cpu`, `min_ram`, `min_disk`, `image_type`, `visibility`, `tags` |
| `/api/v1/routers` | **403** | 경로 존재. **권한 스코프가 실재한다** → 최소 권한 서브 계정이 가능하다는 신호 |
| `security-groups` · `block-storages` · `public-ips` · `load-balancers` · `ssh-keypairs` · `flavors` | **404** | 추측한 복수형 경로가 틀렸다. **명명 규칙 미발견** |

**④ Subnet CRUD** (별도 콘솔 트래픽 캡처로 검증)

```text
POST   /api/v1/subnets        → 201
GET    /api/v1/subnets        → 200
GET    /api/v1/subnets/{id}   → 200   (List보다 응답이 풍부하다 → Read는 상세 API 사용)
PUT    /api/v1/subnets/{id}   → 200   (수정 가능: name, description)
DELETE /api/v1/subnets/{id}   → 204
재생성 필드: network_id, cidr
주의: 빈 필터 id__in=[] 를 보내면 전체가 아니라 빈 결과가 반환된다 → 요청에서 생략해야 한다
```

**⑤ 공식 OpenAPI·Swagger 명세는 없다**

> ⚠️ **2판의 다음 서술을 삭제한다.** "`/swagger-ui/index.html`이 404가 아니라 401이므로 경로가
> 존재할 가능성이 있다" — **틀렸다.** API 게이트웨이가 **미인증 요청 전부에 401**을 반환한다.
> `/zzz-nonsense-9999`도 401이었다. **세션 인증 후에는 `/v3/api-docs`·`/swagger-ui/index.html`
> 모두 404다.** 즉 명세가 공개되지 않는다.

따라서 문서 표현은 다음이 정확하다.

> 가비아 Gen2 자체 REST API와 비대화형 세션 인증은 확인했다. 다만 공식 OpenAPI·Swagger 명세는
> 발견되지 않았으며, 리소스별 경로와 요청·응답 계약은 관리콘솔 트래픽을 통해 개별 검증해야 한다.

### 2.8.2 아직 검증하지 않은 것 — "L1 IaC 완성"이라고 쓰면 안 되는 이유

```text
Network / VPC CRUD                  Router · Routing Table CRUD
Security Group · Rule 모델           SSH Key CRUD
Server 생성 payload                  Volume 생성·연결·해제
Public IP 할당·연결·해제              LB · Listener · Pool · Member · Health Monitor 관계
비동기 task ID와 상태 조회            오류 응답 형식
삭제 의존 순서                       중복 이름 허용 여부
API rate limit                       공식 API 호환성·변경 정책
```

> 인증과 Subnet CRUD를 통해 자동화의 **기술적 실현 가능성**은 확인했다. 그러나 L1을 구성하는
> Compute·Volume·Public IP·Load Balancer API는 아직 경로조차 확정되지 않았으므로, 해당 리소스의
> CRUD와 비동기 상태 전이를 검증한 뒤에만 "L1 IaC 완성"으로 판정한다.

### 2.8.3 OpenStack은 기본안이 아니다 — 3판 결론 하향

3판은 "관리형 K8s가 Cinder CSI를 쓰므로 Keystone이 확실히 존재한다 → OpenStack provider 1순위"로
올렸다. **과했다.**

**검증된 사실** — 가비아 관리형 Kubernetes 매뉴얼에 다음이 있다.

```text
manual/cloud/23381/24268   Provisioner: cinder.csi.openstack.org
                           Parameters: availability=nova, type=ssd_iscsi
                           Helm release: openstack-cinder-csi-num
manual/cloud/23381/24281   loadbalancer.openstack.org/flavor-id
                           loadbalancer.openstack.org/availability-zone: KR1-Zone1-LB
```

**올바른 해석** — 이는 가비아 내부에 Keystone·Cinder·Octavia가 존재할 가능성이 높다는 증거다.
그러나 **가비아가 관리형 서비스 내부에 주입한 자격증명일 수 있고, 일반 Gen2 고객에게 Keystone
엔드포인트와 Application Credential을 제공한다는 증거는 아니다.** 실제로 고객이 쓰는 인터페이스는
`identity-api.gabiacloud.com`과 `cloud-api.gabiacloud.com`의 **가비아 자체 facade API**다.

```text
1순위  가비아 자체 REST API 기반 자동화 (검증 완료)
2순위  Keystone auth_url · Application Credential을 공식 제공할 경우
         → terraform-provider-openstack (성숙도가 검증된 provider)
비상   API 변경·장애 시 문서화된 콘솔 Bootstrap + gabiactl 수동 삭제
```

### 2.8.4 레이어 분리 — CNI만 예외

| 층 | 대상 | 도구 |
| --- | --- | --- |
| **L1 인프라** | VPC, 서브넷, 라우터, 보안그룹, VM, 블록 스토리지, 공인 IP, LB | **gabiactl + Ansible** (§2.8.5) |
| **L2 OS·노드** | 디스크 분할·마운트, 커널 파라미터, 관리망, **Cilium 부트스트랩**, K3s 설치·조인, systemd | **cloud-init + Ansible** |
| **L3 클러스터 리소스** | Namespace, RBAC, NetworkPolicy, Helm, 애플리케이션 | **Argo CD** |

**원칙: IaC는 kubeconfig가 나오는 지점까지, 그 이후는 GitOps.**
**예외: CNI(Cilium)는 L2 소유다.** GitOps가 CNI를 관리하면 잘못된 sync 한 번이 클러스터 네트워크
전체를 끊고, 그 상태에서는 Argo CD로 되돌릴 수도 없다(§2.3 부트스트랩 순서).

`terraform-provider-kubernetes`/`helm`으로 L3를 다루지 않는다. Argo CD와 소유권이 충돌한다.

**자동화 투자 우선순위는 L2 > L3 > L1이다.** L1을 콘솔로 하면 재구축에 20분이지만 L2를 수동으로
하면 며칠이다.

### 2.8.5 L1 실행안 — gabiactl 우선, Provider 병행

**핵심 결정: Custom Provider 개발을 클러스터 구축의 선행 조건으로 두지 않는다.**

```text
Phase 1 필수 (클러스터 구축을 막지 않는다)
└─ gabiactl + Ansible 로 L1 Bootstrap 자동화

병행 트랙 (일정 독립)
└─ terraform-provider-gabiacloud 개발
     └─ gabiactl 과 동일한 Go API Client 를 재사용한다

Provider 가 M3~M5 까지 안정화된 뒤
└─ 기존 리소스 import → terraform plan 이 No changes 확인 → L1 정본을 Terraform 으로 전환
```

**왜 Provider를 선행 조건으로 두지 않는가**

전체 Provider 개발은 OpenAPI 명세 없이 리버스 엔지니어링부터 해야 하고, volumes·LB·SG는 경로도
미발견이다. Go와 `terraform-plugin-framework`가 처음이면 **3~6주**가 든다(확정 일정이 아니라
범위 추정이다). 이것을 Phase 1 선행 조건으로 두면 **서비스 인프라 구축 일정이 API 리버스
엔지니어링과 Go 개발 일정에 종속된다.**

반면 L1 리소스는 약 10종이고 **생성 횟수는 초기 1회 + 재구축 리허설 1~2회**다.

> **Terraform의 가치를 축소하지 않는다.** Terraform은 리소스 ID 매핑, 의존 순서
> (Network → Subnet → SG → VM → Volume → IP → LB), Update와 Replace 판정, 삭제 순서 자동 계산,
> `plan` 사전 검토, import, output → Ansible inventory 연결, Provider 버전·checksum 고정을 모두
> 제공한다. 정확한 판단은 **"9개월·단일 클러스터·낮은 생성 빈도에서는 Custom Provider 전체
> 개발비를 Phase 1 전에 회수하기 어렵다"** 이며, "가치가 없다"가 아니다.

**단일 저장소에서 Go로 시작한다.** 클라이언트 코드를 Provider가 그대로 재사용하므로 Python이
아니라 Go로 쓴다.

```text
terraform-provider-gabiacloud/          (Private)
├─ internal/client/                     ← 공통 SDK. gabiactl 과 Provider 가 공유
│  ├─ session.go                        인증·세션 갱신·mutex·401 재시도
│  ├─ subnet.go  network.go  router.go
│  ├─ security_group.go  server.go  volume.go  public_ip.go  load_balancer.go
│  └─ retry.go                          POST 재시도 시 reconciliation
├─ cmd/gabiactl/                        ← Cobra CLI (Phase 1 에서 사용)
├─ internal/provider/                   ← Terraform Plugin Framework (병행 트랙)
├─ examples/  docs/  GNUmakefile
└─ .github/workflows/
```

Provider가 커지면 `internal/client`를 별도 Go 모듈로 추출한다. 처음부터 저장소 3개를 만들지 않는다.

**gabiactl 일정 — 3~5일은 낙관적이다**

```text
3~5일   인증·세션 관리 · Network/Subnet · 읽기 전용 탐색 · 최소 Bootstrap CLI
1~2주   VM · 볼륨 · 공인 IP · 보안그룹 · 비동기 polling · reconciliation · 최소 테스트
추가    LB 전체 모델 · check(drift) 명령 · 완전 삭제와 재구축 검증
```

**gabiactl이 반드시 갖춰야 할 것** — 이 로직은 Provider에도 동일하게 필요하므로 버리는 코드가 아니다.

```text
□ 세션 만료 5분 전 선제 재인증
□ 401 수신 시 세션 재발급 후 1회만 재시도
□ 동시 요청 시 단일 세션만 재발급 (mutex)
□ POST 재시도 전 이름·요청 식별자로 현재 상태 재조회 (중복 생성 방지)
□ 비동기 생성은 상태가 ACTIVE 될 때까지 polling, ERROR 시 즉시 실패
□ 빈 배열 필터(id__in=[]) 는 요청에서 생략
□ Read 는 List 가 아니라 /{resource}/{id} 상세 API 사용
□ Basic Authorization 헤더와 x-cloud-session 을 로그에 출력하지 않음
□ check 명령: desired-infrastructure.yaml 과 현재 상태 대조 (drift 탐지 80%)
```

### 2.8.6 인증·계정·State 정책

**Provider / gabiactl 인증 흐름** — 실제 API에 맞춘다. `Authorization: Bearer` 형태가 아니다.

```text
Configure
  ├─ 환경변수에서 ID/PW 읽기
  ├─ identity-api 에 세션 생성 (HTTP Basic, body {})
  ├─ scope == "project" 확인
  ├─ session.id 를 프로세스 메모리에만 보관
  └─ cloud-api 요청마다 x-cloud-session 헤더 추가
```

```text
GABIACLOUD_USERNAME          GABIACLOUD_IDENTITY_ENDPOINT
GABIACLOUD_PASSWORD          GABIACLOUD_CLOUD_ENDPOINT
GABIACLOUD_PROJECT_ID
```

```hcl
provider "gabiacloud" {}   # HCL 에 인증정보를 쓰지 않는다
```

> ### ADR — 가비아 계정은 2FA를 사용하지 않는다 (명시적 예외)
>
> **결정** — 사람 계정·자동화 계정 모두 가비아 2FA를 적용하지 않는다.
> **Infisical 사람 계정에는 2FA를 적용한다**(§2.6.5). 두 결정은 별개다.
>
> **근거** — 가비아가 API Key·Service Account·Application Credential을 제공하지 않아 자동화가
> 일반 계정 ID/PW 세션에 의존한다. OTP는 그 흐름을 중단시킬 수 있고, 운영자 2명·9개월 규모에서
> 계정별 예외와 복구 절차를 관리하는 비용이 이득을 넘는다.
>
> **이것은 보안 Best Practice가 아니라 제약을 수용한 예외다.** 문서에 그렇게 기록하고 보완
> 통제로 위험을 낮춘다.
>
> **보완 통제**
>
> ```text
> □ 강한 고유 비밀번호 (재사용 금지). 패스워드 매니저에만 보관
> □ 비밀번호를 채팅·이슈·CI 로그·AI 대화에 붙여넣지 않는다
> □ 자동화는 최소 권한 서브 계정으로만 — root/owner 는 콘솔 예외 작업에만
> □ 이벤트 로그를 주 1회 확인 (본인이 하지 않은 조작 탐지)
> □ 인프라 종료 시 계정·비밀번호 폐기
> ```
>
> **비밀번호 변경은 2FA와 무관하게 필수다.** 노출된 값은 2FA 여부와 관계없이 회전한다.

**전용 서브 계정 — root 사용 금지**

```text
계정 유형    전용 서브 계정 (aligner-terraform)
프로젝트     Aligner 프로젝트만
권한         필요한 리소스 CRUD 만 (routers 가 403 을 반환한 것이 권한 스코프 존재의 근거)
Root/Owner   사용 금지
비밀번호     Infisical aligner-infra Project 뿐. 로컬·CI 는 인증 후 프로세스 환경변수로만 전달받는다
회전         정기 회전 + 인프라 종료 시 폐기
로그         Basic Authorization · 세션 ID 마스킹
```

> **`is_2fa_auth: true`의 의미** — 세션 응답에 이 필드가 `true`인데 인증 완료 MFA 수단은
> `PASSWORD` 하나다(`mfas: [{method: "PASSWORD", authenticated: true}]`). 이 필드는 "OTP가
> 켜져 있다"가 아니라 **"이 세션이 MFA 정책을 충족했다"** 는 뜻으로 보인다. 자동화 계정에
> OTP를 켜지 않는 방침이므로 더 파고들 필요가 없다(위 참조).

**Terraform State — AWS S3 Remote Backend**

3판의 "OpenTofu 자체 state 암호화" 서술은 삭제한다. Terraform으로 확정했으므로 S3 백엔드의
검증된 기능을 쓴다.

```hcl
terraform {
  backend "s3" {
    bucket       = "aligner-terraform-state"
    key          = "gabia/prod/terraform.tfstate"
    region       = "ap-northeast-2"
    encrypt      = true
    use_lockfile = true      # S3 네이티브 락 (Terraform 1.10+). DynamoDB 불필요
  }
}
```

```text
□ Bucket Versioning 활성화 (HashiCorp 강력 권고)
□ Block Public Access 전체 활성화
□ SSE-S3 또는 SSE-KMS
□ state 접근 IAM 최소 권한
□ State 버킷을 가비아 클러스터 밖에 배치  ← 클러스터가 죽어도 state 가 살아야 한다
□ .tfstate · plan 파일 Git 제외
□ .terraform.lock.hcl 은 커밋한다 (Provider 버전·checksum 고정)
```

**state와 plan은 비밀정보로 취급한다.** IP·리소스 ID·사용자 스크립트가 들어간다.

**cloud-init에 넣는 것과 넣지 않는 것** — user_data는 Terraform state와 클라우드 메타데이터
서비스에 남는다.

```text
넣는다    디스크 준비 · 기본 패키지 · Ansible 접근용 계정과 공개키 · 최소 방화벽 초기 설정
넣지 않는다  API 토큰 · K3s token · DB 비밀번호 · WireGuard/Tailscale 인증 키 · R2 자격증명
```

### 2.8.7 Terraform과 OpenTofu는 이 결정과 무관하다

Custom Provider는 **Terraform과 OpenTofu에서 동일하게 동작한다.** 둘 다 같은 플러그인
프로토콜(v5/v6)을 쓰고 `dev_overrides`와 provider mirror도 양쪽 다 지원한다. 즉 **Provider를
만든다는 결정이 Terraform을 요구하지 않는다.**

```text
Provider 구현 결정     Terraform / OpenTofu 와 독립
운영 CLI               Terraform 으로 확정 (state 는 하나로만 고정)
Provider 바이너리      호환 범위 내에서 양쪽 사용 가능
```

3판이 OpenTofu를 권한 근거는 state 암호화였고, S3 SSE-KMS + Versioning + `use_lockfile`이 그것을
대체하며 감사 가능성(S3 접근 로그·KMS 키 정책)은 오히려 높다. **BSL 라이선스는 자기 인프라를
관리하는 용도에 제약이 없으므로 장애가 아니다.** 라이선스 비교표는 결정이 끝났으므로 삭제한다.

### 2.8.8 Provider 병행 트랙 마일스톤

```text
M0  인증 Client + 세션 갱신                    ← 검증 완료 (실제 호출 성공)
M1  Subnet Resource / Data Source / Import      ← API 계약 확인됨
M2  Network + Router + Security Group           ← Router 403 해소, SG 경로 발견 필요
M3  Server + Volume + Attachment                ← Server GET 만 확인. 생성 payload 미확인
M4  Public IP                                   ← 경로 미발견
M5  LB + Listener + Pool + Member + Health Check ← 경로 미발견
M6  전체 destroy / recreate 및 drift test
```

**현재는 M0 완료, M1의 API 계약 확인 단계다.**

Subnet 스키마 설계:

```text
network_id    Required, RequiresReplace
cidr          Required, RequiresReplace
name          Required, Update 가능
description   Optional, Update 가능
```

**테스트 기준**

```text
단위        JSON request/response 매핑 · 세션 만료·401 갱신 · 민감 헤더 redaction · 빈 필터 생략
Contract    개인정보 제거한 실제 응답 fixture · HTTP status 와 필드 변경 감지
Acceptance  전용 테스트 프로젝트 · TF_ACC=1 에서만 실행
            Create → Read → Update → Import → Destroy · 종료 후 잔여 리소스 탐지
```

**배포** — 개발 단계는 `dev_overrides`, 팀 배포는 Private Release 또는 filesystem/network mirror.
버전을 명시 고정하고 `.terraform.lock.hcl`을 커밋한다.

### 2.8.9 비문서화 API 의존 위험 — 정확한 심각도

가비아가 API를 변경하면 Provider의 Read·Update·Delete가 깨질 수 있고, Terraform의 refresh·plan·
destroy도 실패할 수 있다.

> ⚠️ 3판 초안의 **"API가 바뀌면 destroy도 못 하므로 IaC가 없는 것보다 나쁘다"는 과장이다.**
> 복구 수단이 있다.
>
> ```text
> 1. Provider 수정 후 재실행
> 2. 이전 Provider 버전으로 고정
> 3. 콘솔 또는 gabiactl 로 수동 삭제
> 4. removed 블록 또는 terraform state rm 으로 관리 해제 (provider 호출 없이 state 만 편집)
> 5. 수정된 Provider 로 다시 import
> ```

정확한 표현은 다음이다.

> 비문서화 API 변경 시 Terraform의 자동 관리가 **일시적으로 중단**될 수 있다. 따라서 Provider는
> 편의 도구가 아니라 **팀이 유지보수 책임을 지는 내부 소프트웨어**이며, 콘솔·gabiactl 기반
> break-glass 삭제 경로를 반드시 유지해야 한다.

**운영 규칙**

```text
□ Contract 테스트를 주 1회 CI 로 실행해 API 변경을 조기 감지
□ Provider 버전을 고정하고 업그레이드는 PR 리뷰 대상으로
□ gabiactl 수동 삭제 절차를 runbook 으로 유지 (Provider 장애 시 break-glass)
□ 가비아 API 자동화의 공식 허용 여부를 서면으로 확보 (§1.6 D3)
□ 공식 미지원이면 그것을 ADR 에 리스크로 기록하고 수용 여부를 팀이 결정
```

### 2.8.10 Public `ALIGNER-PLATFORM` 디렉터리 구조

Ansible 공식 디렉터리 예시, HashiCorp Standard Module Structure, Argo CD Best Practices,
Kustomize `base`/`overlays` 관례를 조합했다.

> **6판에서 구조를 단순화했다.** 5판은 `l1-infra/`·`l2-nodes/`와 번호가 붙은 playbook 10개,
> `modules/` 3개를 처음부터 만들었다. **구현 전에 과도하게 분리한 것이다.**
>
> HashiCorp의 Standard Module Structure는 **root module만 필수**이며 child module은 복잡도나
> 재사용 경계가 확인됐을 때 도입하고 **모듈 트리를 평평하게 유지**하라고 권한다. Ansible 공식
> 디렉터리 예시도 정답이 아니라 출발점이며 목적에 맞게 축소해도 된다고 명시한다.

```text
ALIGNER-PLATFORM/                         Public
├── README.md   LICENSE   SECURITY.md   CONTRIBUTING.md
├── Makefile                              make infra / inventory / site / verify
├── .gitignore                             §2.8.11
│
├── .github/
│   ├── CODEOWNERS                        ★ ESO·SecretStore 경로는 Platform Owner 승인 (§2.6.6)
│   └── workflows/
│       ├── lint.yml                      ansible-lint · yamllint · tflint · shellcheck
│       ├── render-manifests.yml           모든 overlay kustomize build 검증
│       ├── secret-scan.yml               gitleaks / trufflehog — Public 필수
│       └── contract-test.yml             주 1회 가비아 API 계약 검증 (§2.8.9)
│
├── infra/                                ← L1: 클라우드 리소스
│   ├── bootstrap/
│   │   ├── desired-infrastructure.yaml    gabiactl 목표 상태 (실 IP 는 변수)
│   │   └── security-groups.yaml           규칙 정본 — 별도 파일로 리뷰 대상 명확화
│   └── terraform/
│       └── environments/prod/            ★ root module 하나로 시작
│           ├── main.tf  variables.tf  outputs.tf  versions.tf  backend.tf
│           ├── backend.hcl.example
│           └── terraform.tfvars.example
│
├── ansible/                              ← L2: 노드·OS·K3s·Cilium
│   ├── ansible.cfg
│   ├── requirements.yml                  컬렉션 버전 고정 (kubernetes.core 등)
│   ├── inventories/example/              ★ 공개 — 스키마와 사용법만
│   │   ├── hosts.yml
│   │   └── group_vars/all.yml            k3s_version · cilium_version · CIDR
│   ├── playbooks/
│   │   ├── site.yml                      ★ 실행 순서를 여기 한 곳에서 관리
│   │   ├── verify.yml                    Gate 자동 검증 (assert)
│   │   └── teardown.yml                  재구축 리허설용
│   └── roles/
│       ├── preflight/                    OS·커널·디스크·사설망 사전 검사
│       ├── baseline/                     hostname · 시간 · swap · sysctl
│       ├── storage/                      Data-A/B 마운트 · mount guard
│       ├── management_network/           tasks/{tailscale,wireguard}.yml 분기
│       ├── firewall/                     ★ management_network 검증 후에만
│       ├── k3s/                          templates/config.yaml.j2
│       ├── cilium/                       files/cilium-values.yaml
│       └── argocd_bootstrap/             최초 1회만 (이후는 GitOps)
│
├── gitops/                               ← L3: Argo CD 가 감시하는 경로
│   ├── clusters/prod/root-app.yaml       app-of-apps 진입점
│   ├── infrastructure/
│   │   ├── controllers/                  sync-wave 0 — CRD 를 먼저 세운다
│   │   │   ├── traefik/  cert-manager/  external-secrets/
│   │   │   └── cloudnative-pg/  alloy/
│   │   └── configs/                      sync-wave 1 — CR 은 그 다음
│   │       ├── gateway/                  Gateway (HTTPRoute 는 앱이 소유)
│   │       ├── cluster-issuers/
│   │       ├── secret-stores/            ★ ClusterSecretStore (CODEOWNERS 대상)
│   │       ├── network-policies/
│   │       └── priority-classes/
│   ├── data/                             sync-wave 2
│   │   ├── postgres/                     CNPG Cluster
│   │   └── redis/                        emptyDir — PVC 없음 (§3.5)
│   └── apps/aligner-api/                 sync-wave 3
│       ├── base/
│       └── overlays/{normal,degraded,maintenance}/
│
├── docs/
│   ├── architecture/                     이 설계 문서 (실값 placeholder 화)
│   ├── adr/                              0001-cilium-day1.md 등
│   └── runbooks/                         계정·실제 접근값은 placeholder
│       ├── break-glass.md  etcd-restore.md  pg-pitr.md
│       ├── degraded-mode.md  node-replacement.md  wal-archive-failure.md
│       └── credential-rotation.md
│
└── .runtime/                             ★ 전체 Git ignore
    ├── inventory.yaml                    gabiactl / terraform output 산출물
    └── kubeconfig                        노드에서 가져온 것
```

**`controllers/` 와 `configs/` 를 나누는 이유** — CRD를 설치하는 컨트롤러가 sync-wave 0,
그 CRD를 쓰는 커스텀 리소스가 wave 1이다. 같은 wave에 두면 `ClusterSecretStore`가
`ExternalSecret` CRD보다 먼저 적용돼 실패한다. 디렉터리가 의존 순서를 표현한다.

### Terraform — `modules/`는 필요할 때만 추출한다

```text
infra/terraform/environments/prod/
├── main.tf   variables.tf   outputs.tf   versions.tf   backend.tf
```

같은 디렉터리의 `.tf` 파일은 **하나의 module로 함께 평가**된다. 파일을 나누는 것은 가독성을
위한 것이며 경계를 만드는 것이 아니다.

**다음 조건이 실제로 생겼을 때만** `modules/`를 추가한다.

```text
□ 같은 리소스 묶음을 두 번 이상 생성한다
□ Dev/Prod 등 복수 환경에서 동일 구성을 재사용한다
□ 네트워크·컴퓨트·LB 의 독립 테스트가 필요하다
□ 입력·출력 경계가 안정됐다
```

추출할 때도 **한 단계만** 쓴다(`modules/{network,compute,loadbalancer}`). 중첩 모듈은 만들지 않는다.

### Ansible — 실행 순서는 `site.yml` 한 곳에서 관리한다

```yaml
# ansible/playbooks/site.yml
- hosts: all
  become: true
  roles:
    - preflight
    - baseline
    - storage
    # ⚠️ 아래 두 role 의 순서를 절대 바꾸지 않는다.
    #    management_network 검증 전에 firewall 을 적용하면 3노드 동시 잠금이 된다.
    - management_network      # Tailscale 또는 WireGuard (freeze 결정, §1.5.1)
    - firewall                # 22/6443 공인망 차단 — break-glass 검증 후
    - k3s
    - cilium
    - argocd_bootstrap
```

5판은 `30-management-network.yml` → `35-firewall.yml`처럼 **파일명으로 순서를 강제**했다.
`site.yml`의 role 목록이 같은 효과를 내면서 **볼 곳이 한 군데**다. 순서 경고를 주석으로 박아
둔다.

### Inventory — L1과 L2의 유일한 인터페이스

```bash
gabiactl output --format ansible > .runtime/inventory.yaml
ansible-playbook -i .runtime/inventory.yaml ansible/playbooks/site.yml
```

Terraform으로 이관해도 `output`이 같은 파일을 채우면 L2는 무변경이다. **실제 inventory는 Git에
저장하지 않는다.** 공개 저장소에는 `inventories/example/`만 두어 스키마와 사용법을 보여준다.

### 설계 의도 네 가지

1. **디렉터리가 소유권 경계와 일치한다.** Argo CD는 `gitops/`만 감시하므로 `infra/`·`ansible/`
   커밋이 sync를 유발하지 않는다.
2. **운영 실값이 Git 밖에 있다.** `*.example`이 스키마를, `.runtime/`이 실행 결과를 담당한다.
   Public 여부와 무관하게 적용되는 원칙이다.
3. **`security-groups.yaml` 분리** — 규칙 20여 개가 다른 리소스와 섞이면 리뷰에서 놓친다.
   `AGENTS.md`가 `build.gradle.kts` 의존성을 최우선 리뷰 대상으로 둔 것과 같은 논리다.
4. **`CODEOWNERS`가 ESO 경로를 보호한다.** `ClusterSecretStore`·`ExternalSecret`에 대한 쓰기
   권한은 실제 Production Secret 접근 권한과 거의 동등하다(§2.6.6).

`overlays/{normal,degraded,maintenance}`는 각각 `../../base`를 참조하고 patch만 갖는다. 전환은
Argo CD Application의 `spec.source.path` 변경 1커밋 + sync이며 감사 흔적이 Git에 남는다.

### 2.8.11 Public 저장소의 비커밋 정책

```gitignore
# Terraform
**/.terraform/
*.tfstate
*.tfstate.*
*.tfplan
terraform.tfvars
backend.hcl
crash.log
crash.*.log

# Runtime — 생성물 전체
.runtime/

# Kubernetes
*.kubeconfig
kubeconfig

# Credentials
*.pem
*.key
*.p12
*.pfx
.env
.env.*
vault-password*
secrets/plaintext/

# Local
.idea/
.vscode/
.DS_Store
```

**`.terraform.lock.hcl`은 커밋한다.** Provider 버전과 checksum을 재현하기 위해서다.

**Terraform state와 plan은 IP·리소스 ID·cloud-init user_data를 포함할 수 있으므로 Public Git뿐
아니라 어떠한 Git 저장소에도 커밋하지 않는다.** State는 Versioning·암호화·Public Access 차단·
최소 권한 IAM이 적용된 **AWS S3 Remote Backend**에서 관리한다(§2.8.6).

**Public 저장소이므로 다음을 추가로 켠다.**

```text
□ GitHub secret scanning + push protection   커밋 시점에 차단
□ CI 의 gitleaks/trufflehog (secret-scan.yml)
□ 최초 공개 전 Git 전체 이력 스캔
□ Branch protection — main 직접 push 금지 · 필수 PR 리뷰
□ CODEOWNERS — GitOps 핵심 경로·ESO 경로
□ Actions 최소 permissions (`permissions: contents: read` 기본)
□ ★ Third-party Action 을 commit SHA 로 고정 (태그는 이동 가능하다)
□ Dependabot / Renovate — Public 저장소는 취약점 공개 대상이 된다
```

---

# 세션 3. Kotlin + Spring Boot 운영 최적화 가이드

전제: Kotlin 2.4.10 / JDK 25 (Amazon Corretto) / Spring Boot 4.1.0 / Spring Data JDBC.
노드는 `2 vCPU / 8GB` × 3이다. 이 사양이 아래 모든 숫자의 근거다.

## 3.1 자원 할당 원칙 — JVM은 일반 워크로드와 다르게 다룬다

### 원칙 1. 메모리는 `requests == limits` — 단 QoS는 **Burstable**이다

```yaml
resources:
  requests: { memory: 1536Mi }
  limits:   { memory: 1536Mi }   # 동일하게
```

> ⚠️ **정정** — 초판은 이 설정을 "Guaranteed QoS"라고 썼다. **틀렸다.** Kubernetes의
> Guaranteed는 파드의 **모든 컨테이너에서 CPU와 메모리 모두** request == limit이어야 한다.
> CPU가 `400m → 1500m`이므로 이 파드는 **Burstable**이다. PostgreSQL도 마찬가지다.
>
> 그렇다고 CPU를 억지로 맞춰 Guaranteed로 만들면 안 된다. 3 replica × 1500m = 4500m로
> allocatable 4800m의 94%를 API 하나가 점유해 다른 워크로드가 배치되지 않는다.
> **Burstable로 정확히 기재하고, 장애 대응은 degraded overlay로 한다(§3.5.2).**

**메모리 request == limit을 유지하는 이유는 QoS 등급 때문이 아니라 eviction 순위 때문이다.**
kubelet의 node-pressure eviction은 Burstable 파드 안에서 **`사용량 − request`가 큰 순서로**
축출한다. 사용량이 request와 같으면 초과분이 0이므로 Burstable 중에서 가장 늦게 축출된다.
JVM은 한 번 확보한 메모리를 OS에 거의 반납하지 않으므로 `requests < limits`로 두면 실사용이
항상 request를 크게 초과해 최우선 축출 대상이 된다.

또한 Kubernetes 메모리 limit 초과는 **스로틀링이 아니라 OOMKill**이다. CPU와 달리 완충이 없다.

### 원칙 2. 컨테이너 메모리는 heap이 아니다

```text
컨테이너 RSS = Java heap
             + Metaspace (클래스 메타데이터, Spring은 큼 — 100~200MB)
             + Code Cache (JIT 컴파일 결과 — 50~150MB)
             + Thread stacks (스레드 수 × 1MB — Tomcat 200스레드면 200MB)
             + Direct/Mapped ByteBuffer (NIO, JDBC 드라이버)
             + GC 구조체 (G1은 heap의 약 5~10%)
             + JVM 자체 native
```

`-Xmx`만 잡고 컨테이너 limit을 같은 값으로 주면 **반드시 OOMKill된다.** 실무 배분은 다음이다.

| 컨테이너 limit | `MaxRAMPercentage` | 예상 heap | non-heap 여유 |
| --- | --- | --- | --- |
| 1024Mi | 70 | ~717MB | ~307MB (빡빡함) |
| **1536Mi** | **70** | **~1075MB** | **~461MB (권장)** |
| 2048Mi | 75 | ~1536MB | ~512MB |

**Aligner API 권장값 (Phase 1 시작값)**

```yaml
env:
  - name: JAVA_TOOL_OPTIONS
    value: >-
      -XX:MaxRAMPercentage=70.0
      -XX:InitialRAMPercentage=50.0
      -XX:+UseG1GC
      -XX:+ExitOnOutOfMemoryError
      -XX:+HeapDumpOnOutOfMemoryError
      -XX:HeapDumpPath=/tmp/heapdump.hprof
      -XX:NativeMemoryTracking=summary
resources:
  requests: { cpu: 250m,  memory: 1536Mi }
  limits:   { cpu: 1500m, memory: 1536Mi }   # ← 2000m에서 하향 (§원칙 3)
volumeMounts:
  - { name: tmp, mountPath: /tmp }
volumes:
  - name: tmp
    emptyDir:
      sizeLimit: 2Gi          # heap dump가 노드 디스크를 채우지 못하게 상한
```

- `-Xmx` 고정값 대신 **`MaxRAMPercentage`** 를 쓴다. 컨테이너 limit을 바꿀 때 JVM 옵션을
  같이 고쳐야 하는 이중 관리가 사라진다. JDK 10+ `UseContainerSupport`가 기본 활성이므로
  cgroup limit을 정확히 읽는다.
- `InitialRAMPercentage=50` — heap을 처음부터 절반 확보해 시작 직후 heap 확장에 따른
  GC·CPU 스파이크를 줄인다. `requests == limits`이므로 미리 잡아도 손해가 없다.
- **`ExitOnOutOfMemoryError`** — OOM 발생 시 JVM이 반쯤 죽은 상태로 살아남아 liveness probe만
  통과하는 최악의 상황을 막는다. 즉시 종료해 Kubernetes가 재시작하게 한다.
- `NativeMemoryTracking=summary` — non-heap 실사용을 `jcmd VM.native_memory`로 측정해 아래
  hard cap 결정의 근거를 만든다. 오버헤드는 약 5%다.

> **초판에서 제거한 설정** — `-XX:MaxMetaspaceSize=256m`과 `-Xss512k`를 **Phase 1에서는 넣지
> 않는다.** 메모리 예측성은 올라가지만 그 대가가 크다.
>
> - `MaxMetaspaceSize` — Spring의 프록시·리플렉션 클래스가 늘면 **Metaspace OOM**이 난다.
>   컨테이너 OOMKill보다 원인 파악이 어려운 것은 사실이지만, 값을 근거 없이 정하면
>   정상 동작하던 앱이 배포 후 죽는다.
> - `-Xss512k` — 기본값(x64에서 1MB)의 절반이다. Spring 프록시 체인·JDBC 드라이버의 깊은
>   호출 스택에서 **StackOverflowError** 위험이 있다.
>
> **Phase 2에서 NMT·Micrometer·JFR로 실측한 뒤** 실사용의 1.5배 수준으로 상한을 건다.
> 예측성을 위해 하드 캡을 먼저 거는 것은 순서가 거꾸로다.

**heap dump 취급** — dump 파일은 1GB를 넘길 수 있고 **요청 데이터·토큰·개인정보가 그대로
들어간다.** `readOnlyRootFilesystem: true`와 함께 쓰려면 `/tmp`를 `emptyDir`로 마운트해야
하는데, 다음 규칙을 함께 정한다.

```text
저장   emptyDir sizeLimit 2Gi (노드 디스크 보호). 파드 삭제 시 함께 소멸
회수   OOM 알림 수신 후 kubectl cp로 즉시 로컬 회수 (재시작 전에)
분석   로컬 격리 환경에서만. 공유 저장소·이슈 트래커에 업로드 금지
폐기   분석 완료 후 즉시 삭제. 보관 필요 시 암호화 후 패스워드 매니저 참조로 기록
```

### 원칙 3. CPU limit은 `availableProcessors()`가 2가 되는 최솟값으로

```yaml
requests: { cpu: 250m }    # 정상 상태 실측 기반 (스케줄링 근거)
limits:   { cpu: 1500m }   # 버스트 허용 + Control Plane에 500m 여유
```

**이유 1 — `availableProcessors()`가 CPU limit에서 계산된다.** 이게 가장 자주 놓치는 함정이다.
JDK는 `ceil(cpu_quota / cpu_period)`로 코어 수를 인식한다.

| CPU limit | JVM `availableProcessors()` | 영향 |
| --- | --- | --- |
| 미설정 | 2 (노드 코어 수) | 정상. 단 노이지 네이버 위험 |
| 2000m | 2 | 정상. 단 노드 코어 전부를 쓸 수 있음 |
| **1500m** | **ceil(1.5) = 2** | **정상 + Control Plane에 500m 여유** ← 채택 |
| 1200m | ceil(1.2) = 2 | 정상. 버스트 여유가 줄어듦 |
| 1000m | ceil(1.0) = 1 | G1 GC 워커 1개, `ForkJoinPool.commonPool` 병렬도 0, **Kotlin `Dispatchers.Default` 병렬도 1** |

`Dispatchers.Default`는 `availableProcessors()` 기반으로 스레드 풀 크기를 정한다. CPU limit을
1000m로 주면 **코루틴 병렬 처리가 사실상 사라진다.** Kotlin 프로젝트에서 이 함정은 치명적이다.

> **초판 정정** — 초판은 `limits: 2000m`(노드 코어 전부)을 권했다. `availableProcessors()`가
> `ceil()`로 계산되므로 **1500m에서도 2가 유지된다.** 즉 2000m은 불필요하게 공격적이었다.
> 통합형 노드에서는 같은 노드에 kube-apiserver·etcd·PostgreSQL이 있으므로, API 하나가
> 노드 코어 전부를 쓸 수 있게 두는 것은 Control Plane을 위험에 노출한다. **1500m으로 하향한다.**

**이유 2 — CFS 스로틀링과 GC/JIT의 상성이 나쁘다.** CPU limit은 100ms 주기 quota로 구현된다.
JIT 컴파일러 스레드와 G1 GC 워커가 병렬로 돌면 주기 초반에 quota를 소진하고 나머지
수십 ms를 강제 대기한다. 이 대기가 **GC pause에 그대로 더해져** p99 지연이 수백 ms 튄다.
정상 상태 CPU 사용률이 20%인데도 스로틀링이 발생하는 전형적 원인이다. 1500m은 2000m보다
스로틀링 확률이 약간 높으므로 **원칙 4의 계측이 필수다.**

**limit을 아예 제거하지 않는 이유** — 6 vCPU 소규모 클러스터에서 폭주하는 파드 하나가
Control Plane(kube-apiserver·etcd)의 CPU까지 빼앗으면 클러스터 전체가 흔들린다.
1500m 상한은 그 최악을 막는 안전선이다. 추가로 namespace에 `LimitRange`를 걸어 누락 시
기본값이 적용되게 한다.

**Phase 3 부하 테스트에서 재조정한다** — 스로틀 비율이 5%를 넘으면 1800m까지 올리고,
Control Plane의 etcd fsync p99가 악화되면 1200m로 내린다. 두 지표를 함께 본다.

### 원칙 4. 스로틀링을 계측한다

```promql
# 5분간 스로틀 비율 — 0.05(5%) 초과면 CPU limit 상향 검토
rate(container_cpu_cfs_throttled_periods_total{pod=~"aligner-api-.*"}[5m])
  / rate(container_cpu_cfs_periods_total{pod=~"aligner-api-.*"}[5m])
```

이 값과 `jvm_gc_pause_seconds`를 같은 대시보드에 올려 상관을 본다. 자원 튜닝은 추측이 아니라
이 두 그래프로 한다.

## 3.2 시작 시간 단축 — CPU 스파이크의 근본 대응

JVM의 초기 CPU 부하는 클래스 로딩·검증·JIT 워밍업에서 나온다. probe로 시간을 벌어주는 것은
증상 완화이고, 근본 대응은 **시작 자체를 짧게 만드는 것**이다. 6 vCPU 클러스터에서
파드 재시작이 잦으면 시작 스파이크가 다른 파드의 지연으로 전파된다.

| 기법 | 효과 | 적용 |
| --- | --- | --- |
| **CDS (Class Data Sharing)** | 클래스 로딩·검증 결과를 아카이브로 재사용. 시작 20~40% 단축 | Spring Boot 3.3+ 지원. Paketo buildpack `BP_JVM_CDS_ENABLED=true`로 이미지 빌드 시 자동 생성 |
| **AOT 캐시 (JEP 483, JDK 24+)** | CDS를 확장해 링킹까지 캐시. 추가 단축 | JDK 25 사용 중이므로 적용 가능. **Spring Boot 4에서 실측 후 채택** |
| Spring AOT 처리 | 리플렉션·프록시를 빌드 시점에 해석 | `bootJar` + `springBoot { }` AOT. GraalVM 없이 JVM에서도 이득 |
| `AutoCreateSharedArchive` | 첫 실행 시 아카이브 자동 생성 | `-XX:+AutoCreateSharedArchive -XX:SharedArchiveFile=/tmp/app.jsa`. 컨테이너에서는 빌드 시점 생성이 낫다 |
| ~~`TieredStopAtLevel=1`~~ | 시작은 빠르지만 **정상 상태 성능이 크게 저하** | 상시 API에는 금지. CronJob·Batch에만 |
| ~~`spring.main.lazy-initialization=true`~~ | 시작은 빠르지만 첫 요청이 느려짐 | **금지**. readiness 통과 후 실사용자가 지연을 맞는다 |

**권장 이미지 빌드 (Paketo buildpack)**

```kotlin
// build.gradle.kts
tasks.named<BootBuildImage>("bootBuildImage") {
    environment.set(mapOf(
        "BP_JVM_VERSION"     to "25",
        "BP_JVM_CDS_ENABLED" to "true",   // CDS 아카이브를 이미지에 포함
        "BP_SPRING_AOT_ENABLED" to "true"
    ))
}
```

buildpack은 계층 분리(의존성/애플리케이션)를 자동으로 해주므로 이미지 pull 시간도 줄어든다.
`Dockerfile`을 직접 관리하는 것보다 CDS·계층 최적화를 놓칠 위험이 적다.

## 3.3 Probe 전략

### 절대 규칙: liveness와 readiness에 외부 의존성을 넣지 않는다

이것이 Probe 설계에서 가장 중요한 규칙이고 가장 많이 위반된다.

```text
liveness에 DB 헬스체크를 넣으면 →  DB 장애 시 모든 API 파드가 재시작 폭풍에 빠진다.
                                    DB가 돌아와도 파드가 CrashLoopBackOff에서 못 나온다.

readiness에 DB 헬스체크를 넣으면 →  DB 장애 시 모든 파드가 Endpoint에서 제거된다.
                                    503이 아니라 연결 거부가 되어 원인 파악이 어려워지고,
                                    DB가 5초만 끊겨도 전면 장애가 된다.
```

DB 장애는 DB 알림으로 감지한다. Probe의 역할은 “이 파드 프로세스가 살아 있는가 / 트래픽을
받을 준비가 됐는가”뿐이다.

### Spring Boot 설정

```yaml
# application.yaml
management:
  server:
    port: 8081                    # 관리 포트 분리 — Service·LB로 노출하지 않음
  endpoints:
    web:
      exposure:
        include: health,prometheus,info
  endpoint:
    health:
      probes:
        enabled: true             # /health/liveness, /health/readiness 활성화
      group:
        liveness:
          include: livenessState          # ★ 애플리케이션 자체 상태만
        readiness:
          include: readinessState         # ★ db·redis 지시자 제외
      show-details: never
  health:
    db:
      enabled: true               # /actuator/health 에는 노출 (모니터링용)
    redis:
      enabled: true

server:
  shutdown: graceful

spring:
  lifecycle:
    timeout-per-shutdown-phase: 25s
```

`group.readiness.include: readinessState`를 **명시**하는 것이 핵심이다. 그룹을 정의하지 않은
상태에서 지시자 구성이 바뀌면 DB 헬스가 readiness에 섞여 들어올 수 있다. 명시적으로 못 박는다.

### Deployment Probe

```yaml
containers:
  - name: aligner-api
    ports:
      - { name: http,       containerPort: 8080 }
      - { name: management,  containerPort: 8081 }

    # 1) startupProbe — 시작 지연을 전담 흡수. 이게 있으면 liveness의
    #    initialDelaySeconds를 0으로 둘 수 있다.
    startupProbe:
      httpGet: { path: /actuator/health/liveness, port: management }
      periodSeconds: 5
      failureThreshold: 24          # 최대 120초 허용 (CDS 적용 시 실측 15~25초)
      timeoutSeconds: 3

    # 2) readinessProbe — 트래픽 수용 여부. 실패하면 Endpoint에서만 제거(재시작 안 함)
    readinessProbe:
      httpGet: { path: /actuator/health/readiness, port: management }
      periodSeconds: 5
      failureThreshold: 3           # 15초 연속 실패 시 트래픽 차단
      successThreshold: 1
      timeoutSeconds: 2

    # 3) livenessProbe — 프로세스 데드락 등 회복 불가 상태만 감지. 관대하게.
    livenessProbe:
      httpGet: { path: /actuator/health/liveness, port: management }
      periodSeconds: 10
      failureThreshold: 6           # 60초 연속 실패 시에만 재시작
      timeoutSeconds: 3
```

**설계 의도**

| Probe | 실패 시 동작 | 튜닝 방향 |
| --- | --- | --- |
| startup | 임계 초과 시 재시작 | **관대하게** — 짧으면 정상 앱이 무한 재시작한다 |
| readiness | Endpoint 제거 (재시작 없음) | **민감하게** — 준비 안 된 파드에 트래픽이 가면 5xx |
| liveness | **컨테이너 재시작** | **가장 관대하게** — 오탐의 대가가 가장 크다 |

liveness `failureThreshold: 6`(60초)은 일반 권장보다 관대하다. 의도적이다. GC full pause,
일시적 CPU 스로틀링, 노드 I/O 지연으로 3초 타임아웃이 몇 번 실패하는 것은 흔하고, 그때
재시작하면 상황을 악화시킨다. 재시작으로만 고칠 수 있는 상태(데드락)는 60초 뒤에도 여전히
같은 상태다.

**관리 포트 8081 분리** — probe 트래픽이 애플리케이션 스레드 풀·액세스 로그·메트릭을 오염시키지
않는다. Service는 8080만 노출하고 8081은 NetworkPolicy로 kubelet·Alloy에만 허용한다.

## 3.4 Graceful Shutdown — 무중단 배포의 실제 조건

`server.shutdown: graceful` 한 줄로 끝나지 않는다. **Endpoint 전파와 SIGTERM이 경쟁**하기
때문이다.

```text
Pod 삭제 요청
   │
   ├──(A) kubelet → 컨테이너에 SIGTERM  ─────────────► 즉시
   │
   └──(B) EndpointSlice 갱신 → kube-proxy / Traefik 반영 ──► 수백 ms ~ 수 초

A가 B보다 빠르면: 이미 종료를 시작한 파드로 새 요청이 계속 들어와 연결 거부(502/504)
```

Kubernetes는 이 순서를 보장하지 않는다. **`preStop` 훅으로 A를 지연**시켜 해결한다.

```yaml
spec:
  terminationGracePeriodSeconds: 45      # preStop(5s) + 앱 graceful(25s) + 여유
  containers:
    - name: aligner-api
      lifecycle:
        preStop:
          exec:
            command: ["sh", "-c", "sleep 5"]   # B가 전파될 시간을 벌어준다
```

**타임라인**

```text
t=0     Pod 삭제 → EndpointSlice에서 제거 시작 + preStop 시작
t=0~5   preStop sleep. 앱은 아직 정상 동작 — 진행 중 요청과 신규 요청 모두 처리
t=~1    Traefik이 Endpoint 제거를 반영 → 신규 요청 유입 중단
t=5     preStop 종료 → SIGTERM 전달
t=5     Spring Boot graceful shutdown 시작:
          · 커넥터가 신규 연결 수락 중단
          · 진행 중 요청 완료 대기 (최대 25s)
          · readiness가 OUT_OF_SERVICE로 전환 (Spring Boot가 자동 처리)
t=5~30  진행 중 요청 완료 → ApplicationContext close → HikariCP·코루틴 정리
t=≤45   프로세스 종료 (초과 시 SIGKILL)
```

`terminationGracePeriodSeconds`(45) > `preStop`(5) + `timeout-per-shutdown-phase`(25) 관계를
반드시 지킨다. 역전되면 SIGKILL이 진행 중 요청을 끊는다.

**Kotlin 코루틴 정리**

```kotlin
@Component
class BackgroundScope : DisposableBean {
    private val job = SupervisorJob()
    val scope = CoroutineScope(job + Dispatchers.IO)

    // ApplicationContext close 시 호출 — timeout-per-shutdown-phase 안에서 끝나야 한다
    override fun destroy() = runBlocking {
        withTimeoutOrNull(20_000) { job.cancelAndJoin() }
        Unit
    }
}
```

`GlobalScope`를 쓰면 shutdown 시점에 취소할 방법이 없어 SIGKILL까지 살아남는다. 구조화된
동시성을 유지해야 graceful shutdown이 성립한다.

**Spring Data JDBC / HikariCP**

```yaml
spring:
  datasource:
    hikari:
      maximum-pool-size: 10        # ★ 산정 근거 아래
      minimum-idle: 5
      connection-timeout: 3000     # 3초 — 무한 대기 금지
      max-lifetime: 900000         # 15분. CNPG failover 후 stale 연결을 순환시킨다
      keepalive-time: 300000       # 5분
      validation-timeout: 2000
```

**풀 크기 산정** — PostgreSQL `max_connections: 120`(§2.5.2)을 넘지 않아야 한다.

```text
API 3 replica × 10 = 30
Batch/Worker 1 × 5  =  5
CNPG 내부(복제·모니터링·백업)  ≈ 15
운영자 수동 접속 여유          ≈ 10
─────────────────────────────────
합계 60  <  max_connections 120   ✅ HPA로 API가 4~5개까지 늘어도 안전
```

풀을 크게 잡는 것이 성능에 유리하다는 직관은 틀렸다. 2 vCPU 노드에서 동시 실행 가능한 쿼리는
소수이고, 풀이 크면 DB 쪽 컨텍스트 스위칭과 메모리(`work_mem` × 연결 수)만 늘어난다.

## 3.5 배치·스케줄링과 클러스터 자원 검증

### 워크로드 배치

```yaml
# 노드 분산 — 3노드에 2~3 replica
topologySpreadConstraints:
  - maxSkew: 1
    topologyKey: kubernetes.io/hostname
    whenUnsatisfiable: DoNotSchedule       # 같은 노드에 몰리는 것을 금지
    labelSelector:
      matchLabels: { app: aligner-api }

# 자발적 중단(노드 drain·업그레이드)에서 최소 가용성 보장
---
apiVersion: policy/v1
kind: PodDisruptionBudget
spec:
  maxUnavailable: 1                        # minAvailable보다 replica 변동에 견고
  selector:
    matchLabels: { app: aligner-api }

# 자원 압박 시 축출 순서
---
priorityClassName: aligner-api-high        # 시스템 > API > Batch
```

`PDB`에 `minAvailable` 대신 **`maxUnavailable: 1`** 을 쓴다. HPA로 replica가 2↔5로 변할 때
`minAvailable: 2`는 replica 2에서 drain을 완전히 막아버리는 반면 `maxUnavailable: 1`은
항상 “한 번에 하나씩”으로 동작한다.

### HPA — JVM에서 메모리 기반 스케일링은 쓰지 않는다

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
spec:
  minReplicas: 2
  maxReplicas: 4                     # 노드 3개 · 자원 여유 기준 상한
  metrics:
    - type: Resource
      resource:
        name: cpu                    # ★ CPU만 사용
        target: { type: Utilization, averageUtilization: 70 }
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
    scaleDown:
      stabilizationWindowSeconds: 300   # 5분 — JVM 워밍업 비용 때문에 보수적으로
```

**메모리 메트릭을 쓰지 않는 이유** — JVM RSS는 부하가 빠져도 내려오지 않으므로 메모리 기반
HPA는 **스케일아웃만 하고 스케일인을 하지 않는다.** replica가 상한에 붙어 고정되고
자원이 잠긴다.

**CPU 기준 70%의 주의점** — HPA는 `requests.cpu`(400m) 대비 사용률로 계산한다. 즉 280m를
넘으면 스케일아웃한다. JIT 워밍업 구간에서 CPU가 일시적으로 튀어 불필요한 스케일아웃이
발생할 수 있으므로 `scaleUp.stabilizationWindowSeconds: 30`으로 완충한다. 정확한 스케일링
지표는 요청률·큐 길이지만 Prometheus Adapter가 필요하므로 이 규모에서는 CPU로 시작하고
Phase 3 부하 테스트 결과로 임계를 조정한다.

### 클러스터 전체 자원 검증 — 노드 1대 장애를 견디는가

이 계산이 §1.2에서 `2/8 × 3`을 선택한 최종 근거다. **분모는 물리 자원이 아니라 kubelet이
계산하는 allocatable이다.** 초판은 메모리에만 reserved를 반영하고 CPU는 물리 코어(6000m)를
분모로 써서 사용률을 크게 과소평가했다. 이 절은 그 오류를 바로잡은 것이다.

**노드당 allocatable**

```text
[CPU]                                  [메모리]
물리            2000m                  물리                    8192Mi
- system-reserved 200m                 - system-reserved       1024Mi   ← 512Mi에서 상향
- kube-reserved   200m                 - kube-reserved          512Mi
────────────────────                   - eviction-hard          300Mi
allocatable     1600m                  ────────────────────────────────
                                       allocatable             6356Mi

3노드 총 allocatable      CPU 4800m   /  메모리 18.6Gi
1노드 장애 시 allocatable  CPU 3200m   /  메모리 12.4Gi   ← 이 두 값이 상한선이다
```

`system-reserved` 메모리를 512Mi → **1024Mi로 올린 이유** — 통합형 노드에서는 kube-apiserver·
etcd·scheduler·controller-manager가 `k3s.service` 프로세스로 system.slice에 있고 실사용이
약 700Mi다. 512Mi로 잡으면 예약이 부족해 그 초과분이 파드 공간을 침식한다. 초판은 이 값을
따로 한 번 더 뺐는데(`- K3s server 실사용 ~700Mi`) 그것은 **이중계산**이었다. 예약값을
올리고 별도 차감을 제거하는 것이 맞다.

> ⚠️ `system-reserved`·`kube-reserved`는 **allocatable 계산에만 반영되고 자원을 전용으로
> 확보하지 않는다.** 실제 격리에는 `--enforce-node-allocatable`과 reserved cgroup 지정이
> 필요하다. §1.2.2의 `CPUWeight`도 경합 시 상대적 우선순위이지 보장이 아니다.
> **Phase 1 완료 조건에 `kubectl describe node` 실측값으로 이 표를 교체한다.**

**정상 모드 requests**

아래 값은 실측 전 추정치다. **Phase 2에서 `kubectl top` p95 실측치로 교체한다.**
`필수` 열은 **1노드 장애 시 반드시 살아 있어야 하는 워크로드**를 표시한다.

| 워크로드 | 개수 | CPU req | Mem req | CPU 합 | Mem 합 | 필수 |
| --- | --- | --- | --- | --- | --- | --- |
| **Cilium agent** (DaemonSet) | 3 | 100m | 300Mi | 300m | 900Mi | ✅ |
| **Cilium operator** | 2 | 50m | 128Mi | 100m | 256Mi | ✅ |
| Traefik | 3 | 100m | 128Mi | 300m | 384Mi | ✅ |
| CoreDNS | 2 | 100m | 170Mi | 200m | 340Mi | ✅ |
| metrics-server | 1 | 50m | 200Mi | 50m | 200Mi | ✅ (HPA) |
| local-path-provisioner | 1 | 25m | 64Mi | 25m | 64Mi | ✅ |
| cert-manager (3 pods) | 3 | 25m | 96Mi | 75m | 288Mi | ✅ |
| **external-secrets (ESO)** | 1 | 50m | 150Mi | 50m | 150Mi | ✅ |
| Argo CD — app-controller | 1 | 150m | 200Mi | 150m | 200Mi | ✅ |
| Argo CD — repo·server·redis·dex | 4 | — | — | 250m | 440Mi | ✗ |
| Grafana Alloy (DaemonSet) | 3 | 80m | 256Mi | 240m | 768Mi | ✅ |
| kube-state-metrics | 1 | 25m | 128Mi | 25m | 128Mi | ✗ |
| CNPG operator | 1 | 50m | 200Mi | 50m | 200Mi | ✅ |
| **PostgreSQL (CNPG)** | 2 | 250m | 2048Mi | 500m | **4096Mi** | ✅ |
| Redis (emptyDir 캐시) | 1 | 50m | 256Mi | 50m | 256Mi | ✅ |
| **Aligner API** | 3 | 250m | 1536Mi | 750m | **4608Mi** | ✅ (2개) |
| Worker / Batch | 1 | 150m | 1024Mi | 150m | 1024Mi | ✗ |
| **합계 (약 33 pods)** | | | | **3265m** | **13.97Gi** | |

> **Redis를 512Mi → 256Mi로 낮추고 PVC를 제거했다**(6판). 순수 캐시이므로 유실을 허용하며,
> `emptyDir`이면 **노드 장애 시 다른 노드로 자유롭게 재스케줄된다.** local-path PVC는 노드에
> 고정되어 재스케줄을 막으므로 1노드 장애 생존 요건과 충돌한다.
>
> **Cilium 초기값 주의** — 공식 Helm 기본값은 agent `resources: {}`로 강제 request가 없다.
> `100m / 300Mi`는 실측 전 보수적 초기값이며 **Phase 1 Gate에서 교체한다**(§2.3).

### ⚠️ 설계 요구 — 1노드 장애는 사람 개입 없이 견뎌야 한다

> **6판에서 요구사항을 강화했다.** 5판은 "1노드 장애 시 메모리 109% 초과 → degraded overlay로
> 전환해야 수용"이라고 썼다. **그건 HA가 아니다.** 노드가 죽으면 사람이 sync를 하기 전까지
> 서비스가 불안정하다는 뜻이고, 새벽 3시에 아무도 없으면 그대로 방치된다.
>
> **정정된 요구사항: `normal` overlay 자체가 1노드 장애를 자동 생존해야 한다.**
> 기준은 **필수 워크로드 request 합계가 2노드 allocatable의 85% 이하**다.

**노드당 allocatable** (§2.1 `kubelet-arg` 기준)

```text
[CPU]                          [메모리]
물리            2000m          물리                8192Mi
- system-reserved 200m         - system-reserved   1024Mi
- kube-reserved   200m         - kube-reserved      512Mi
────────────────────           - eviction-hard      300Mi
allocatable     1600m          ────────────────────────────
                               allocatable         6356Mi

3노드   CPU 4800m / 메모리 18.6Gi
2노드   CPU 3200m / 메모리 12.4Gi     ← 이 값이 상한선이다
목표 85%  CPU 2720m / 메모리 10.5Gi
```

**1노드 장애 시 살아야 하는 집합** — DaemonSet은 죽은 노드분이 빠지고, API는 2 replica가 남는다.

| 워크로드 | 생존 구성 | CPU | Mem |
| --- | --- | --- | --- |
| Cilium agent | 2 (DaemonSet) | 200m | 600Mi |
| Cilium operator | 2 | 100m | 256Mi |
| Traefik | 2 (PDB minAvailable 2) | 200m | 256Mi |
| CoreDNS | 2 | 200m | 340Mi |
| metrics-server · local-path | 1 · 1 | 75m | 264Mi |
| cert-manager | 3 | 75m | 288Mi |
| external-secrets | 1 | 50m | 150Mi |
| Argo CD app-controller | 1 | 150m | 200Mi |
| Grafana Alloy | 2 (DaemonSet) | 160m | 512Mi |
| CNPG operator | 1 | 50m | 200Mi |
| **PostgreSQL** | 2 | 500m | 4096Mi |
| Redis | 1 | 50m | 256Mi |
| **Aligner API** | **2** | 500m | 3072Mi |
| **필수 합계** | | **2310m** | **10.24Gi** |

**검증 결과**

| 상황 | CPU | 메모리 | 판정 |
| --- | --- | --- | --- |
| 정상 3노드 (전체) | 3265 / 4800m = **68%** | 13.97 / 18.6Gi = **75%** | ✅ |
| **1노드 장애 · 필수 집합만** | 2310 / 3200m = **72%** | **10.24 / 12.4Gi = 82.6%** | ✅ **85% 이하 충족** |
| 1노드 장애 · 비필수 포함 | 3265 / 3200m = 102% | 13.7 / 12.4Gi = 110% | 비필수가 `Pending` |

**1노드 장애 시 자동으로 벌어지는 일**

```text
1. 죽은 노드의 파드가 사라진다 (DaemonSet 2개분은 재스케줄되지 않는다)
2. 스케줄러가 남은 파드를 2노드에 재배치한다
3. PriorityClass 순서에 따라 필수 파드가 먼저 자리를 얻는다
   → 필요하면 preemption 으로 비필수 파드를 밀어낸다 (§3.5.1)
4. 비필수 파드(Worker/Batch · Argo CD UI · kube-state-metrics)는 Pending 으로 남는다
5. 서비스는 API 2 replica + PostgreSQL 2 instance 로 계속 동작한다   ← 사람 개입 없음
```

**`Pending` 파드가 남는 것은 정상 동작이다.** 장애가 있다는 신호이며,
`kube_pod_status_unschedulable` 알림이 발화한다(§2.7). 서비스 가용성과는 무관하다.

> ### ⚠️ 집계 용량이 맞아도 스케줄링이 성공한다는 보장은 아니다
>
> 위 82.6%는 **집계(aggregate) 용량 계산**이다. 계산은 맞지만 실제 배치는 다음 제약이 **동시에**
> 작동한다.
>
> ```text
> PostgreSQL anti-affinity (primary·standby 를 다른 노드에)
> Aligner API topologySpreadConstraints
> Traefik 노드별 1개 (externalTrafficPolicy: Local 의 전제)
> DaemonSet 의 노드별 고정 비용
> PodDisruptionBudget
> 개별 Pod 의 request 단위 (조각화 — 남은 공간이 흩어져 있으면 큰 Pod 가 안 들어간다)
> ```
>
> 특히 **PostgreSQL 2048Mi 두 개가 서로 다른 노드에 있어야 한다**는 제약과 API 1536Mi가 겹치면,
> 총합은 맞는데 특정 노드에 자리가 없어 Pending이 될 수 있다.
>
> **따라서 Gate는 계산이 아니라 실증이어야 한다. 실제로 VM 한 대를 정지시켜 확인한다.**
>
> ```text
> □ 가비아 콘솔에서 VM 한 대 강제 정지 (graceful shutdown 아님)
> □ 필수 Pod 전부 10분 이내 Running/Ready
> □ 필수 Pod Pending 0개
> □ 두 생존 노드 각각의 memory requests 합계 확인 (한쪽만 포화되지 않았는지)
> □ PostgreSQL primary·standby 가 서로 다른 노드에 존재
> □ Aligner API 최소 2개 Ready
> □ Traefik 이 두 노드 모두에 존재 (LB 헬스체크 통과)
> □ etcd fsync p99 · API server latency 허용 범위 유지
> □ 비필수 Pod 만 Pending (Worker/Batch · Argo CD UI · kube-state-metrics)
> ```

**추정치가 틀리면 어떻게 되는가** — 필수 합계가 85%를 넘거나 조각화로 배치가 실패하면 필수 파드도
Pending이 될 수 있다. 따라서 **Phase 1·2의 실측이 이 설계의 전제 조건**이다. 초과가 확인되면
순서대로 조정한다.

```text
1. Cilium agent · Alloy 의 request 를 실측치로 하향 (초기값이 과대할 가능성)
2. PostgreSQL 2048Mi → 실측 기반 하향 (메모리 requests 의 29% 를 차지한다)
3. Aligner API 1536Mi → NMT·JFR 실측 기반 하향 (§3.2)
4. 위로도 부족하면 Cilium 을 포기하고 Flannel 로 재구축 (§2.3 Gate)
```

### 3.5.1 PriorityClass의 실제 동작 범위

PriorityClass는 **필수 파드의 스케줄링 가능성을 높이는 보조 장치**다. 결정적인 축소 수단이 아니다.

| 메커니즘 | 작동 조건 | 이 설계에서의 의미 |
| --- | --- | --- |
| **스케줄러 preemption** | 높은 우선순위 파드가 Pending이고, 낮은 우선순위 파드를 제거하면 배치 가능할 때 | CPU·메모리 부족으로 API가 Pending이면 **작동한다.** 다만 **총수요를 줄이지 않고 누가 실행될지만 정한다** — 축출된 파드는 계속 Pending으로 남아 재시도 루프를 돈다 |
| **kubelet node-pressure eviction** | 메모리·디스크 압박 시 | 우선순위만 보지 않고 **request 초과 사용량과 함께** 순위를 정한다. **CPU는 compressible resource라 축출 대상이 아니다** |
| PDB | 자발적 중단(drain·업그레이드) | 노드의 비자발적 장애를 막지 않는다. preemption 과정에서도 best-effort다 |

따라서 자원 축소는 PriorityClass에 맡기지 않고 **명시적인 degraded overlay로 수행한다.**
PriorityClass는 그 전환이 완료되기 전 과도기에 무엇이 먼저 자리를 얻을지 정하는 역할만 한다.

```yaml
# PriorityClass — 과도기 스케줄링 우선순위 (축소 수단이 아님)
system-node-critical  (K3s 기본)   : CoreDNS, Traefik, Alloy
aligner-critical      value: 1000  : PostgreSQL, CNPG operator, Argo CD app-controller
aligner-high          value: 500   : Aligner API
aligner-normal        value: 100   : Redis, Worker / Batch
aligner-low           value: 10    : Argo CD server·dex(UI), kube-state-metrics
```

### 3.5.2 세 가지 overlay — degraded는 생존 필수 절차가 아니다

> **6판에서 degraded의 역할을 바꿨다.** 5판은 degraded를 "1노드 장애 생존의 필수 절차"로 뒀다.
> **틀렸다.** 생존은 `normal`이 자동으로 해야 하고(§위 검증), degraded는 그 다음 문제다.

| overlay | 언제 쓰는가 | 목적 |
| --- | --- | --- |
| **`normal`** | 평상시 | **1노드 장애를 사람 개입 없이 자동 생존한다** |
| **`degraded`** | 노드 장애가 **장기화**될 때 (수 시간 이상) | Pending 파드 정리 + 여유 확보 + 배포 차단 |
| **`maintenance`** | 계획 작업 (업그레이드·키 회전·데이터 복구) | 배포 차단 + 축소 |

**`degraded`가 하는 일** — 생존이 아니라 **정리와 여유 확보**다.

| 항목 | normal | degraded | 절감 |
| --- | --- | --- | --- |
| Worker / Batch CronJob | 활성 | **suspend: true** | −150m / −1024Mi |
| Argo CD server · dex · repo · redis | 활성 | **replicas: 0** | −250m / −440Mi |
| kube-state-metrics | 활성 | **replicas: 0** | −25m / −128Mi |
| Aligner API replicas | 3 | **2** (Pending 1개를 명시적으로 제거) | −250m / −1536Mi |
| **Cilium · CoreDNS · Traefik · ESO · CNPG · PostgreSQL · Redis** | 활성 | **전부 활성 유지** | — |
| **합계** | 3265m / 13.97Gi | **2590m / 10.87Gi** | **−675m / −3.1Gi** |

**degraded로 얻는 것**

```text
□ Pending 파드가 사라져 클러스터 상태가 깨끗해진다 (알림 노이즈 감소)
□ 남은 2노드에 여유가 생겨 PostgreSQL standby 재생성·재배치가 원활해진다
□ Argo CD UI 를 내려 장애 중 실수 sync 를 물리적으로 막는다
□ 장기 장애 중 자원 압박으로 인한 2차 축출 위험을 낮춘다
```

**Argo CD application-controller는 반드시 유지한다.** degraded overlay를 sync하는 주체이므로
함께 내리면 전환 자체가 불가능해진다. UI(server·dex·repo·redis)만 내린다.

**Cilium은 어느 overlay에서도 건드리지 않는다.** CNI를 줄이면 클러스터 네트워크가 끊기고
그 상태에서는 overlay를 되돌릴 수도 없다. `system-node-critical` 우선순위를 유지한다.

**degraded / maintenance 상태의 운영 규칙**

```text
금지  — 애플리케이션 배포, K3s·Traefik·CNPG 업그레이드, 노드 drain, 스키마 변경
       secrets-encrypt 키 회전 (maintenance 에서만 허용)
필수  — Grafana Cloud 알림으로 상태 공지, 복구 목표 시각 공유
해제  — 노드 복구 확인 → CNPG standby 재생성 완료 확인 → normal overlay sync
```

**전환 방법** — Argo CD Application의 `spec.source.path`를 변경하는 1커밋 + sync다.
감사 흔적이 Git에 남고 되돌리기가 `git revert`다. 자동 전환은 하지 않는다 — 오탐으로 정상
상태에서 축소되면 더 나쁘다.

**Aligner API replica 3의 근거** — `topologySpreadConstraints`로 노드마다 1개씩 배치되므로
어느 노드가 죽어도 2개가 남는다. replica 2면 죽은 노드에 1개가 있어 순간적으로 1개만 남는다.
3노드 클러스터에서 replica 3은 낭비가 아니라 최소값이다.

## 3.6 Spring Boot 컨테이너 체크리스트

배포 전 확인 항목이다. 하나라도 빠지면 운영 중 사고로 나타난다.

| # | 항목 | 확인 |
| --- | --- | --- |
| 1 | `requests.memory == limits.memory` | 필수 |
| 2 | `MaxRAMPercentage` 사용, `-Xmx` 고정값 없음 | 필수 |
| 3 | `limits.cpu ≥ 2000m` (`availableProcessors()` = 2 확보) | 필수 |
| 4 | `MaxMetaspaceSize` 상한 설정 | 필수 |
| 5 | `ExitOnOutOfMemoryError` 설정 | 필수 |
| 6 | startup / readiness / liveness 3종 모두 설정 | 필수 |
| 7 | liveness·readiness에 DB·Redis 헬스체크 **없음** | 필수 |
| 8 | 관리 포트(8081) 분리, Service 미노출 | 필수 |
| 9 | `server.shutdown: graceful` + `preStop sleep 5` + `terminationGracePeriodSeconds: 45` | 필수 |
| 10 | HikariCP 풀 크기 × replica ≤ PG `max_connections` 여유 | 필수 |
| 11 | HPA 메트릭에 memory 없음 | 필수 |
| 12 | `topologySpreadConstraints` + PDB `maxUnavailable: 1` | 필수 |
| 13 | `runAsNonRoot` + `readOnlyRootFilesystem` (+ heapdump용 `/tmp` emptyDir) | 필수 |
| 14 | 이미지 digest 고정, `latest` 없음 | 필수 |
| 15 | CDS 활성화 이미지 | 권장 |
| 16 | `PriorityClass` 지정 | 권장 |
| 17 | `lazy-initialization` / `TieredStopAtLevel=1` 미사용 | 필수 |

`readOnlyRootFilesystem: true`를 쓰면 heap dump 경로가 쓰기 불가가 되므로 `/tmp`를
`emptyDir`로 마운트해야 한다. 이 조합을 놓치면 OOM 시 dump가 안 남아 원인 분석이 불가능해진다.

---

# 세션 4. 9개월 구축·운영 로드맵 (Phase 1~4)

각 Phase에 **완료 조건(DoD)** 과 **검증 명령**을 붙인다. 검증하지 않은 항목은 완료로 세지 않는다.
크레딧 만료가 확정된 프로젝트에서 “나중에 하겠다”는 사실상 “하지 않는다”이므로, 백업·복구
검증을 Phase 4가 아니라 **Phase 2에 배치**한 것이 원본 계획과의 주요 차이다.

## Phase 0. 착수 전 (D-7 ~ D-0, 크레딧 미소진)

| 순서 | 작업 | 완료 조건 |
| -: | --- | --- |
| 1 | `Nexters/ALIGNER-PLATFORM` **Public** 저장소 생성 | Repository 생성 |
| 2 | `LICENSE`(Apache-2.0) · `SECURITY.md` · `CONTRIBUTING.md` 추가 | 공개 기준선 완료 |
| 3 | Branch Protection · `CODEOWNERS` 구성 (ESO·GitOps 경로 포함) | main 직접 push 차단 |
| 4 | **Git 전체 이력 Secret Scan** + secret scanning · push protection 활성화 | 노출 Secret 없음 |
| 5 | 설계 문서의 **실제 IP·계정·break-glass 대상을 placeholder로 전환** | 공개 가능한 문서 |
| 6 | **Infisical Project 2개 생성** — `aligner-infra` · `aligner-runtime` (§2.6.4) | Project 경계로 권한 분리 |
| 7 | **Infisical 무료 티어 한도 확인** — Identity 5 · Project 3 · RBAC 유무 | 한도 내 확인 또는 Pro 비용 산정 |
| 8 | Infisical 사람 계정 2FA 적용 (운영자 2명) | 2명 완료 |
| 9 | **노출 이력이 있는 인증정보 전부 회전** — 가비아 비밀번호·세션 폐기·이벤트 로그 점검 | 완료 확인 |
| 10 | 가비아 `aligner-terraform` 최소 권한 서브 계정 생성 | 최소 권한 확인 |
| 11 | 가비아 ID/PW를 **`aligner-infra` Project `/prod/gabia`에만** 등록 | 다른 저장소에 복제 없음 |
| 12 | **GitHub OIDC → Infisical** 연동 (`github-platform-deploy` Identity) | 장기 Token 없음 |
| 13 | **ESO 전용 Machine Identity `k3s-production-eso` 생성** | ★ **`aligner-runtime` 만 가입.** `aligner-infra` 미가입 |
| 14 | ESO Bootstrap credential을 **오프클러스터 보관** (§2.6.7) | 패스워드 매니저 + 오프라인 |
| 15 | Terraform **S3 Remote Backend** 구성 (Versioning·SSE·`use_lockfile`) | State Git 미추적 |
| 16 | **Cloudflare R2** `hot/`·`immutable/` + 자격증명 3분할 (§2.5.2) | 버킷·토큰 |
| 17 | AWS S3 2차 사본 버킷 (Object Lock) | 버킷·키 |
| 18 | Grafana Cloud 계정·토큰 → `aligner-runtime` Project `/prod/observability` | 토큰 등록 |
| 19 | **`k3s_token` 사전 생성 → `aligner-infra` Project `/prod/k3s`** | 백업이 구조적으로 보장된다 |
| 20 | **gCloud API endpoint matrix 작성** — SG·Volume·Public IP·LB 경로·스키마 | matrix 문서 |
| 21 | **`gabiactl` 세션 인증 구현** (2시간 세션 재발급·mutex·401 재시도) | 인증 동작 확인 |
| 22 | **ADR 작성 — 가비아 계정 2FA 미사용** (§2.8.6 보완 통제 포함) | ADR |
| 23 | Tailscale Community on GitHub 신청 + WireGuard Role 준비 | 신청 접수 · Role 작성 |
| 24 | 개인 Private `terraform-provider-gabiacloud` 저장소 생성 | 저장소 |
| 25 | 요금 계산기 견적 재확인 · 도메인·DNS 준비 | 견적 · DNS 존 |
| 26 | §1.6 문의 접수 — A1·A2 / C1·C5·C6·C7 / D1·D5·D7 / F1·F3 | 답변 기록 |

**저장소를 분리하는 이유** — 공개 여부가 아니라 **변경 책임과 생명주기가 다르기 때문**이다.

- `ALIGNER-SERVER`는 애플리케이션 소스와 CI를 소유한다.
- `ALIGNER-PLATFORM`은 클라우드 인프라·노드 구성·Kubernetes·GitOps 배포 정본을 소유한다.
- `terraform-provider-gabiacloud`는 Aligner에 종속되지 않는 **재사용 가능한 Provider**이며
  개인 저장소에서 별도로 개발한다.

앱 CI는 이미지를 GHCR에 push한 뒤 **`ALIGNER-PLATFORM`에 image digest 변경 PR**을 생성한다.
앱 저장소에 배포 digest를 다시 커밋하지 않으므로 **CI 재귀 트리거를 방지**하고,
**애플리케이션 빌드와 프로덕션 배포 승인을 분리**할 수 있다.

### Phase 0 Gate — Phase 1 진입 조건

```text
[공개 준비]
□ ALIGNER-PLATFORM 공개 전 Git 전체 이력 secret scan 통과
□ tfstate·tfplan·실제 tfvars·.runtime/·kubeconfig 미추적 확인
□ Public 문서의 실제 IP·계정·운영자 개인정보 제거 완료
□ GitHub secret scanning · push protection · branch protection · CODEOWNERS 활성화
□ Third-party Action 을 commit SHA 로 고정

[시크릿]
□ Infisical Project 2개에 모든 시크릿 등록 (정본이 한 곳)
□ 사람 계정 2FA 적용
□ GitHub Actions 가 OIDC 로 인증 — 장기 Token 0개
□ ★ ESO Machine Identity 가 aligner-infra Project 에 **미가입**임을 확인 (구조적 차단)
□ Bootstrap credential 오프클러스터 보관 완료
□ 노출 이력이 있는 기존 인증정보 회전 완료

[기술]
□ SG·Volume·Public IP·LB 의 API 경로와 스키마 확정 (endpoint matrix)
□ gabiactl 로 Network·Subnet 생성·삭제 성공 + 2시간 세션 재발급 동작
□ Terraform State 버킷과 IAM 최소 권한 구성

[정책]
□ 가비아 API 자동화 공식 허용 여부 서면 답변 (미지원이면 ADR 에 리스크 기록)
□ Tailscale Community 승인 여부 → freeze 시점 관리망 결정
□ Apache-2.0 배포 권한 내부 승인 (두 Public 저장소 모두)
□ 가비아 2FA 미사용 ADR 작성 + 보완 통제 6항목 적용 확인
```

> **문의 D1·D2 답변은 더 이상 "자동화를 할 수 있느냐"의 조건이 아니다.** 실측으로 가능함이
> 확인됐다. 답변이 결정하는 것은 **"공식 지원을 받을 수 있느냐"** 이고, 그것은 운영 리스크
> 등급과 **Provider 공개 시점**을 정하는 정보다.

---

## Phase 1. 인프라 · 클러스터 · 보안 기준선 (1~2개월차)

크레딧 소진 시작. 목표는 **"의도적으로 노드를 죽여도 서비스가 유지되는 클러스터"** 다.

### 1개월차

| # | 작업 | 세부 |
| --- | --- | --- |
| 1 | **L1 프로비저닝 — `gabiactl` + Ansible** (§2.8.5) | `desired-infrastructure.yaml` 기반 멱등 생성. Provider 완성을 기다리지 않는다 |
| 2 | 생성 결과를 `inventory.yaml`에 저장 → Ansible이 소비 | 리소스 ID·사설 IP·공인 IP |
| 3 | `gabiactl check`로 desired/current 대조 | drift 탐지 80%. 특히 **보안그룹 규칙** |
| 4 | **관리망 배포 — freeze 결정에 따라 하나만** (§1.5.1) | Tailscale 승인 → subnet router 2대(k3s-01·02). 미승인 → WireGuard 게이트웨이 2대 + MASQUERADE |
| 5 | **관리망으로 세 노드 사설 IP 접속 성공 확인** | ★ 다음 단계의 전제 |
| 6 | **break-glass 경로 1회 실사용 검증** | 가비아 VNC 콘솔(문의 C5) 또는 `rescue-Ubuntu-22.04` 이미지 부팅 |
| 7 | **보안그룹 잠금 — 22·6443 공인망 차단** | ★ **4·5·6이 전부 통과한 뒤에만.** 순서를 틀리면 세 노드 동시 잠금 |
| 8 | **cloud-init 최소 Bootstrap** (가비아 사용자 스크립트) | 디스크 준비·기본 패키지·Ansible 접근 계정과 공개키·최소 방화벽. **시크릿 금지**(§2.8.6) |
| 9 | **L2 Ansible** — `/mnt/k3s`(Data-A) `/mnt/aligner`(Data-B) 마운트, `mount-guard.conf`, `priority.conf`, 커널 파라미터, 시간 동기화, swap 비활성화, 고유 hostname | OS는 **Ubuntu 24.04 LTS 로 동결** (커널 6.8 — Cilium 요구 5.10+ 충족, §2.3) |
| 10 | **k3s-01만 `cluster-init: true`로 설치** | `flannel-backend: none`, `disable-network-policy: true`, `traefik`·`servicelb` disable, `secrets-encryption: true`, `data-dir: /mnt/k3s`, **`kubelet-arg` 3종**(§2.1), `etcd-snapshot-*`, `etcd-s3`. `INSTALL_K3S_VERSION` 고정 |
| 11 | kube-apiserver 응답 확인 | `kubectl get --raw='/readyz?verbose'`. 노드는 `NotReady`가 정상 |
| 12 | **Cilium 설치 — Ansible이 컨트롤 노드에서 helm 실행** (§2.3) | `delegate_to: localhost` + `kubernetes.core.helm`. **auto-deploy 매니페스트를 쓰지 않는다**(helm-controller Job이 CNI 없이 Pending) |
| 13 | k3s-01 `Ready` 확인 → CoreDNS 기동 | |
| 14 | **k3s-02·03을 server로 조인** | 동일 `config.yaml` + `server: https://{{ k3s_node_ips[0] }}:6443` + 동일 token. `node-name`·`node-ip`·`advertise-address`만 다름 |
| 15 | etcd 멤버 3개 복귀 확인 | `journalctl -u k3s \| grep -i "etcd.*member"` |
| 16 | `cilium status --wait` / `cilium connectivity test` 전체 통과 | 실패 시 **Flannel로 클러스터 재생성** (§2.3 Gate) |
| 17 | **자원 Gate 실측** — cilium-agent RSS·CPU → **1노드 장애 시 필수 request ≤ 2노드 allocatable 85%** 판정 | ★ 현재 추정 **82.6%로 충족**하나 초기값 기반이다. 실측 초과 시 PG·API request 하향 또는 Flannel 재생성 |
| 18 | **LB 리스너 2개만 구성** (443→30443, 80→30080) | **6443 리스너는 만들지 않는다.** kubectl은 관리망 경유 사설 IP |
| 19 | Traefik Helm 배포 (3 replica, `externalTrafficPolicy: Local`, PDB, Gateway API 활성) | 아직 수동 — 2개월차에 Argo CD가 인수 |
| 20 | cert-manager + Let's Encrypt ClusterIssuer, 첫 인증서 발급 | staging → production 순서 |
| 21 | etcd snapshot **R2 `hot/etcd/`** 업로드 확인 + **server token 오프클러스터 백업** | token은 **Phase 0에서 미리 생성해 패스워드 매니저에 저장**하면 백업이 구조적으로 보장된다 |

**병행 트랙(일정 독립)** — `terraform-provider-gabiacloud` M1(Subnet) 착수. Phase 1을 막지 않는다.

### 2개월차

| # | 작업 | 세부 |
| --- | --- | --- |
| 9 | Pod Security Admission `restricted` 적용 | 애플리케이션 namespace |
| 10 | **NetworkPolicy default-deny + 명시적 허용** (§2.3) | 원본 대비 앞당긴 항목 |
| 11 | ESO 설치 + **Infisical Machine Identity Bootstrap 주입** | Phase 4 이관의 전제 |
| 12 | Argo CD 설치, app-of-apps 구성, Traefik·cert-manager를 GitOps로 인수 | 수동 리소스를 Git으로 이관 |
| 13 | Argo CD 접근 통제: `admin` 비활성화 + GitHub OAuth + RBAC 또는 Tailscale 전용 | 인증 없는 노출 금지 |
| 14 | **장애 훈련 #1 — 노드 1대 강제 정지** | etcd quorum·API·Traefik·Endpoint 반응 관측 |
| 15 | **복구 훈련 #1 — etcd snapshot 복구** | 3노드 재조립 절차 문서화 |

### DoD 및 검증

```bash
# 1. 3노드 Ready, 대칭 확인
kubectl get nodes -o wide
kubectl get nodes -o json | jq '.items[].status.allocatable'

# 2. etcd 멤버 3개, 모두 정상
sudo k3s etcd-snapshot ls
kubectl -n kube-system get pods            # etcd는 프로세스이므로 K3s 로그로 확인
sudo journalctl -u k3s | grep -i "etcd.*member"

# 3. 노드 1대 정지 후에도 API·서비스 응답 (훈련 #1)
#    별도 노드에서 실행
while true; do curl -s -o /dev/null -w "%{http_code} " https://aligner.example.com/health; sleep 1; done
# → 정지 직후 일부 실패 후 회복되어야 한다. 지속 실패면 설계 문제.

# 4. NetworkPolicy 동작 — 차단과 허용을 둘 다 검증해야 한다
#    초판의 `wget http://...:5432` 는 PostgreSQL 포트에 HTTP 를 보내므로
#    실패 원인이 정책인지 프로토콜 불일치인지 구분되지 않았다.

# 4-a) 차단 테스트 — 허용 label 이 없는 Pod 에서 (실패해야 한다)
kubectl run netpol-deny --rm -it --restart=Never --image=nicolaka/netshoot -- \
  nc -vz -w 3 aligner-db-rw.database.svc.cluster.local 5432
#   기대: "Connection timed out" 또는 무응답 → BLOCKED

# 4-b) 허용 테스트 — aligner-api 와 동일한 label 을 가진 Pod 에서 (성공해야 한다)
kubectl run netpol-allow --rm -it --restart=Never \
  --labels="app=aligner-api" --image=postgres:17-alpine -- \
  pg_isready -h aligner-db-rw.database.svc.cluster.local -p 5432
#   기대: "accepting connections" → ALLOWED

# 4-c) egress 차단 테스트 — 허용되지 않은 포트 (실패해야 한다)
kubectl run egress-deny --rm -it --restart=Never --labels="app=aligner-api" \
  --image=nicolaka/netshoot -- nc -vz -w 3 example.com 22

# 4-d) Cilium 채택 시 정책 거부를 메트릭으로 확인
kubectl -n kube-system exec ds/cilium -- \
  cilium-dbg metrics list | grep -i policy_denied

# 5. TLS 인증서 발급
kubectl get certificate -A
echo | openssl s_client -connect aligner.example.com:443 2>/dev/null | openssl x509 -noout -dates

# 6. Argo CD 동기화 상태
argocd app list                            # 전부 Synced / Healthy
```

| DoD | 기준 |
| --- | --- |
| 노드 3대 Ready. **`kubectl describe node` 실측 allocatable로 §3.5 표 교체** (CPU 1600m / 메모리 약 6.2Gi 예상) | 필수 |
| **`cilium connectivity test` 전체 통과** + §2.3 도입 Gate 전 항목 | 필수 |
| **cilium-agent RSS·CPU 실측으로 §3.5의 300Mi 초기값 교체.** 1노드 장애 시 필수 request ≤ 2노드 allocatable 85% | 필수 |
| Data-A / Data-B 마운트 확인. `ConditionPathIsMountPoint` 동작 검증(의도적 마운트 해제 후 기동 실패 확인) | 필수 |
| 노드 1대 정지 시 API 5분 내 정상, etcd quorum 유지 | 필수 |
| **degraded overlay가 GitOps 저장소에 존재하고 1회 sync 테스트 완료** | 필수 |
| etcd snapshot이 **R2**에 6시간 주기로 적재 | 필수 |
| **K3s server token이 오프클러스터에 백업됨** | 필수 |
| **`secrets-encryption: true` 활성 확인** (`k3s secrets-encrypt status`) | 필수 |
| snapshot + token으로 클러스터 복구를 **1회 실제 수행**하고 소요 시간 기록 | 필수 |
| **R2 Bucket Lock 적용 + backup-writer 자격증명이 DeleteObject 불가함을 실제 확인** | 필수 |
| default-deny NetworkPolicy(표준) 하에 애플리케이션 통신 정상 | 필수 |
| **관리망 하나만 배포됨.** 22·6443이 공인망에서 닫힘. 관리자 2명이 세 노드 사설 IP 접근 가능 | 필수 |
| **break-glass 경로 1회 실제 사용 확인** (VNC 콘솔 또는 rescue 이미지 부팅) | 필수 |
| **`gabiactl check`가 desired/current 일치를 보고** | 필수 |
| **LB 리스너가 443·80 두 개만 존재** | 필수 |
| Argo CD가 platform 전체를 관리, 수동 리소스 0 (**Cilium은 예외 — L2 소유**) | 필수 |
| **cloud-init에 시크릿이 없음을 확인** (user_data는 state·메타데이터에 남는다) | 필수 |
| cgroup v2·k3s.service cgroup 위치 확인, stress-ng 부하 중 etcd fsync p99 측정 | 권장 |

---

## Phase 2. 애플리케이션 · 데이터베이스 · 관측성 (3~4개월차)

목표는 **“Aligner API가 관측·백업되는 상태로 실제 운영되는 것”** 이다.

### 3개월차

| # | 작업 | 세부 |
| --- | --- | --- |
| 1 | CI 파이프라인 완성 (GitHub Actions) | `build` → `ktlintCheck` → `integrationTest`(TestContainers) → 이미지(CDS) → Trivy → GHCR → GitOps digest 커밋 |
| 2 | CloudNativePG operator 설치, `aligner-db` Cluster 2 instance 배포 | anti-affinity로 다른 노드 강제 |
| 3 | Liquibase changelog 적용 경로 확정 | 도메인별 changelog, 애플리케이션 시작 시 또는 Job |
| 4 | Barman Cloud Plugin → **Cloudflare R2** `hot/cnpg/` WAL 아카이빙 + 주간 basebackup | **§2.5.4의 R2 acceptance test를 먼저 통과해야 한다.** "endpoint만 바꾸면 동작"으로 가정하지 않는다 |
| 5 | Aligner API 배포 (§3 전체 설정 적용) | 3 replica, probe 3종, graceful shutdown, PDB, topologySpread |
| 6 | Redis 배포 (캐시 용도, 유실 허용) | **emptyDir — PVC 없음.** 노드 장애 시 자유롭게 재스케줄된다(§3.5) |
| 7 | Grafana Alloy 배포, Grafana Cloud 연결 | metrics + logs + traces |
| 8 | 카디널리티 제어 relabel 규칙 적용 (§2.7) | Free tier 한도 내 유지 확인 |

### 4개월차

| # | 작업 | 세부 |
| --- | --- | --- |
| 9 | 대시보드 구축 | JVM heap·GC, **CFS throttle**, HTTP p95/p99, HikariCP, PG 복제 지연, 노드 자원 |
| 10 | 알림 규칙 (Grafana Cloud → Slack/Discord) | 아래 표 |
| 11 | 외부 프로빙(Synthetic) 설정 | 클러스터 전체 다운을 외부에서 감지 |
| 12 | **복구 훈련 #2 — PostgreSQL PITR** | 임의 시점 복구, 소요 시간 기록 |
| 13 | **훈련 #3a — CNPG primary Pod 삭제** (pod failover) | switchover 시간, 앱 재연결 확인 |
| 13b | **훈련 #3b — primary 노드 VM 강제 정지** (node-loss recovery) | **아래 별도 절차. Pod 삭제와 전혀 다른 시험이다** |
| 13c | **훈련 #3c — 아카이빙 강제 중단** | R2 자격증명 무효화 → `failed_count` 증가·경보 발화·pg_wal 증가 속도 실측 |
| 14 | 자원 실측 기반 requests/limits 1차 조정 | 추측값 → 실측값. **Cilium agent RSS 포함**(§2.3 Gate) |
| 15 | HPA 적용 및 동작 확인 | CPU 70%, min 2 / max 4 |

### ⚠️ 훈련 #3b — Pod 삭제와 노드 영구 유실은 다른 시험이다

초판 Phase 2는 "primary 파드 삭제"만 있었다. **그것은 pod failover 시험이고, local-path PVC가
다른 노드로 옮겨지지 않는 상황을 검증하지 않는다.** §2.5.3에서 기대한 순서가 실제로 그렇게
동작하는지 반드시 확인해야 한다.

```text
1. primary 가 올라간 VM 을 가비아 콘솔에서 강제 정지 (graceful shutdown 아님)
2. standby 승격 시간 측정 (앱의 쓰기 실패 지속 시간)
3. 기존 노드의 local PVC 가 어떤 상태로 남는지 확인 (Bound / Pending / Released)
   → local-path PV 는 node affinity 가 걸려 있어 다른 노드로 attach 되지 않는다
4. **세 번째 노드에 새 standby 가 자동 생성되는지** 확인
   → CNPG 가 pg_basebackup 으로 동기화를 시작해야 한다
5. 자동 생성되지 않으면 필요한 정리 절차를 문서화
   (Cluster 의 instances 조정, 고아 PVC·PV 삭제, node affinity 해제 등)
6. redundancy 2 인스턴스 복귀까지 걸린 시간 측정  ← §2.5.3 의 "수 분~수십 분" 가설 검증
7. 그 동안 애플리케이션 쓰기·읽기 동작 검증 (degraded overlay 적용 상태)
8. 정지한 노드를 복구해 재합류시킨 뒤 고아 PVC 정리
```

**정량 성공 기준 — 사전에 정해 두고 측정한다.**

```text
□ Write RTO 목표      standby 승격까지 쓰기 실패 지속 시간 ≤ 60초
□ 허용 RPO            비동기 복제이므로 0 이 아니다. 실측 후 명시 (§2.5.3)
                      CNPG 공식 문서도 비동기 failover 에서 최신 replica 에 반영되지 않은
                      commit 이 유실될 수 있다고 경고한다
□ 새 standby 생성 시간  pg_basebackup 완료까지 측정
□ redundancy 2 복귀    ≤ 30분 (합의 시 조정)
□ 고아 local PV 정리    수동 절차인지 자동인지 확인 후 runbook 화
□ 기준 초과 시         instances: 3 검토 (§2.5.3 — 인스턴스당 1.33Gi 로 동작하면 총량 유지 가능)
```

**측정 결과를 §2.5.3에 실측치로 반영한다.** "수 분~수십 분"은 현재 추정이며 데이터가 없다.

**알림 규칙 (최소 세트)**

| 알림 | 조건 | 심각도 |
| --- | --- | --- |
| 서비스 다운 | 외부 프로빙 실패 2회 연속 | Critical |
| 노드 NotReady | 3분 이상 | Critical |
| etcd 멤버 이탈 | 1분 이상 | Critical |
| PG 복제 지연 | `pg_replication_lag > 60s` | Warning |
| PG 백업 실패 | WAL 아카이빙 실패 또는 basebackup 미수행 24h | Critical |
| 파드 CrashLoopBackOff | 5분 이상 | Warning |
| OOMKilled 발생 | 즉시 | Warning |
| CPU 스로틀 비율 | 5분 평균 > 5% | Warning |
| 메모리 requests 총합 | allocatable(1노드 장애 기준) 초과 | Warning |
| 인증서 만료 임박 | 14일 이내 | Warning |
| 디스크 사용률 | Data SSD > 75% | Warning |

### DoD 및 검증

```bash
# 1. PG HA 상태 — primary/standby가 다른 노드에 있는지
kubectl -n database get pods -o wide -l cnpg.io/cluster=aligner-db
kubectl -n database get cluster aligner-db -o jsonpath='{.status.instancesStatus}' | jq

# 2. 백업·WAL 아카이빙 동작
kubectl -n database get cluster aligner-db \
  -o jsonpath='{.status.lastSuccessfulBackup}{"\n"}{.status.firstRecoverabilityPoint}{"\n"}'
aws s3 ls s3://aligner-backup/aligner-db/wals/ --recursive | tail -5

# 3. PITR 복구 검증 (훈련 #2) — 별도 Cluster로 복구, 운영 DB 건드리지 않음
#    recovery target time 지정 후 데이터 시점 일치 확인

# 4. failover (훈련 #3)
kubectl -n database delete pod aligner-db-1        # primary 삭제
kubectl -n database get cluster aligner-db -w      # targetPrimary 전환 관측
# 앱 로그에서 HikariCP 재연결 확인. 무중단이 아니라 '빠른 회복'이 목표.

# 5. Graceful shutdown 검증 — 롤링 업데이트 중 5xx 0건
kubectl rollout restart deployment/aligner-api -n aligner
# 동시에 부하 생성:
hey -z 90s -c 20 https://aligner.example.com/api/body-parts
# → non-2xx 응답이 0이어야 한다. 있으면 preStop·terminationGracePeriod 재조정.

# 6. 자원 실측
kubectl top pods -A --sort-by=memory
kubectl top nodes
```

| DoD | 기준 |
| --- | --- |
| Aligner API 3 replica 정상, p95 목표 이내 | 필수 |
| **롤링 업데이트 중 5xx 0건** | 필수 |
| PG primary/standby가 서로 다른 노드, 복제 지연 < 5s | 필수 |
| WAL 아카이빙 연속 동작, 주간 basebackup 성공 | 필수 |
| **PITR 복구를 실제 수행하고 RTO 실측치 기록** | 필수 |
| primary 삭제 시 자동 failover, 앱 자동 재연결 | 필수 |
| Grafana Cloud에 metrics·logs·traces 모두 수집, 무료 한도 내 | 필수 |
| 알림 11종 설정 및 각 1회 실발화 테스트 | 필수 |
| requests/limits가 실측 기반으로 갱신됨 | 필수 |

---

## Phase 3. 성능 · 부하 · 축소 운전 검증 (5~6개월차)

목표는 **“한계와 축소 운전 동작을 숫자로 아는 것”** 이다. Phase 1~2는 “동작한다”를,
Phase 3은 “어디까지 동작하고 넘어가면 어떻게 되는가”를 확인한다.

| # | 작업 | 세부 |
| --- | --- | --- |
| 1 | 부하 테스트 (k6 또는 Gatling) — **클러스터 외부에서 생성** | 클러스터 안에서 부하를 만들면 자원을 경합해 결과가 오염된다 |
| 2 | 시나리오: 핵심 루프 (`BodyPart` → `Screening` → `Cause` → `Course` → `Session`) | 실제 사용 경로. 단일 엔드포인트 테스트는 의미가 적다 |
| 3 | JVM 워밍업 곡선 측정 | 시작 후 몇 초에 p99가 안정되는가 → HPA `scaleUp` 튜닝 근거 |
| 4 | CDS·AOT 캐시 적용 전후 시작 시간 A/B 측정 | 실측으로 채택 여부 결정 (§3.2) |
| 5 | HPA 임계 조정 | 부하 곡선 기반 |
| 6 | 커넥션 풀 포화 지점 확인 | `hikaricp_connections_pending` 관측 |
| 7 | **축소 운전 훈련 — PriorityClass 축출 순서 검증** (§3.5) | 노드 1대 정지 후 무엇이 먼저 죽는지 실제 확인 |
| 8 | **장애 훈련 #4 — 노드 2대 동시 정지** | etcd quorum 상실 상태 관측. 복구 절차 확인 |
| 9 | **장애 훈련 #5 — 노드 1대 완전 재설치** | L1 삭제·재생성 + Ansible 재설정 후 클러스터 재합류 |
| 10 | 로그·메트릭 보관 정책 점검 | Grafana Cloud 한도 소진 속도 확인 |
| 11 | **K3s 마이너 업그레이드 리허설** | 노드 순차 업그레이드, PDB 동작 확인. **1대씩** 진행하고 etcd 멤버 3개 복귀 확인 후 다음 노드(§1.2.2) |
| 12 | **degraded overlay 실전 검증** | 노드 1대 정지 → degraded sync → 자원 수용 확인 → 복구 → normal 복귀. 전환 소요 시간 실측(§3.5.2) |
| 13 | **maintenance overlay 검증** | 계획 작업 시 배포 차단 + 축소가 동작하는지 |
| 14 | Data 볼륨 사용률·inode 점검 및 필요 시 증설 | 10GB 단위. Data-A(etcd)와 Data-B 각각 |
| 15 | 런북(runbook) 작성 | 알림별 대응 절차. 새벽에 당황하지 않기 위한 문서 |

**훈련 #4(노드 2대 정지)를 반드시 하는 이유** — 이 클러스터의 HA 경계가 “1노드 장애”라는 것을
문서로 아는 것과 실제로 겪는 것은 다르다. quorum을 잃으면 API가 read-only도 아니라 응답 자체를
멈춘다. 이 상태에서 `--cluster-reset`으로 단일 노드 복구 후 나머지를 재합류시키는 절차는
연습 없이 실전에서 하면 반드시 실수한다.

```bash
# 훈련 #4 복구 절차 (사전 연습 필수)
# ★ 전제: /var/lib/rancher/k3s/server/token 을 오프클러스터에서 먼저 복원한다 (§2.5.2)
#         token 이 다르면 스냅샷을 복호화할 수 없어 복구가 실패한다.

# [살아있는 노드 1대]
sudo systemctl stop k3s
sudo install -m600 /path/to/restored/token /mnt/k3s/server/token   # 또는 --token 으로 전달
sudo k3s server --cluster-reset \
  --cluster-reset-restore-path=/mnt/k3s/server/db/snapshots/<snapshot>
# 위 명령이 "Managed etcd cluster membership has been reset" 를 출력하고 종료되면
sudo systemctl start k3s
kubectl get nodes                      # 단일 server 로 API 복귀 확인

# [나머지 2대]
sudo systemctl stop k3s
sudo rm -rf /mnt/k3s/server/db          # data-dir 의 etcd DB 만 제거
sudo systemctl start k3s                # 동일 token 으로 재조인
# 세 노드 모두에서 etcd 멤버가 3개로 복귀했는지 확인
sudo journalctl -u k3s | grep -i "etcd.*member"
```

> ⚠️ **경로는 `data-dir` 설정과 반드시 일치해야 한다.** §2.1에서 `data-dir: /mnt/k3s`로
> 지정했으므로 스냅샷 경로는 `/mnt/k3s/server/db/snapshots/`다. 기본 경로
> (`/var/lib/rancher/k3s/...`)를 쓰면 스냅샷을 찾지 못한다. **Runbook의 경로 오타는 실전에서
> 치명적이므로 Phase 1 복구 훈련에서 이 명령을 그대로 복사해 검증한다.**

### DoD

| DoD | 기준 |
| --- | --- |
| 목표 처리량에서 p95·p99 지연 실측치 확보 | 필수 |
| 자원 한계(최초 병목 지점)와 그때의 증상 기록 | 필수 |
| PriorityClass 축출 순서가 설계대로 동작함을 확인 | 필수 |
| 노드 2대 정지 → 복구 절차 실제 수행 및 RTO 기록 | 필수 |
| 노드 1대 재설치 → IaC로 재합류 성공 | 필수 |
| K3s 업그레이드 무중단 수행 (5xx 0건) | 필수 |
| **degraded overlay 전환 실전 검증 및 소요 시간 기록** | 필수 |
| 알림별 런북 문서 완성 | 필수 |
| CDS·AOT 적용 여부를 실측 근거로 결정 | 권장 |
| JVM hard cap(Metaspace·Xss) 실측 후 설정 | 권장 |

---

## Phase 4. DR · 이관 리허설 · 종료 계획 (7~9개월차)

목표는 **"크레딧이 끝나도 이 서비스를 다른 곳에서 다시 세울 수 있음을 증명하는 것"** 이다.

> ⚠️ **명칭 정정** — 초판은 이 단계를 "DR"이라고 불렀다. 정확하지 않다. **"DR"은 가비아 전체
> 장애나 계정 장애에서 복구 가능함을 검증했을 때 쓰는 말**이고, 같은 클라우드 안에서 클러스터를
> 다시 세우는 것은 **재구축·데이터 복원 리허설(rebuild drill)** 이다. 이 설계에서 진짜 DR을
> 뒷받침하는 것은 **외부 백업(R2·S3)뿐**이다.
>
> 2노드 리허설이 **검증하는 것** — L1 재현성, K3s token 복원, Argo CD 부트스트랩,
> Infisical Machine Identity 복원, PostgreSQL PITR, 데이터 정합성.
>
> **검증하지 못하는 것** — etcd quorum 복구, 3노드 장애 내구성, 실제 External LB 경로,
> TLS 자동화 전체, local-path 노드 교체, 한 노드 장애 중 CNPG standby 재생성.
> 앞의 넷은 Phase 1~3의 훈련 #1·#4·#5에서, 나머지는 9개월차 3노드 검증에서 다룬다.

### 7~8개월차 — 재구축·데이터 복원 리허설 (신규 2노드 클러스터)

신규 클러스터는 **2노드(`2/8` × 2, Data 40GB × 2, 공인 IP 2, LB 없음), 1개월, 182,270원**으로
띄운다(§1.3). 정확히 1개월 단위로 생성·삭제한다 — 부분 월은 시간제로 계산되어 월 정액보다
비쌀 수 있다(§1.6 #10).

| # | 작업 |
| --- | --- |
| 1 | **L1 인프라 재생성 + Ansible로 노드 부트스트랩** (§2.8.7 확정 경로, 기존 클러스터 무중단 유지) |
| 2 | **K3s server token 복원 후** etcd snapshot restore — token 없이 시도해 실패를 재현하는 것도 1회 수행 |
| 3 | **Infisical Machine Identity 주입 → ESO 가 모든 Secret 을 재동기화하는지 확인** (분실 시에도 재발급 가능) |
| 4 | `secrets-encryption` 키 복원 → Secret 복호화 확인 (§2.6) |
| 5 | Argo CD 부트스트랩 → app-of-apps 동기화만으로 전체 플랫폼 재구성 |
| 6 | **R2** basebackup + WAL로 PostgreSQL 복구 (CNPG `bootstrap.recovery`) — **restore 자격증명은 오프클러스터에서 가져온다** |
| 7 | 데이터 정합성 검증 (행 수, 최신 `Session` 시각, 체크섬) |
| 8 | NodePort로 애플리케이션 응답 확인 (도메인·TLS는 검증 대상 아님) |
| 9 | **전체 복구 RTO·RPO 실측** 및 목표(§2.5.2 표)와 비교 |
| 10 | 리허설 종료 후 즉시 삭제 (또는 문의 C3 확정 시 '종료' 상태로 전환) |

**이 리허설이 모든 앞선 설계의 검증**이다. K3s token·Infisical Machine Identity·secrets-encryption 키·
오프클러스터 restore 자격증명·L1 정의·GitOps·외부 백업 중 **하나라도 빠져 있으면 여기서
실패한다.** 실패는 성과다 — 크레딧이 살아 있는 동안 발견한 것이므로.

**2번의 "token 없이 실패 재현"을 의도적으로 넣었다.** 팀이 그 실패 화면을 한 번 봐야
`/var/lib/rancher/k3s/server/token`의 중요성이 절차가 아니라 경험으로 남는다.

### 8개월차 — 잔여 검증과 최적화

| # | 작업 |
| --- | --- |
| 11 | 신규 2노드 클러스터에서 **Cilium 고급 기능 실험** — `kubeProxyReplacement: true`, Hubble Relay/UI, `CiliumNetworkPolicy` L7·FQDN, WireGuard 투명 암호화. **운영 클러스터에는 적용하지 않는다** |
| 12 | **Longhorn** replica 2로 비핵심 데이터 검증 — 2 vCPU에서의 실제 CPU 부하 측정 |
| 13 | 두 실험 결과를 **"다음 클러스터에서 채택/미채택" 결정으로 기록** |
| 14 | K3s 메이저 업그레이드 리허설 (신규 클러스터에서 먼저) |
| 15 | 비용 실적 정산 — 예측 대비 실제 청구액, 크레딧 잔액, R2·S3 현금 비용 |
| 16 | **문의 C1(커스텀 이미지)이 "가능"이었다면 Talos Linux PoC** — §2.1의 유보 항목 |
| 17 | **문의 F1(물리 분산)·F3(존 분리) 답변으로 HA 명칭 확정** — §1.2의 단서 해소 |

### 9개월차 — 3노드 전체 복구 검증 · 종료 · 이관 결정

2노드 리허설이 검증하지 못한 것을 여기서 **최소 1회** 다룬다. 기존 클러스터를 대상으로 하되
서비스 영향을 최소화할 시간대에, maintenance overlay를 적용한 상태로 수행한다.

| # | 3노드 전체 복구 검증 (훈련 #8) |
| --- | --- |
| 1 | 기존 클러스터의 최신 etcd snapshot + K3s token 확보 확인 |
| 2 | 노드 3대를 순차 초기화 (또는 신규 3노드 생성) |
| 3 | **K3s token 복원 → `--cluster-reset-restore-path`로 첫 server 복구** |
| 4 | **나머지 2개 server 멤버 재가입 → etcd 멤버 3개 복귀 확인** |
| 5 | Argo CD reconcile → 플랫폼·앱 전체 재구성 |
| 6 | R2에서 PostgreSQL 복구 + 데이터 정합성 검증 |
| 7 | **External LB 대상 서버 재등록 + DNS 전환 + TLS 자동 발급 확인** |
| 8 | **RTO / RPO 실측** 및 §2.5.2 목표 대비 평가 |

| # | 종료·이관 작업 |
| --- | --- |
| 9 | 최종 백업: PG 논리 덤프(`pg_dump`) + basebackup + etcd snapshot + token → **R2 + AWS S3 2중 사본 (Object Lock)** |
| 10 | 컨테이너 이미지 GHCR 보존 확인 (digest 목록 기록) |
| 11 | 이관 시나리오 결정: (a) 유료 전환 지속 (b) 타 클라우드 이전 (c) 종료 후 데이터 보관 |
| 12 | 이관 시 예상 비용 산정 (동일 사양 기준 타 CSP 비교) |
| 13 | **9개월 회고 문서** 작성 |
| 14 | 크레딧 잔액 확인 및 리소스 삭제 순서 계획 (LB → VM → 볼륨 → IP) |
| 15 | 삭제 전 최종 스냅샷 및 외부 사본 무결성 검증 (실제 복원 1회) |

**회고 문서에 반드시 담을 것**

- 훈련별 실측 RTO/RPO와 목표치 차이
- 자원 실측치와 초기 산정치의 차이 (다음 설계의 근거)
- 이 설계에서 틀렸던 판단 (예: `2/8`이 CPU 병목이었는가, PG 2 instance가 과했는가)
- Cilium·Longhorn 검증 결과와 채택 판단
- 다시 한다면 바꿀 것

### DoD

| DoD | 기준 |
| --- | --- |
| **신규 클러스터에서 전체 복구 성공** (L1 재생성 → Ansible → Argo CD → PG 복구 → 데이터 검증) | 필수 |
| 전체 복구 RTO 실측 및 목표 대비 평가 | 필수 |
| Infisical Machine Identity 복원만으로 전체 시크릿 동작 확인 | 필수 |
| 최종 백업 3중 사본 및 복원 가능성 검증 | 필수 |
| 이관/종료 결정과 비용 산정 완료 | 필수 |
| 회고 문서 작성 | 필수 |
| Cilium·Longhorn 검증 결과 문서화 | 권장 |

---

## 훈련 일정 요약

| 훈련 | 내용 | 시점 |
| --- | --- | --- |
| #1 | 노드 1대 강제 정지 | 2개월차 |
| 복구 #1 | etcd snapshot 복구 | 2개월차 |
| 복구 #2 | PostgreSQL PITR | 4개월차 |
| #3 | CNPG primary failover | 4개월차 |
| #4 | 노드 2대 정지 (quorum 상실) + `--cluster-reset` 복구 | 6개월차 |
| #5 | 노드 1대 완전 재설치 후 재합류 | 6개월차 |
| #6 | K3s 무중단 업그레이드 | 6개월차 |
| **#6b** | **degraded / maintenance overlay 전환 검증** | 6개월차 |
| #7 | **재구축·데이터 복원 리허설 (신규 2노드)** | 7~8개월차 |
| **#7b** | **K3s token 없이 복구 실패 재현** (경험 학습) | 7~8개월차 |
| **#8** | **3노드 전체 복구 검증** (token → etcd restore → 멤버 재가입 → LB·DNS 전환 → RTO 측정) | 9개월차 |
| 정례 | 월 1회 백업 복구 검증 | 2개월차부터 매월 |

---

# 최종 구성 요약 — v7 Final (동결)

> **이 버전을 실행 정본으로 동결한다.** 이후 변경은 **Phase 1~4의 실측 결과와 가비아 서면
> 답변으로만** 한다. 설계를 다시 뒤집지 않는다. 남은 미확정 항목은 §Go/No-Go에 명시했다.
>
> v7은 **새로운 설계 결정이 없다.** 문서 내부 모순 9건을 제거하고 Infisical 권한 경계를
> Project 분리로 구조화하고 Gate 3건을 실증 기준으로 강화했다(§7판 수정).
> **설계 재논의는 종료한다. 이후 변경은 Phase 1~4의 실측 결과와 가비아 서면 답변으로만 한다.**

```text
[ 인프라 ]
Cloud            : 가비아 클라우드 Gen2 (VPC)
Cluster          : 3-node Converged (Control Plane + etcd + Worker 대칭)
                   ※ 단일 리전·단일 장애 도메인 가능성 — 문의 F 그룹으로 확정 (§1.2)
Node             : standard 2 vCPU / 8GB × 3        (총 6 vCPU / 24GB)
OS               : **Ubuntu 24.04 LTS (동결)** — 커널 6.8. 자동화 분기를 하나로 줄인다
Root SSD         : 50GB × 3   (VM 요금 포함)
Data-A           : 25GB × 3  /mnt/k3s      ← K3s data-dir · etcd · **컨테이너 이미지** · kubelet
Data-B           : 40GB × 3  /mnt/aligner  ← local-path PV (PostgreSQL 전용. Redis 는 emptyDir)
                   ※ 복수 볼륨 불가 시 단일 65GB + LVM 분할 (문의 C6)
Load Balancer    : Gabia External LB (Small) — **443/80 두 리스너만.** 6443 없음
공인 IP          : 4개 (노드 3 아웃바운드 + LB 1)
관리망           : **Phase 1 시작을 freeze로 두는 시한부 분기** (§1.5.1)
                   승인 → Tailscale Community (subnet router 2대, 자동 failover ~15초)
                   미승인 → WireGuard 게이트웨이 2대 (VPC CIDR 라우팅 + MASQUERADE)
                   22·6443은 어느 경우든 공인망 차단
break-glass      : 가비아 VNC 콘솔(문의 C5) 또는 rescue-Ubuntu-22.04 이미지 부팅

[ 플랫폼 ]
Kubernetes       : K3s (embedded etcd ×3, secrets-encryption: true)
                   ※ Talos는 커스텀 이미지 미지원으로 배제 (문의 C1로 재검토)
Runtime          : containerd
CNI              : **Cilium — Day 1 최소 구성** (§2.3)
                   VXLAN tunnel · cluster-pool IPAM · kubeProxyReplacement: false
                   Hubble agent 메트릭만 (Relay·UI 끔) · L7 proxy·ClusterMesh 미사용
                   부트스트랩은 **Ansible 이 컨트롤 머신에서 helm 실행** — Argo CD·auto-deploy 아님
                   Phase 1 Gate 실패 시 Flannel로 클러스터 재생성 (운영 중 교체 없음)
NetworkPolicy    : 표준 default-deny (Phase 1 DoD). CiliumNetworkPolicy 는 실제 요구 시
Ingress 구현체   : Traefik × 3 (K3s 번들 해제 → Argo CD가 Helm으로 관리)
Ingress 리소스   : Gateway API (Gateway + HTTPRoute) — IngressRoute 미사용
TLS              : cert-manager + Let's Encrypt
Storage          : local-path Provisioner (Longhorn 미도입, quota 미강제 — LVM으로 보완)

[ 저장소 — 역할 기준 분리 ]
ALIGNER-SERVER
  위치         : Nexters Organization
  공개 범위     : Public
  역할         : Kotlin/Spring Boot 애플리케이션, 테스트, 컨테이너 이미지 CI
  라이선스      : Apache-2.0

ALIGNER-PLATFORM
  위치         : Nexters Organization
  공개 범위     : Public
  역할         : Terraform·gabiactl 설정, Ansible, K3s/Cilium, GitOps, ADR, Runbook
  공개 제외     : tfstate · tfplan · 실제 tfvars · generated inventory · private key · token
  Secret       : 정본은 **Infisical Cloud**. CI 는 OIDC. Password Manager 는 Bootstrap·복구 예외만
  GitOps Secret: ExternalSecret 경로 참조만 Git 에 저장 (값은 Infisical 에만 존재)
  라이선스      : Apache-2.0

terraform-provider-gabiacloud
  위치         : 이동훈 개인 계정
  공개 범위     : Private 로 시작
  역할         : Go API Client + gabiactl 공통 코드 + Terraform Provider
  공개 전제     : 가비아 API 자동화·재배포 허용 여부 확인(문의 D7) 및 fixture 비식별화

[ 배포 ]
IaC (L1)         : **gabiactl(Go) + Ansible** — Phase 1 필수 경로
                   검증 완료: 세션 발급(2h), Subnet CRUD, Network·Server·Image GET
                   미검증: SG·Volume·Public IP·LB 경로와 스키마, 비동기 상태 전이
                   → 이들을 검증하기 전에는 "L1 IaC 완성"으로 판정하지 않는다
                   병행 트랙: terraform-provider-gabiacloud (M0 완료, M1 진행)
                   Provider M3~M5 안정화 후 import → plan No changes → 정본 전환
OpenStack        : 내부 구현 기술로 추정하되 고객용 API로 확정하지 않는다
                   Keystone auth_url·Application Credential 공식 제공 시에만 대체안
IaC (L2)         : cloud-init + Ansible (디스크·OS·관리망·Cilium·K3s·systemd)
CI               : GitHub Actions → GHCR → ALIGNER-PLATFORM 에 digest 변경 PR
GitOps (L3)      : Argo CD (app-of-apps, automated sync · prune · selfHeal)
                   ※ CNI 는 L2 소유 — GitOps 가 관리하지 않는다
Overlay          : normal      1노드 장애를 **사람 개입 없이 자동 생존** (필수 request ≤ 85%)
                   degraded    장기 장애 시 비필수 워크로드 축소 · Pending 정리 · 배포 차단
                   maintenance 계획 작업 (업그레이드 · 키 회전 · 데이터 복구)
State            : AWS S3 Remote Backend (Versioning · SSE · use_lockfile · 최소 권한 IAM)
                   .terraform.lock.hcl 커밋. state·plan 은 비밀정보로 취급
Manifest         : Kustomize (자체 앱) + Helm (외부 솔루션)
Image            : digest 고정, latest 금지
Secret 정본      : **Infisical Cloud** (단일 정본)
동기화           : External Secrets Operator → native Kubernetes Secret
CI 인증          : GitHub Actions **OIDC** (장기 토큰 없음)
etcd 암호화       : K3s secrets-encryption (필수 — ESO 가 native Secret 을 만든다)
Secret Zero      : Infisical Machine Identity 1쌍만 수동 주입 (오프클러스터 보관)
                   가비아 ID/PW 의 정본은 Infisical aligner-infra 뿐이다.
                   환경변수는 전달 방식이고 GitHub Secrets 는 보관 장소가 아니다 — 실제 ID/PW 를
                   GitHub Secrets 에 복제하지 않는다
                   x-cloud-session 은 프로세스 메모리에만 — state·로그·Git·CI Artifact 금지
계정             : aligner-terraform 전용 최소 권한 서브 계정. root/owner 사용 금지
가비아 계정      : **사람·자동화 계정 모두 2FA 미사용** (명시적 예외 ADR, §2.8.6)
                   자동화는 최소 권한 aligner-terraform 계정만 사용. Owner 자동화 금지
                   비밀번호는 Infisical aligner-infra Project 에만 저장
Infisical 계정   : 운영자 2명 모두 2FA 적용

[ 데이터 ]
Database         : CloudNativePG 2 instance — **single-failure automatic failover**
                   (완전한 노드 장애 내구성이 아님. §2.5.3)
                   WAL 별도 PVC 없음
                   max_wal_size 1GB 는 **checkpoint soft target — 디스크 상한이 아니다**
                   archive_timeout 300s 적용 (RPO 5분 목표의 전제)
                   누적 감시: pg_wal 사용량 · archive failed_count ·
                             last_archived_time 15분 · Data-B 60/75/85% 3단 경보
                   트래픽은 -rw 기본. -ro는 일관성 요구 낮은 조회만
Backup 저장소    : Cloudflare R2 — **prefix 분리로 retention 과 불변성 충돌 해소** (§2.5.2)
                     hot/{cnpg,etcd}       짧은 보존 · 자동 prune 허용 · Bucket Lock 없음
                     immutable/monthly/**  Bucket Lock (WORM 3~6개월)
                   + AWS S3 monthly/ (Object Lock, 다른 계정·다른 CSP)
                   ※ R2 호환성은 §2.5.4 acceptance test 통과 후 확정
자격증명 3분할   : backup-writer  클러스터 내부 · hot/** Put·List·**Delete 허용**
                   archiver       클러스터 **외부** · hot/** Get + immutable/** Put · Delete 없음
                   restore        오프클러스터 보관 · 전체 Get·List · Put·Delete 없음
Backup           : Barman Cloud (WAL 연속 + 주간 basebackup, PITR)
etcd Backup      : K3s 내장 snapshot → R2 hot/etcd/ (6시간)
                   + **server token 오프클러스터 보관 (없으면 복구 불가)**
Cache            : Redis 1 — **emptyDir, PVC 없음** (유실 허용 + 자유 재스케줄)

[ 관측 ]
Collector        : Grafana Alloy DaemonSet ×3 (metrics · logs · traces + Hubble 메트릭)
Backend          : Grafana Cloud (클러스터 외부 — 장애 시에도 생존)
클러스터 내부    : metrics-server, kube-state-metrics 만
핵심 지표        : etcd WAL fsync p99 · pod unschedulable · CPU throttle 비율
                   CNPG archive lag · 마지막 성공 백업 시각 · inode 사용률
                   Hubble drop·policy-deny·DNS 실패
Alerting         : Grafana Cloud + 외부 Synthetic 프로빙 → Slack/Discord

[ 비용 ]
월 예상액        : 303,793원 (VAT 포함)
9개월 기본 운영  : 2,734,137원
재구축 리허설    : 182,270원 (신규 2노드, 1개월)
예상 총 소진     : 2,916,407원 (97.2%) · 예비 83,593원
크레딧           : 3,000,000원 통합 풀 (월 한도 없음) · 만료 2027-07-31
크레딧 밖 현금   : R2 + S3 + Grafana Cloud ≈ 월 1,500원 (§2.5.2)
크레딧 미적용    : Windows·MSSQL·Tibero·가비아 부가서비스 → 전부 미사용이므로 영향 0
```

## 원본 설계안 대비 변경 요약

| # | 변경 | 원본 | 본안 | 원인 |
| --- | --- | --- | --- | --- |
| 1 | 노드 사양 | `2/4` × 3 (12GB) | **`2/8` × 3 (24GB)** | 월 예산 25만 → 33만 원 |
| 2 | 기간 | 12개월 | **9개월** | 조건 변경 |
| 3 | GitOps | Flux CD | **Argo CD** | 프로젝트 README 정본 일치 + 팀 5인 가시성 + 메모리 제약 해소 |
| 4 | Secret | SOPS + age | **Sealed Secrets** | Argo CD는 SOPS 내장 미지원 (3번의 귀결) |
| 5 | Database | 단일 Primary + 백업 | **CNPG 2 instance + PITR** | 메모리 24GB 확보 |
| 6 | Ingress 관리 | K3s 번들 Traefik | **번들 해제 → Argo CD Helm** | GitOps 일관성 (버전·설정을 Git에) |
| 7 | etcd 배치 | 기본 경로 | **Data SSD 분리** | fsync I/O 격리 |
| 8 | etcd 백업 | 로컬 + 주 1회 수동 S3 | **K3s 내장 S3 직접 업로드 6시간** | 내장 기능 활용, CronJob 제거 |
| 9 | NetworkPolicy | “초기 필수 보안” | **Phase 1 DoD, default-deny** | 시점 명시 |
| 10 | 관리 접근 | 고정 IP 화이트리스트 | **Phase 1 freeze 시점에 Tailscale Community 또는 WireGuard 하나만 배포** (§1.5.1) | 유동 IP 대응 + 22·6443 미노출. 3판 WireGuard 확정 → 4판 시한부 분기 |
| 11 | 백업 검증 | 7~9개월차 | **Phase 2(4개월차) + 월 1회 정례** | 검증 안 한 백업은 백업이 아니다 |
| 12 | 자원 산정 | requests 상한만 제시 | **1노드 장애 기준 검증 + PriorityClass 축소 운전** | 정량 검증 |
| 13 | JVM 설정 | 언급 없음 | **§3 전체** | JVM 특성 반영 요구 |
| 14 | 잔여 크레딧 | 소진율 99.9% | **98% + Phase 4 재원으로 계획** | 변동비 초과 방어 |
| 15 | 요금 근거 | 계산기 전제 | **계산기 실제 단가표 추출** | 검증 가능성 |
| 16 | **백업 저장소** | AWS S3 | **Cloudflare R2 1차** | 가비아에 오브젝트 스토리지 없음 확인 + egress 무료로 복구 훈련 비용 0 |
| 17 | **Ingress 리소스** | Ingress | **Gateway API `HTTPRoute`** | ingress-nginx 은퇴 후 2026 표준. 벤더 종속 제거 |
| 18 | **CNI 계획** | Flannel 고정 | **Cilium Day 1 최소 구성** (4판. 2판의 "Phase 3 운영 클러스터 전환"은 철회된 상태를 유지) | 신규 클러스터에서 마이그레이션 리스크를 만들지 않는다. 커널 5.10+ 이미지 제공 확인(§2.3) |
| 19 | **L1 IaC 도구** | Terraform 전제 | **초기 `gabiactl`(Go) + Ansible → 안정화 후 Terraform + Custom Provider** (§2.8.5) | 가비아 provider 없음. 33-star provider 의존은 Terraform의 목적과 모순. Provider 개발이 클러스터 구축을 막지 않는다 |
| 20 | **Talos Linux** | 미검토 | **검토 후 배제 (가비아 커스텀 이미지 미지원)** | 2026 자체 운영 K8s 정석. 문의 C1 답변에 따라 재검토 |

## 3판 수정 — 외부 리뷰 반영 (P0 8건 · P1 7건)

정상 상태 설계는 유지하되 **장애 상태 모델링의 결함**을 고쳤다. 아래 11건이다.

| # | 수정 | 이전 | 3판 | 심각도 |
| --- | --- | --- | --- | --- |
| 1 | **CPU allocatable 분모 오류** | 4150/6000 = 69% | **2840/4800 = 59%.** 1노드 장애 시 CPU·메모리 모두 초과 명시 | **치명** |
| 2 | **degraded overlay 신설** | PriorityClass로 축소 | **normal / degraded / maintenance 3 overlay.** 사람이 1회 sync | **치명** |
| 3 | QoS 오기 | "Guaranteed" | **Burstable** (CPU req≠limit). eviction ranking으로 근거 재서술 | 중 |
| 4 | HPA 서술 오류 | "노드 장애 시 API가 2개로 줄어 여유 확보" | **삭제.** 노드 장애는 HPA 축소 신호가 아니다(사용률이 오르므로 스케일아웃) | 중 |
| 5 | PriorityClass 서술 | "결정적 축출 순서" | **"스케줄링 가능성을 높이는 보조 장치".** preemption/eviction 구분 명시 | 중 |
| 6 | **K3s server token 백업 누락** | 없음 | **`/var/lib/rancher/k3s/server/token` 필수.** 없으면 etcd 복구 불가(공식 문서) | **치명** |
| 7 | **백업 불변성·순환 의존** | R2·S3에 두는 것만 | **Bucket Lock/Object Lock + writer(Delete 불가)/restore 자격증명 분리 + 오프클러스터 보관 목록** | **치명** |
| 8 | **디스크 재설계** | 40GB 시작, WAL 별도 PVC | **65GB 시작, Data-A 25(etcd+이미지) / Data-B 40 2볼륨 분리, WAL PVC 제거, LVM·mount guard** | 상 |
| 9 | CNPG 명명·라우팅 | "PostgreSQL HA", Query는 `-ro` | **"single-failure automatic failover"**, `-rw` 기본(복제 지연으로 read-your-writes 깨짐) | 상 |
| 10 | **CNI 전환 철회** | Phase 3에 운영 클러스터 Cilium 전환 | **운영 중 CNI 교체 금지** (이 원칙은 4판에서도 유지. 단 4판은 Day 1 Cilium으로 시작한다) | 상 |
| 11 | **관리망 교체** | Tailscale + LB 6443 (모순) | **WireGuard 게이트웨이 2대 + LB 6443 제거 + break-glass 명시.** Tailscale Personal은 비상업용 한정 | 상 |

부수 수정: `secrets-encryption: true` 추가(Sealed Secrets는 etcd를 암호화하지 않음),
`system-reserved` 1Gi 상향 및 이중계산 제거, JVM `limits.cpu` 1500m 하향(`ceil()`로
`availableProcessors()=2` 유지), Metaspace·Xss hard cap 초기 제거, heap dump `sizeLimit`·PII
절차, "DR" → "재구축·데이터 복원 리허설" 명칭 정정, HA 명칭에 단일 장애 도메인 단서,
관측 지표 9종 추가, 문의 문안 C5~C7·D2 보강·F 그룹 신설.

## 4판 수정 — API 실측과 외부 리뷰 반영

3판까지는 "가비아에 API가 있을까"를 추론하는 단계였다. **4판은 실제 호출로 확인된 사실 위에
서 있다.** 그 결과 IaC 절이 전면 교체되고 CNI 결론이 다시 뒤집혔다.

| # | 수정 | 3판 | **4판** | 근거 |
| --- | --- | --- | --- | --- |
| 1 | **문서 위치** | Public 저장소 | **Private `aligner-infra`로 이관** | `ALIGNER-SERVER`가 Public이라 CIDR·보안그룹·break-glass가 공개돼 있었다 |
| 2 | **저장소 구조** | 앱 / GitOps 2개 | **앱 / infra / provider 3개** | 1번의 귀결 + CI 재귀 트리거 방지 |
| 3 | **§2.8 IaC 전면 교체** | "OpenTofu 1순위" · "Ansible 1순위" · "OpenStack 1순위" **3중 모순** | **가비아 자체 API + gabiactl(Go) 단일 경로.** Provider는 병행 트랙 | 실측으로 사실 확정 |
| 4 | **Swagger 존재 추론 삭제** | "401이므로 경로 존재 가능성" | **명세 없음.** 미인증은 전부 401, 인증 후 404 | 임의 경로도 401 확인 |
| 5 | **OpenStack 순위 하향** | 1순위 | **대체안** (Keystone 자격증명 공식 제공 시) | 관리형 K8s 내부 주입 자격증명일 수 있다 |
| 6 | **Provider를 선행 조건에서 제외** | (해당 없음) | **Phase 1은 gabiactl. Provider 완성을 기다리지 않는다** | 3~6주 개발이 클러스터 구축 일정을 잡는다 |
| 7 | **CNI → Cilium Day 1** | Flannel 9개월 고정 | **Cilium 최소 구성 + Phase 1 Gate** | 신규 클러스터이므로 나중 마이그레이션보다 안전. **커널 요구 해소**(Rocky 9.6 / Ubuntu 24.04 제공 확인) |
| 8 | **관리망 시한부 분기** | WireGuard 채택 | **Phase 1 시작을 freeze로 두고 하나만 배포** | 3판 안은 둘 다 만들게 된다 |
| 9 | **State 백엔드** | OpenTofu state 암호화 | **S3 + Versioning + SSE + `use_lockfile`** | Terraform 확정. 감사 가능성이 더 높다 |
| 10 | **2FA 를 계정 역할로 분리** | (해당 없음) | **사람 계정만 2FA, 자동화 계정은 password only.** 5판에서 "OTP 호환성 실측"을 삭제 | 자동화 계정에 2FA 를 켜지 않으면 호환성 문제가 발생하지 않는다. 질문을 "계정별 적용 가능 여부"로 교체 |

**4판에서 정정한 제 과장 3건**

| 표현 | 정정 |
| --- | --- |
| "Terraform의 가치는 보안그룹 drift뿐" | 과장. 의존 순서·삭제 순서·Replace 판정·import·output 연결이 모두 가치다. 정확한 문장은 **"9개월·저빈도 생성에서는 Provider 개발비를 Phase 1 전에 회수하기 어렵다"** |
| "API가 바뀌면 destroy도 못 해 IaC 없는 것보다 나쁘다" | 과장. `terraform state rm`은 provider 호출 없이 state만 편집하므로 탈출 경로가 있다. 정확한 심각도는 **"자동 관리의 일시적 중단"** (§2.8.9) |
| "Cilium agent 400~600MB / 250~350MB" | 출처 없는 수치. Cilium 공식 Helm 기본값은 `resources: {}`로 **강제 request가 없다.** 실측이 필요하다 |

**번복 이력을 남기는 이유** — CNI는 1판 Flannel → 2판 Phase 3 전환 → 3판 Flannel 고정 →
4판 Day 1 Cilium으로 네 번 바뀌었다. 각 판의 근거와 무엇이 틀렸는지를 §2.3에 표로 남겼다.
2판의 실패 원인은 **GitHub 별점과 "표준"을 아키텍처 근거로 쓴 것**이고, 4판이 다시 뒤집을 수
있었던 것은 **커널 버전이라는 검증 가능한 사실**을 확인했기 때문이다. 판단이 아니라 근거의
질이 바뀐 것이다.

## 5판 수정 — Public Platform 저장소 전환

4판은 실제 CIDR·보안그룹·관리망·Runbook이 포함된다는 이유로 인프라 저장소 전체를 **Private으로
결정**했다. 재검토 결과, **저장소 공개 여부와 시크릿 보관 여부를 분리**하는 편이 오픈소스성과
운영 단순성을 함께 얻을 수 있다고 판단했다.

| # | 수정 | 4판 | 5판 | 근거 |
| --- | --- | --- | --- | --- |
| 1 | 플랫폼 저장소 공개 범위 | `aligner-infra` **Private** | **`ALIGNER-PLATFORM` Public** | IaC·Ansible·GitOps 코드는 공개 가능하다. 보안은 인증·최소 권한·방화벽·키 관리로 보장한다 |
| 2 | 운영 실값 | Private Git에 커밋 | **Git 외부 주입 또는 generated file** | Public 여부와 무관하게 state·key는 Git 금지 |
| 3 | 환경 저장소 | 인프라 저장소에 포함 | **별도 `ALIGNER-ENV` 미도입** | 단일 클러스터에서 저장소 분리 비용이 더 크다 |
| 4 | Private submodule | 미검토 | **미사용** | 로컬·CI·Argo CD 인증과 커밋 포인터 관리 복잡도 |
| 5 | 생성 인벤토리 | Git 추적 | **`.gitignore` 대상** | 리소스 ID·IP를 실행 시 생성 |
| 6 | SealedSecret | Private Git | **Public Git에 암호문 저장** | private key만 오프클러스터 보관하면 성립한다 |
| 7 | Provider 위치 | 팀 Private | **이동훈 개인 Private** | Aligner에 종속되지 않는 재사용 소프트웨어. 공개는 문의 D7 답변 후 |
| 8 | 저장소 분리 근거 | "인프라는 공개하면 안 된다" | **"변경 책임과 생명주기가 다르다"** | 공개 여부는 분리 이유가 아니다 |

**5판의 최종 원칙**

> **플랫폼 코드와 운영 구성을 Public으로 공개하되, 자격증명·State·Private Key·생성된 인벤토리는
> 처음부터 Git의 관리 대상에서 제외한다. 별도의 ENV 저장소와 Private submodule은 도입하지 않는다.**

**4판의 Private 결정 기록은 지우지 않는다.** 그 시점의 판단 근거(실제 CIDR·break-glass 노출)는
타당했고, 5판이 뒤집은 것은 **"노출을 막는 방법이 저장소 비공개가 아니라 값의 분리"** 라는
인식이다. 위 표와 §공개 저장소 운영 원칙이 그 전환을 기록한다.

## 6판 수정 — 시크릿 정본 통합과 장애 생존 요구 강화

5판까지의 두 가지 결함을 고쳤다. **하나는 시크릿 정본이 네 곳으로 흩어져 있었던 것**이고,
**다른 하나는 1노드 장애 생존에 사람 개입을 전제했던 것**이다.

| # | 수정 | 5판 | **6판** | 근거 |
| --- | --- | --- | --- | --- |
| 1 | **시크릿 정본** | Sealed Secrets(Git) + 패스워드 매니저 + GitHub Secrets + 환경변수 = **4곳** | **Infisical Cloud 단일 정본** + ESO 동기화 | 5판은 Kubernetes 시크릿만 다뤘고 가비아·R2·Grafana·K3s token 은 흩어져 있었다(§2.6.1) |
| 2 | **재해 복구 리스크** | 봉인 키 분실 → 모든 SealedSecret 영구 복호화 불가 | **Machine Identity 재발급 가능** | 복구 불가능한 손실을 제거했다(§2.6.2) |
| 3 | **CI 인증** | GitHub Secrets 에 장기 토큰 | **GitHub Actions OIDC — 장기 토큰 0** | 유출 시 영향 범위 축소 |
| 4 | **1노드 장애 생존** | degraded overlay **필수** (사람이 sync) | **`normal` 이 자동 생존** (필수 request ≤ 2노드의 85%) | 사람 개입이 필요하면 HA 가 아니다(§3.5) |
| 5 | **degraded 역할** | 생존 절차 | **장기 장애 시 Pending 정리·여유 확보·배포 차단** | 생존과 정리를 분리했다(§3.5.2) |
| 6 | **Redis** | local-path PVC 512Mi | **emptyDir 256Mi** | PVC 는 노드에 고정돼 재스케줄을 막는다 — 4번 요구와 충돌 |
| 7 | **secrets-encrypt 키 회전** | `prepare → rotate → reencrypt` | **`rotate-keys` 1회** + 3노드 hash 일치 확인 | 5판 절차는 legacy 다(§2.6.8) |
| 8 | **디렉터리 구조** | `l1-infra`/`l2-nodes` + 번호 playbook 10개 + `modules/` 3개 | **`infra`/`ansible`/`gitops`/`.runtime` + `site.yml` + root module 하나** | 구현 전 과도한 분리. HashiCorp·Ansible 공식 지침은 평평하게 시작하라고 한다(§2.8.10) |
| 9 | **GitOps 계층** | `platform`/`policies`/`database`/`apps` | **`infrastructure/{controllers,configs}`** 분리 | CRD(wave 0) 와 CR(wave 1) 의 의존 순서를 디렉터리가 표현한다 |
| 10 | **Public 저장소 보호** | secret scan · push protection | **+ Third-party Action commit SHA 고정 · Actions 최소 permissions · Dependabot** | Public 은 취약점 공개 대상이 된다 |

**6판에서 새로 인정한 리스크** — Infisical Cloud는 외부 SaaS이며 부트스트랩 경로에 있다.
§2.6.9에 장애 시나리오 4종과 대비를 명시했고, **ESO Provider 교체로 정본을 이전할 수 있다는 것**이
이 의존을 받아들이는 근거다. Infisical 무료 티어 한도는 Phase 0 ⑦에서 확인한다.

## 7판 수정 — 문서 모순 제거와 권한 경계 구조화

6판까지의 개정을 합치는 과정에서 **문서 내부 모순 9건**이 남아 있었다. 설계 문제가 아니라
작업자가 서로 다르게 해석할 수 있는 문제이므로 착수 전에 제거했다.

| # | 수정 | 6판 잔존 | **7판** |
| --- | --- | --- | --- |
| 1 | **Infisical 권한 경계** | 단일 Project + **경로별** 최소 권한 | **Project 2개** (`aligner-infra` / `aligner-runtime`). ESO 는 runtime 만 가입 |
| 2 | Cilium 설치 방식 | 본문 = Ansible helm · 최종 요약 = **auto-deploy 매니페스트** | **Ansible helm 으로 통일.** auto-deploy 문장 삭제 |
| 3 | 시크릿 관리 주체 | 최상단·요약에 **GitHub Secrets + Password Manager** | 정본은 **Infisical**. Password Manager 는 **Bootstrap·복구 예외만** |
| 4 | 가비아 2FA | "가능하면 사람 계정만 2FA" + 문의 D6 | **전 계정 미사용 ADR.** D6 삭제 |
| 5 | 1노드 장애 생존 | 일부에 "degraded 필요" 잔존 | `normal` 자동 생존으로 통일 |
| 6 | Data-A 용량 | 다이어그램 **20GB** / 본문 25GB | **25GB 로 일괄** |
| 7 | overlay 설명 | "장애 시 사람이 1회 sync" | normal 자동 생존 / degraded 장기 장애 / maintenance 계획 작업 |
| 8 | **OS** | Rocky 9.6 **또는** Ubuntu 24.04 | **Ubuntu 24.04 LTS 동결** (커널 6.8) — 자동화 분기 축소 |
| 9 | 구형 경로 | `l2-nodes/playbooks/45-cilium.yml` | `ansible/roles/cilium/tasks/main.yml` |

**#1이 가장 중요한 실질 변경이다.** 6판의 "경로별 최소 권한"은 **Infisical RBAC Custom Role에
의존**하고 **그것은 Pro 기능**이다. 무료 플랜에서 동작한다고 가정하면 안 된다.

> **보안 경계를 요금제 기능에 의존하게 두는 것 자체가 설계 결함이다.** Project 멤버십은 플랜과
> 무관하게 강제되므로, ESO를 `aligner-infra`에 **가입시키지 않는 것**으로 가비아 ID/PW·K3S_TOKEN·
> 백업 키에 대한 접근 경로를 **구조적으로 제거**한다. Role 설정 실수나 플랜 변경으로 뚫릴 여지가 없다.

**Gate를 강화한 것 3건**

| 항목 | 이전 | **7판** |
| --- | --- | --- |
| 1노드 장애 자원 | 집계 82.6% 계산으로 판정 | **실제 VM 정지 후 필수 Pod Pending 0 · 노드별 requests 확인** 9항목. 집계 용량이 맞아도 anti-affinity·topology spread·조각화로 배치가 실패할 수 있다 |
| R2 호환성 | 단일 acceptance test 8항목 | **CNPG Barman 과 K3s etcd-s3 를 별도 테스트로 분리.** 서로 다른 S3 클라이언트다 |
| CNPG node-loss | 시간 "측정" | **Write RTO ≤ 60초 · redundancy 복귀 ≤ 30분** 등 정량 기준 6항목 |

## 최종 의사결정표

| 영역 | 최종 결정 | 판정 |
| --- | --- | --- |
| Application Repo | `Nexters/ALIGNER-SERVER` Public | **GO** |
| Platform Repo | `Nexters/ALIGNER-PLATFORM` Public | **GO** |
| Environment Repo | 생성하지 않음 | **GO** |
| Git Submodule | 미사용 | **GO** |
| Provider | 개인 Private 로 시작 · 공개는 문의 D7 후 | **GO** |
| **Secret 정본** | **Infisical Cloud** | **GO** (무료 티어 한도 확인 필요) |
| **Kubernetes Secret 동기화** | **External Secrets Operator** | **GO** |
| GitHub 인증 | **OIDC** — 장기 토큰 없음 | **GO** |
| ESO 인증 | Universal Auth Bootstrap credential 1쌍 | **조건부 GO** (오프클러스터 보관 필수) |
| K3s Secret 저장 | `secrets-encryption: true` | **필수** |
| 가비아 인증 | ID/PW → 2시간 세션 | **제약 기반** (API Key 미제공) |
| 가비아 2FA | 미사용 | **명시적 예외** (§2.8.6 보완 통제) |
| Kubernetes | K3s 3노드 embedded etcd | **GO** |
| CNI | Cilium Day 1 + Phase 1 Gate | **조건부 GO** |
| Ingress | Traefik + Gateway API(`HTTPRoute`) | **GO** |
| GitOps | Argo CD (app-of-apps) | **GO** |
| Database | CNPG 2 instances (single-failure automatic failover) | **조건부 GO** |
| Storage | local-path + 외부 Backup | **예산 절충** |
| Redis | emptyDir 캐시 (PVC 없음) | **GO** |
| Observability | Alloy + Grafana Cloud | **GO** |
| Backup | R2 `hot`/`immutable` + AWS S3 | **GO** |
| **1노드 장애 생존** | **`normal` overlay 자동 생존 (필수 ≤ 85%)** | **조건부 GO** (실측 필요) |
| degraded / maintenance | 장기 장애·계획 작업용 | **GO** |

## 2026-08-06 기준 스택 재감사 실측

도구 선택이 현재 시점 best practice인지 GitHub 실측으로 대조한 결과다.

| 프로젝트 | stars | 최근 push | 판정 |
| --- | --- | --- | --- |
| K3s | 33,661 | 2026-08-05 | ✅ 채택 (RKE2 2,298 / k0s 6,408) |
| Talos Linux | 10,886 | 2026-08-05 | ⚠️ 가비아 제약으로 배제 |
| Argo CD | 23,845 | 2026-08-05 | ✅ 채택 (Flux 8,316) |
| Cilium | 24,860 | 2026-08-05 | ✅ **Day 1 조건부 채택** (Phase 1 Gate) |
| Flannel | 9,519 | 2026-08-05 | Gate 실패 시 재구축 대상 |
| Traefik | 64,292 | 2026-08-05 | ✅ 채택 (Envoy Gateway 2,935) |
| Gateway API | 2,963 | 2026-08-04 | ✅ 리소스 표준으로 채택 |
| **External Secrets Operator** | 6,778 | 활성 | ✅ **채택** (6판 — Infisical 동기화 계층) |
| Infisical | 25,000+ | 활성 | ✅ **Secret 단일 정본** (별점은 보조 신호로만 본다) |
| Sealed Secrets | 9,230 | 2026-08-04 | ❌ **철회** (6판 — 범위가 Kubernetes 전용, §2.6.1) |
| SOPS / ESO | 22,693 / 6,778 | 활성 | 전환 후보 (둘 다 CNCF) |
| CloudNativePG | 9,091 | 2026-08-05 | ✅ 채택 (CNCF) |
| Longhorn | 7,902 | 2026-08-04 | ❌ 미도입 (open issues 1,810) |
| Grafana Alloy | 3,409 | 2026-08-05 | ✅ 채택 (Grafana Agent 후속) |
| OpenTelemetry Collector | 7,347 | 2026-08-05 | 대안 (Alloy와 호환) |
| Terraform / OpenTofu | 49,413 / 29,691 | 활성 | **Terraform 확정.** Provider 안정화 후 L1 정본 전환 |
| `Mastercard/restapi` · `magodo/restful` | 919 · **33** | — | ❌ **둘 다 철회.** 자체 API 는 Go Client + gabiactl 로 직접 다룬다(§2.8.5) |

## 유지된 판단

원본에서 그대로 유지한 결정과 그 이유다. 재검토 결과 여전히 최선이다.

| 판단 | 유지 근거 |
| --- | --- |
| K3s (kubeadm·RKE2·k0s 대신) | 9개월의 병목은 도구 학습이 아니라 운영 완주. Control Plane 오버헤드 절감 = JVM heap |
| 3노드 통합형 (CP/Worker 분리 대신) | 같은 예산에서 저사양 6노드보다 충분한 사양 3노드가 안정적 |
| embedded etcd ×3 (외부 DB 대신) | 외부 DB는 추가 HA 비용과 장애 지점 |
| ~~Flannel VXLAN (Cilium 대신)~~ | **철회.** 4판은 **Cilium Day 1 조건부 채택**이다(§2.3). Gate 실패 시 Flannel로 클러스터 재구축 |
| kube-proxy (eBPF replacement 대신) | **유지.** `kubeProxyReplacement: false`. 운영 중 서비스 라우팅 전환은 하지 않는다 |
| **운영 중 CNI 교체 금지** | 이 원칙은 모든 판을 통해 유지된다. Gate 실패 시에도 "교체"가 아니라 **재구축**이다 |
| 가비아 External LB (MetalLB·kube-vip 대신) | 외부 진입점과 헬스 체크를 관리형으로 |
| Traefik (ingress-nginx 대신) | ingress-nginx는 2026년 3월 은퇴, 저장소 read-only, 보안 패치 없음 |
| cert-manager (Traefik 내장 ACME 대신) | 3 replica에서 인증서 중앙 관리 |
| local-path (Longhorn 대신) | Longhorn 권장 4 vCPU에 미달. 복제는 PostgreSQL 계층에서 해결 |
| Alloy → Grafana Cloud (내부 스택 대신) | 관측 백엔드를 관측 대상과 같은 클러스터에 두면 장애 시 진단 수단을 동시에 잃음 |
| PSA + NetworkPolicy (Kyverno·Gatekeeper 대신) | 정책 엔진은 정책을 운영할 인력이 있을 때 가치 있음 (운영 2명) |
| Kubeflow 미도입 | GPU·ML 파이프라인 요구 없음. LLM API 호출은 Deployment·Job으로 충분 |
| Istio 미도입 | 서비스 3개 미만에서 서비스 메시는 순수 오버헤드 |

---

## Go / No-Go — 단계별 진입 판정

이 문서는 **"프로덕션 구축을 지금 시작해도 된다"를 뜻하지 않는다.** 단계별 판정을 명시한다.

| 단계 | 판정 | 조건 |
| --- | --- | --- |
| **ALIGNER-PLATFORM Public 저장소 생성 · 실값 placeholder 화 · 인증정보 회전** | **즉시 GO** | secret scan 통과 후 공개 |
| API endpoint matrix · gabiactl · Ansible 개발 | **GO** | — |
| **비프로덕션 3노드 클러스터 생성** | **GO** | v7 문서 정합성 수정 완료 후 |
| **Cilium 프로덕션 확정** | **Phase 1 Gate 통과 후 GO** | **1노드 장애 시 `normal` overlay 필수 워크로드 request ≤ 2노드 allocatable 85%** 실증 + 기능·장애 Gate(§2.3) |
| **PostgreSQL 실데이터 투입** | **검증 후 GO** | 훈련 #3b(node-loss) + PITR + **R2 acceptance test**(§2.5.4) |
| **실사용자 프로덕션 오픈** | **현재 NO-GO** | Phase 1 DoD 전 항목 + 훈련 #1·#3b + 백업 복구 1회 검증 |
| Terraform Provider 완성 대기 | **불필요** | 병행 트랙. 구축을 막지 않는다 |

**현재 상태 요약** — 아키텍처 방향은 확정됐고, 비프로덕션 환경 구축은 진행 가능하다.
**실사용자 트래픽 투입은 Phase 1 Gate 통과 전까지 보류한다.** 특히 다음 셋이 미검증이다.

```text
1. Cilium 자원 Gate      1노드 장애 시 필수 메모리 82.6% (기준 85% 이하 — 추정치 기반)
2. R2 + Barman 호환성    acceptance test 미실시
3. CNPG node-loss 복구    Pod 삭제만 계획돼 있었고 노드 영구 유실은 미검증
```

---

## 이 설계의 원칙

1. **예산이 늘면 결론을 다시 계산한다.** 원본의 Flux·SOPS·PG 단일 Primary는 12GB 제약의
   산물이었다. 제약이 사라졌는데 결론이 같으면 재검토를 하지 않은 것이다.
2. **검증하지 않은 것은 완료가 아니다.** 백업·HA·무중단 배포는 모두 “실제로 깨뜨려 보고
   복구한 기록”이 있을 때만 DoD를 통과한다.
3. **자원 한계를 숫자로 안다.** 1노드 장애 시 12.0Gi vs requests 13.0Gi라는 계산과, 그때
   무엇이 먼저 밀려나는지(PriorityClass)를 미리 정한다.
4. **기술을 많이 설치하지 않는다.** 3노드 HA에 필요한 것만 유지하고, 고급 기능은 실제 요구가
   생기거나 별도 재원으로 검증한 뒤 도입한다. (원본의 결론이며 여기서도 유지한다.)
5. **끝을 설계에 넣는다.** 9개월 뒤 크레딧이 만료되는 것은 리스크가 아니라 알려진 조건이다.
   Phase 4의 이관 리허설과 잔여 크레딧 집행 계획은 처음부터 설계의 일부다.
