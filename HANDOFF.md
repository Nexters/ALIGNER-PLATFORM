# ALIGNER Platform 인수인계

최종 갱신: 2026-08-12 (Asia/Seoul)

이 문서는 현재 실제 인프라 상태, 코드 완료 범위, 미실행 Gate, PR 병합 순서와 다음 실행 절차의 정본이다. 자격증명·세션·private key·실제 secret 값은 포함하지 않는다.

## PR 스택

모든 PR은 Draft이며 아래 순서대로 의존하는 stacked PR이다.

| 순서 | PR | Base | 범위 |
|---|---|---|---|
| 1 | [#36 gabiactl foundation](https://github.com/Nexters/ALIGNER-PLATFORM/pull/36) | `main` | Gabia read/status 기반, strict state, desired infrastructure 계약 |
| 2 | [#37 node bootstrap/security](https://github.com/Nexters/ALIGNER-PLATFORM/pull/37) | PR 1 branch | preflight, baseline, storage, WireGuard, firewall, K3s |
| 3 | [#38 Cilium runtime gate](https://github.com/Nexters/ALIGNER-PLATFORM/pull/38) | PR 2 branch | Cilium 설치 설정과 네트워크 acceptance Gate |
| 4 | [#39 GitOps infrastructure](https://github.com/Nexters/ALIGNER-PLATFORM/pull/39) | PR 3 branch | Gateway API, Traefik, cert-manager, CNPG/Barman, ESO, Alloy |
| 5 | [#40 data services](https://github.com/Nexters/ALIGNER-PLATFORM/pull/40) | PR 4 branch | Data-B guard, PostgreSQL, R2 backup 계약, Redis, PITR validator |
| 6 | [#41 application/production gates](https://github.com/Nexters/ALIGNER-PLATFORM/pull/41) | PR 5 branch | API render artifacts, Argo bootstrap, production/DR validators |
| 7 | [#42 project Handoff](https://github.com/Nexters/ALIGNER-PLATFORM/pull/42) | PR 6 branch | 이 문서만 포함 |

병합 시 #36을 먼저 `main`에 병합하고, #37의 base를 `main`으로 변경하여 diff와 checks를 재확인한 다음 병합한다. 같은 방식으로 #38부터 Handoff PR까지 한 개씩 base를 `main`으로 바꿔 순서대로 병합한다. 중간 branch를 먼저 삭제하지 않는다.

## [완료된 작업]

### 실제 Gabia 인프라

- 기존 소형 `aligner-sbx-ci` 서버는 변경하지 않았다.
- 운영 후보 서버 `k3s-01`, `k3s-02`, `k3s-03`을 생성했다.
  - Ubuntu 24.04
  - 각 2 vCPU / 8 GiB RAM
  - root 50 GiB, Data-A 25 GiB, Data-B 40 GiB
- `aligner-prod-vpc`를 `10.20.0.0/16`, subnet을 `10.20.0.0/24`로 구성했다.
- routing table, security group, SSH key와 노드별 볼륨/공인 IP를 생성했다.
- 임시 public SSH 허용 rule은 제거했고, public SSH 3/3 차단을 확인했다. 기존 security-group rule 10개는 유지했다.
- 로컬 state, inventory, SSH key, WireGuard profile은 `.runtime/`에 있고 Git에서 제외된다.

### 노드 부트스트랩과 관리망

- 세 노드에서 preflight, baseline, Data-A/Data-B 포맷·UUID mount를 실제 적용했다.
- 동일 play 재실행 결과는 3/3 `changed=0`, `failed=0`이었다.
- storage role은 다음 문제를 수정했다.
  - `/usr/local/libexec` 선행 생성
  - 기존 managed ext4 UUID를 정상 재사용
  - blank device에만 filesystem 생성
  - mount mode 0755/0750 oscillation 제거
  - Data-B mount 검증 뒤 marker를 `/mnt/aligner/.aligner-data-b.uuid`에 기록
- WireGuard gateway는 `k3s-01`, `k3s-02`의 `wg0`에 구성했다.
- macOS operator profile은 짧은 interface name `wgprod0`/`wgprod1`을 사용한다.
- WireGuard 경유 private SSH가 세 노드 모두 성공했다. `k3s-03`은 gateway를 통한 routed private SSH 경로를 사용한다.
- gateway에는 client private key를 전달하지 않으며, client profile은 localhost에서만 `no_log`로 생성하도록 role을 수정했다.
- nftables role은 전용 `inet aligner_firewall` table만 관리하고 다른 table과 WireGuard NAT를 보존한다. serial 적용, 사전 SSH proof, backup/rescue rollback을 구현했다.
- non-gateway는 inventory의 management gateway private IP와 정확히 일치하는 source에서만 private-interface SSH를 허용하도록 계약을 수정했다.

### 코드와 GitOps 정의

- K3s `v1.36.3+k3s1`, Cilium chart `1.20.0`을 고정했다.
- K3s role에 checksum download, embedded-etcd 3-server join, secrets encryption, R2 snapshot, audit policy, Data-B guard와 readiness 검증을 구현했다.
- Cilium Gate에 status/connectivity, DNS/Service, default-deny/allow, agent 순차 복구, 사용량 증적과 current-cluster PASS 증적을 구현했다.
- Argo CD HA bootstrap을 checksum 고정하고 field ownership 충돌 시 fail-closed하도록 구현했다.
- Gateway API v1.6.1은 release commit에 고정했다. Traefik 41.2.0, cert-manager v1.21.1, External Secrets 2.8.0, Alloy 1.11.1을 고정했다.
- Traefik은 DaemonSet, NodePort 30080/30443, `externalTrafficPolicy: Local`, Gateway API 전용으로 정의했다.
- Infisical SecretStore/ExternalSecret 계약을 추가했고 credential 값은 Git에 넣지 않았다.
- CNPG 2-instance PostgreSQL, Barman R2 ObjectStore/ScheduledBackup, local-path StorageClass, Redis `emptyDir` cache를 정의했다.
- local-path provisioner `setup`은 `/mnt/aligner/*`만 허용하고 Data-B UUID marker가 없으면 PVC 생성을 거부한다.
- API의 normal/degraded/maintenance overlay, PDB, Service, HTTPRoute, default-deny 및 최소 allow policy를 만들었다.
- production gate와 etcd recovery, PostgreSQL PITR, node failover, K3s/Cilium upgrade, full rebuild 증적 validator를 추가했다.
- 위험한 activation은 닫혀 있다.
  - `gitops/apps/kustomization.yaml`은 `resources: []`이다.
  - prod root는 controllers/configs만 포함한다.
  - data/apps child는 runtime 값과 acceptance가 준비될 때까지 제외된다.
  - Gateway/Certificate runtime overlay도 기본 kustomization에서 제외된다.

### 검증 결과

- 모든 PR 후보 238개 파일을 `.runtime` 제외 gitleaks로 검사했고 0 findings였다. 각 staged PR도 다시 0 findings였다.
- PR 1: 공식 checksum으로 받은 임시 Go 1.26.5에서 `go test ./...`, `go vet ./...` 통과.
- PR 2: site/exposure syntax, scoped `ansible-lint`, WireGuard/firewall contract tests 통과.
- PR 3: Cilium playbook syntax/lint와 test manifest kustomize 통과.
- PR 4: checksum 검증한 임시 Helm 3.19.4로 전체 controllers render 통과. configs와 runtime overlays도 render 통과.
- PR 5: 전체 data render, local-path JSON/shell 구문, PITR tests 4/4 통과.
- PR 6: API overlays/prod composition render, 6개 Make test target의 Python tests 21개, Ansible syntax/lint 통과.
- 각 PR은 별도 Sober read-only review를 거쳤다. 발견된 credential endpoint allowlist, firewall rollback, Cilium workload/chart 검증, Traefik schema, Gateway API pin, Data-B marker enforcement, Cilium evidence freshness, Argo field ownership 문제를 수정한 뒤 모두 PASS를 받았다.

## [미완료/누락된 작업]

### 즉시 처리할 보안 항목

- 대화 중 Gabia 비밀번호가 노출되었다. 다른 작업보다 먼저 Gabia 콘솔에서 해당 비밀번호를 회전해야 한다.
- 회전한 비밀번호, R2 key, K3s token, Infisical credential은 채팅·Git·shell history에 기록하지 않는다. `.runtime`의 mode 0600 파일 또는 승인된 secret manager로만 주입한다.

### Cloud와 클러스터 runtime

- Cloudflare R2 bucket/access key는 아직 생성하지 않았다. dashboard 로그인까지만 완료했다.
- Gabia external load balancer를 아직 생성하지 않았다. NodePort 30080/30443 target, `/ping` health check와 LB private IP가 필요하다.
- firewall role은 실제 노드에 적용하지 않았다. LB private IP와 WireGuard SSH proof가 없으면 기본값에서 fail-closed한다.
- K3s, embedded etcd, Cilium은 실제 서버에 아직 설치하지 않았다.
- Argo CD와 GitOps controllers/configs/data/apps는 클러스터에 적용하지 않았다.
- public domain, Cloudflare DNS, Gateway, ACME issuer, Certificate와 HTTPS routing은 미구성이다.
- Infisical project/machine identity/bootstrap Secret은 미구성이다.
- PostgreSQL backup/WAL upload, restore/PITR, primary failover는 모두 `NOT_EXECUTED`다.
- Cilium connectivity/agent recovery/VM-stop, one-node-loss, etcd recovery, upgrade, full rebuild drill도 모두 `NOT_EXECUTED`다.
- production gate PASS artifact는 없다.

### 코드상 의도적인 Gate와 제한

- `gabiactl`은 완전한 cloud write provider가 아니다.
  - 인증, 안전한 credential 입력, desired validation, strict/atomic state, inventory, verified read/status는 구현됐다.
  - `apply`, `destroy`, `access`의 live write는 API contract가 완전히 검증되지 않아 의도적으로 mutation 없이 거부한다.
  - 이번 실제 인프라는 검증된 API 호출을 제한적으로 사용해 만들었다.
  - 향후 authoritative tool로 사용하려면 create/update/delete payload, async operation polling, ownership/drift, partial-resume, LB와 SG contract를 sandbox에서 캡처해 테스트해야 한다.
- API image는 `registry.invalid/...@sha256:000...`, hostname은 `.invalid`, probes/resources/HTTPS egress는 미확정이다. app overlay를 활성화하면 안 된다.
- PostgreSQL ObjectStore의 R2 account endpoint와 runtime Secret은 placeholder다. data child를 활성화하면 안 된다.
- certificate/gateway runtime manifests의 이메일·hostname은 placeholder이고 parent에서 제외돼 있다.
- `make lint` 전체는 로컬 `yamllint`와 `shellcheck` 부재로 완주하지 못했다. scoped `ansible-lint`, syntax와 개별 tests는 통과했다.
- Go와 Helm은 시스템에 상시 설치하지 않고 checksum 검증한 임시 toolchain으로 테스트했다.
- 요청한 subagent model은 Terra/medium으로 지정했지만 agent runtime에서 실제 pin을 독립 조회하는 인터페이스가 없어 적용 여부를 검증하지 못했다. 격상 재시도는 없었다.

## [향후 작업 계획 (Next Steps)]

### 1. PR 병합과 credential 회전

1. Gabia 노출 비밀번호를 즉시 회전한다.
2. #36부터 PR 스택 순서대로 리뷰한다.
3. 각 선행 PR 병합 후 다음 PR base를 `main`으로 바꾸고 diff/checks가 해당 기능만 남는지 확인한다.
4. #41과 Handoff PR까지 병합하기 전에는 Argo root를 apply하지 않는다. GitOps Application은 `targetRevision: main`을 본다.

### 2. 로컬 접근과 현재 노드 상태 재확인

```bash
sudo wg show
sudo wg-quick up "$PWD/.runtime/wireguard/wgprod0.conf"  # 아직 up이 아닐 때만
ANSIBLE_CONFIG=ansible/ansible.cfg \
  ANSIBLE_COLLECTIONS_PATH="$PWD/.ansible/collections" \
  ansible -i .runtime/inventory.yaml all -m ping
```

작업 종료 시 필요하면 `sudo wg-quick down "$PWD/.runtime/wireguard/wgprod0.conf"`을 사용한다. inventory/key/profile을 출력하거나 commit하지 않는다.

### 3. R2와 Gabia LB 준비

1. Cloudflare R2에 운영 bucket을 생성한다.
2. K3s etcd snapshot writer와 CNPG Barman writer/restore 정책을 분리한다. CNPG writer는 DeleteObject를 거부한다.
3. account endpoint, bucket, access key/secret을 runtime secret 파일에 mode 0600으로 저장한다.
4. Gabia LB를 세 노드의 30080/30443 NodePort target으로 생성하고 `/ping` health check를 설정한다.
5. LB private IP를 runtime inventory의 `firewall_gabia_lb_private_ip`에 넣는다.

### 4. firewall, K3s, Cilium 설치

1. 새 operator shell에서 WireGuard SSH 3/3을 다시 증명한다.
2. firewall approval/proof와 gateway private IP exact set, LB private IP를 runtime vars에 넣는다.
3. serial 1로 firewall을 적용하고 각 노드 직후 새 SSH 세션을 확인한다. 실패 시 다음 노드로 진행하지 않는다.
4. 강한 K3s token을 생성해 runtime으로만 주입하고 R2 etcd vars와 `k3s_runtime_approved=true`를 설정한다.
5. `ansible/playbooks/site.yml`의 순서대로 첫 server, Cilium, 나머지 두 server를 설치한다. Argo bootstrap approval은 이 단계에서는 false로 유지할 수 있다.
6. `kubectl get nodes`, etcd 3-member health, encryption hash와 Cilium Ready를 확인한다.
7. 별도 승인으로 `make verify-cilium`을 실행하고 fresh PASS evidence를 만든다.

### 5. Argo와 안전한 GitOps 단계 활성화

1. PR 스택이 모두 `main`에 병합됐는지 확인한다.
2. Argo bootstrap checksum, kubeconfig와 runtime approval을 검토한 뒤 controllers/configs만 sync한다.
3. controller CRD/Deployment Ready와 Traefik NodePort `/ping`을 확인한다.
4. Infisical runtime project/identity와 namespace bootstrap Secret을 out-of-band로 만든다.
5. R2 endpoint/Secret, Data-B marker 3/3, CNPG/Barman controller Ready를 확인한다.
6. `gitops/clusters/prod/kustomization.yaml`에 `data.yaml`을 추가하는 별도 PR을 만든다.
7. PostgreSQL Ready, `aligner-postgresql-rw`, Redis Service, WAL archive와 weekly base backup을 검증한다.

### 6. DNS/TLS와 애플리케이션 활성화

1. 실제 API domain과 DNS/LB 주소를 확정한다.
2. Gateway/Certificate runtime overlay의 `.invalid` hostname과 ACME email을 교체하는 별도 PR을 만든다.
3. staging certificate 후 production certificate를 발급하고 HTTP redirect, TLS, host/path negative test를 수행한다.
4. API immutable image digest, 실제 health endpoint와 startup/readiness/liveness probe, 측정한 requests/limits, 승인된 external HTTPS egress를 확정한다.
5. normal overlay를 `gitops/apps/kustomization.yaml`에 추가하고, 이후 prod root에 `apps.yaml`을 추가하는 별도 PR을 만든다.

### 7. 운영 acceptance와 종료 조건

1. PostgreSQL WAL/base backup, delete denial, 별도 cluster PITR을 실행하고 evidence를 `PASS`로 갱신한다.
2. node loss, etcd recovery, Cilium agent/VM recovery, upgrade와 full rebuild drill을 승인된 maintenance window에서 실행한다.
3. external LB one-node-loss와 HTTPS 지속성을 검증한다.
4. `make verify`가 fresh Cilium evidence, 3-node etcd, workloads, Gateway/TLS/LB evidence, one-node-loss capacity를 모두 PASS하는지 확인한다.
5. `.runtime/production-gate/<UTC>.json`과 각 runbook evidence를 검토한 뒤에만 production ready로 선언한다.

## 로컬 파일 보호

- 절대 commit 금지: `.runtime/`, `.ansible/`, private inventory, kubeconfig, SSH/WireGuard key와 외부 서비스 자격정보.
- `.serena/`는 이번 PR 스택에서 제외한 로컬 tool metadata다.
- `.runtime`을 삭제하면 현재 인프라 state와 접근 자료 복구가 어려우므로 백업 정책 없이 정리하지 않는다.
