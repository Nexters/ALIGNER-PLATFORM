# WireGuard 관리 접근

## 최초 부트스트랩

```bash
export ALIGNER_BOOTSTRAP_CIDR=<current-ip>/32
export WG_K3S_01_PRIVATE_KEY=<gateway-private-key>
export WG_K3S_02_PRIVATE_KEY=<gateway-private-key>
make bootstrap-access
make bootstrap-inventory
ansible-playbook -i .runtime/bootstrap-inventory.yaml ansible/playbooks/management-access.yml \
  -e wireguard_runtime_approved=true \
  -e wireguard_client_profiles_dir=<secure-local-directory> \
  -e @<untracked-wireguard-peers.yml>
```

`<untracked-wireguard-peers.yml>`에는 gateway의 public key, `primary`/`secondary`
profile name, `wireguard_peers`의 peer public key와 gateway별 `/32`만 넣는다. 같은 name의
`wireguard_client_profiles`에는 client private key, gateway별 `/32`, 그리고 gateway별로 고유한
15자 이하 `interface_names`를 별도로 넣는다. client
private key는 localhost profile-render task에서만 사용하고 gateway config에는 public key와
allowed IP만 쓴다. role은
키, profile 출력 경로, 두 gateway와 모든 tunnel IP의 고유성을 변경 전에 확인한다. private key와
생성된 `<interface_name>.conf`는 Git과 CI 로그에 넣지 않는다.

primary와 secondary 프로필로 **서로 다른 외부 네트워크에서** 세 노드 사설 IP 접속을 검증한 뒤 정상 inventory로 전환한다.

## Host firewall approval gate

방화벽은 `management_network` 직후 serial 1로 실행된다. 각 노드에서 새 WireGuard 경로의
SSH `true`를 확인한 뒤 해당 노드의 runtime vars에
`firewall_runtime_approved=true`, `firewall_wireguard_access_proven=true`와 같은 read-only
SSH command를 넣는다. K3s API는 다음 #22 단계에서 생기므로 기본 gate에는 넣지 않는다.
이미 API가 있는 재적용이라면 `firewall_wireguard_api_check_command`에 `kubectl ...
get --raw=/livez` 같은 read-only command를 넣어 pre/post에 함께 검사한다. 하나라도 없거나
facts의 public/private/WG 주소가 inventory와 다르면 firewall role은 패키지·파일·규칙을 변경하지
않고 실패한다.

`k3s-01`·`k3s-02` gateway는 실제 `wg0` 주소와 `firewall_wireguard_cidrs`를 검증한 뒤
`wg0`에서 SSH/API를 직접 허용한다. `k3s-03`에는 `wg0`가 없으므로 이를 요구하지 않는다.
대신 runtime vars의 `firewall_management_gateway_private_ips`가 inventory의
`management_gateways` 두 호스트 `private_ip`와 정확히 일치해야 하며, private interface의
TCP 22는 그 두 SNAT source에서만 허용한다. 이 목록을 subnet/CIDR로 넓히지 않는다.
K3s 내부 API(6443) 허용은 기존 VPC control-plane 규칙을 따른다.

적용 중 post-check가 실패하면 해당 노드의 기존 nftables 설정을 복원하고 serial play가
중단된다. 재부팅 뒤에는 WireGuard SSH, K3s 설치 뒤 WG API, `sudo nft list table inet
aligner_firewall`을 확인한 뒤 다음 노드의 approval을 준다.

```bash
make inventory
make lockdown
make site
```

`lockdown` 전에 사설 inventory로 SSH와 kubectl이 되는지 반드시 확인한다.

## #17 관리 포트 차단 검증

이 절차는 **검증만** 한다. `gabiactl access close`는 아직 가비아 write API 계약이
확정되지 않아 fail-closed이며, 보안그룹·방화벽·계정·VM에는 아무 변경도 하지 않는다.
실제 차단은 API 계약 및 변경 승인을 받은 별도 작업에서만 수행한다.

실행할 때마다 untracked 파일에 실행 시각과 증적 위치를 넣는다. playbook은 임의 명령을
실행하지 않으며, SSH/public 검사는 TCP 연결만, K3s 검사는 HTTPS GET만 수행한다. 인증값,
private key, token, kubeconfig 내용 또는 `-v`/debug 옵션을 vars에 넣지 않는다.

