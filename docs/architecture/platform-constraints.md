# 플랫폼 제약과 버전 Gate

기준일: 2026-08-12. 이 문서는 계정·시크릿·실제 ID/IP를 저장하지 않는다. 아래 Gate가
닫혀 있으면 `gabiactl apply` 또는 프로덕션 백업 전환을 진행하지 않는다.

## 가비아 Gen2

| 항목 | 상태 | 결정 또는 중단 조건 |
| --- | --- | --- |
| VPC/subnet | 확인됨 | `{{ vpc_cidr }}`와 `{{ subnet_cidr }}`를 사용한다. VPC는 RFC1918 `/8`~`/24`, subnet은 VPC에 포함된 `/24`여야 한다. 실제 값은 bootstrap 입력에만 둔다. |
| Ubuntu 24.04 | 부분 확인 | 콘솔에 Ubuntu 24.04가 노출되는 것은 확인됐다. image ID는 대상 프로젝트에서 이미지 목록을 다시 조회해 정확히 하나인 ID를 기록하기 전까지 `os_image: null`을 유지하고 apply를 중단한다. |
| data volume 2개 | 미검증 | 공개 번들은 root와 복수 blank volume 요청 형식을 보이지만, 계정 sandbox에서 서버 1대에 두 volume을 attach→재조회→detach할 때까지 구성을 확정하지 않는다. 실패하면 apply를 중단한다. 단일-volume 모드는 desired-state와 mount 계약을 별도로 구현·검증하기 전에는 사용하지 않는다. |
| 콘솔/VNC, 장애 도메인, LB health check | 부분 확인 | API 경로와 health-monitor 설정 가능성은 확인됐다. web console/VNC 실제 접속, `availability_zone`/배치 정책, LB의 실제 health-check 전환은 sandbox에서 확인 전까지 가용성 주장이나 운영 Gate 통과 근거로 쓰지 않는다. |

가비아 근거는 로컬의 [Gen2 API 계약](gabia-gen2-api-contract.md)이며, 이는 2026-08-08
로그인한 콘솔의 공개 번들과 UI를 조사한 결과다. image/flavor ID와 생성·복구 결과는 그
조사만으로 확정할 수 없다.

## 고정 버전

| 구성요소 | 고정값 | 호환 근거 |
| --- | --- | --- |
| K3s | `v1.36.3+k3s1` | 공식 K3s 최신 릴리스가 Kubernetes `v1.36.3`을 포함한다. |
| Cilium Helm chart | `1.20.0` | 공식 Cilium `1.20.0` 릴리스가 Kubernetes `v1.36`으로 갱신됐음을 명시하며, 공식 K3s 설치 문서도 이 exact chart version과 Flannel/기본 NetworkPolicy controller 비활성화를 사용한다. 따라서 위 K3s Kubernetes minor와 일치한다. |

버전은 설치 시 최신 채널을 따라가지 않고 위 exact value를 사용한다. 버전 값을 소유한
Ansible inventory와 collection requirements의 변경은 이 문서의 범위 밖이며, 해당 소유자가
`k3s_version: "v1.36.3+k3s1"`, `cilium_version: "1.20.0"`으로 반영해야 한다.

- [K3s v1.36.3+k3s1 공식 릴리스](https://github.com/k3s-io/k3s/releases/tag/v1.36.3%2Bk3s1)
- [Cilium v1.20.0 공식 릴리스](https://github.com/cilium/cilium/releases/tag/v1.20.0)
- [Cilium 1.20 K3s 설치](https://docs.cilium.io/en/stable/installation/k3s/)

## R2 acceptance Gate

R2는 S3 API endpoint `https://<account-id>.r2.cloudflarestorage.com`와 region `auto`를
제공한다. K3s는 S3 endpoint, region, bucket, folder, access key/secret key 및 lookup
type을 설정할 수 있다. 이는 설정 가능성만 뒷받침하며, 이 저장소에서는 R2 etcd snapshot과
CNPG 복구를 아직 실행하지 않았다.

테스트 전용 bucket과 분리된 writer/restore 자격증명으로 다음을 수행한다. 자격증명 값, account
ID, bucket 이름, snapshot 내용은 Git·명령 기록에 넣지 않는다.

1. K3s server 3대에 `--etcd-s3`, R2 endpoint, `--etcd-s3-region=auto`, test bucket/folder와
   `--etcd-s3-bucket-lookup-type=path`를 설정한다. snapshot 생성 뒤 R2에 객체가 생기는지
   확인하고, 별도 복구 환경에서 같은 K3s token으로 `--cluster-reset --cluster-reset-restore-path`
   복구를 실행한다. 세 member Ready와 시험 데이터의 존재를 확인한다.
2. CNPG Operator `1.30.0`과 Barman Cloud Plugin `0.14.0`을 사용해 test cluster의 base backup과 WAL archive를
   R2에 저장한다. 새 cluster의 `bootstrap.recovery`와 별도 `externalClusters` source로 PITR을
   수행한다. 복구 전용 `ObjectStore`를 만들고 `externalClusters.plugin.parameters`의
   `barmanObjectName`이 이를 참조하게 하며, source별 고유 `serverName`을 사용한다. source와
   recovery cluster는 같은 설정을 재사용하지 않고 시험 데이터 정합성을 확인한다.
3. 둘 중 하나라도 실패하면 R2를 프로덕션 backup store로 사용하지 않는다. 원인은 endpoint,
   region/lookup type, TLS, IAM permission, Barman plugin 버전으로 분리해 기록하고 중단한다.
   AWS S3도 동일한 acceptance test와 별도 승인을 통과한 뒤에만 대안으로 사용할 수 있다.

- [Cloudflare R2 S3 API compatibility](https://developers.cloudflare.com/r2/api/s3/api/)
- [K3s server S3 snapshot options](https://docs.k3s.io/cli/server)
- [CloudNativePG Barman Cloud Plugin requirements](https://cloudnative-pg.io/plugin-barman-cloud/docs/intro/)
- [CloudNativePG 1.30 recovery](https://cloudnative-pg.io/docs/1.30/recovery/)
