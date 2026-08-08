# WireGuard 관리 접근

## 최초 부트스트랩

```bash
export ALIGNER_BOOTSTRAP_CIDR=<current-ip>/32
make bootstrap-access
make bootstrap-inventory
make bootstrap-management
```

primary와 secondary 프로필로 세 노드 사설 IP 접속을 검증한 뒤 정상 inventory로 전환한다.

```bash
make inventory
make lockdown
make site
```

`lockdown` 전에 사설 inventory로 SSH와 kubectl이 되는지 반드시 확인한다.

## 정상 접속

1. 운영자 장비에서 primary 프로필을 활성화한다.
2. k3s-01·02·03 사설 IP에 SSH가 되는지 확인한다.
3. kubeconfig의 primary context로 API 상태를 확인한다.

```bash
wg-quick up aligner-primary
ssh ansible@10.0.0.11 true
kubectl --context aligner-primary get --raw=/readyz
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

1. 폐기할 peer 공개키를 inventory에서 제거한다.
2. `management_gateways`에 management network role을 재적용한다.
3. 두 gateway의 `wg show`에서 peer가 사라졌는지 확인한다.
4. 운영자 장비와 복구용 비밀 저장소의 개인키를 폐기한다.

정기 회전은 하지 않는다. 팀원 변경, 장비 분실, 키 노출 때만 새 키를 발급한다.