```yaml
# <untracked-management-exposure.yml>
management_exposure_runtime_approved: true
management_exposure_stage: pre-lockdown
management_exposure_evidence_ref: INC-1234/wg-and-break-glass-rehearsal
management_exposure_cleanup_evidence_ref: INC-1234/temporary-rule-and-account-removed
management_exposure_desired_rules_verified: true # 별도 승인된 read-only 증적 참조
management_exposure_wg_ssh_checks:
  - {name: primary-k3s-01, host: "<wg-private-ip>"}
  - {name: primary-k3s-02, host: "<wg-private-ip>"}
  - {name: primary-k3s-03, host: "<wg-private-ip>"}
  - {name: secondary-k3s-01, host: "<wg-private-ip>"}
  - {name: secondary-k3s-02, host: "<wg-private-ip>"}
  - {name: secondary-k3s-03, host: "<wg-private-ip>"}
management_exposure_break_glass_evidence_ref: INC-1234/rehearsal-complete
```

`post-lockdown-pre-k3s`에는 public check를 `{name: public-tcp-22, host: "<public-ip>",
port: 22}` 형식으로 4개(22, 6443, 5432, 6379) 넣는다. `post-k3s` API check는
`{name: primary-k3s-01, url: "https://<wg-api-endpoint>/readyz"}` 형식으로 6개를 넣는다.

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg \
ansible-playbook ansible/playbooks/verify-management-exposure.yml \
  -e @<untracked-management-exposure.yml>
```

단계별 gate는 다음과 같다.

1. `pre-lockdown`: 두 WireGuard 프로필에서 3개 노드 SSH(6개), 보안그룹/노드 방화벽의
   목표 규칙, break-glass 예행연습 및 임시 규칙·계정 삭제 증적을 확인한다. K3s API
   positive check는 요구하지 않는다.
2. 승인된 실제 차단 후 `post-lockdown-pre-k3s`: 같은 SSH 6개와 공인 TCP
   22/6443/5432/6379 negative check 4개를 확인한다. #22 전에는 6443 positive check를
   하지 않는다.
3. #22 K3s 설치 후 `post-k3s`: 위 public negative 및 SSH 검사를 다시 하고, 두 프로필
   × 세 노드의 `/readyz` 또는 `/livez` API positive check 6개를 추가한다.

모든 stage는 evidence ref 또는 필수 check가 없으면 명령을 하나도 실행하지 않고 실패한다.

## 정상 접속

1. 운영자 장비에서 primary 프로필을 활성화한다.
2. k3s-01·02·03 사설 IP에 SSH가 되는지 확인한다.
3. kubeconfig의 primary context로 API 상태를 확인한다.

```bash
wg-quick up aligner-primary
ssh ansible@10.20.0.11 true
kubectl --context aligner-primary get --raw=/readyz
```

각 gateway에서 재부팅 자동 시작과 peer 상태도 확인한다.

```bash
sudo systemctl is-enabled wg-quick@wg0
sudo wg show wg0
```

## Gateway 전환

primary gateway가 응답하지 않으면 프로필을 겹쳐 켜지 않고 secondary로 전환한다.

```bash
wg-quick down aligner-primary
wg-quick up aligner-secondary
kubectl --context aligner-secondary get --raw=/readyz
```

서비스가 정상이라면 gateway 장애는 사용자 장애로 취급하지 않는다. 장애 노드를 복구한 뒤 primary 프로필을 다시 검증한다.

## Peer 폐기

1. gateway의 `wireguard_peers`에서는 폐기할 공개키와 두 gateway의 `/32`만 제거하고, client private key는 별도 `wireguard_client_profiles`와 비밀 저장소에서 폐기한다.
2. `wireguard_runtime_approved=true`로 `management-access.yml`을 두 gateway에 재적용한다.
3. 두 gateway의 `sudo wg show wg0`에서 공개키가 사라졌는지, 폐기한 프로필로 VPC SSH/6443 접속이 실패하는지 확인한다.
4. 운영자 장비, 생성된 profile 파일과 복구용 비밀 저장소의 개인키를 폐기한다.

정기 회전은 하지 않는다. 팀원 변경, 장비 분실, 키 노출 때만 새 키를 발급한다.
