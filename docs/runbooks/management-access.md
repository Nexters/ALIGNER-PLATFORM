# Tailscale 관리 접근

## Tailnet 정책

Tailscale 콘솔 JSON editor의 정본은 [tailscale-policy.hujson](tailscale-policy.hujson)이다.
`group:aligner-operators`에는 현재 두 운영자만 넣고, 이 그룹만 `tag:aligner-prod`를
소유하거나 해당 서버의 OpenSSH 22/TCP와 K3s API 6443/TCP에 접근할 수 있다. Tailnet
admin 권한은 이 서버 접근 권한을 대신하지 않는다. Tailscale SSH는 사용하지 않는다.

## 최초 부트스트랩

1. reusable·tagged·non-ephemeral auth key를 생성하고 Git 밖 0600 파일로 저장한다.
2. 현재 운영자 `/32` SSH로 각 노드에 접근할 수 있는 public bootstrap inventory를 준비한다.
3. 다음을 실행한다.

```bash
chmod 600 .runtime/tailscale/bootstrap.authkey
ANSIBLE_CONFIG=ansible/ansible.cfg ansible-playbook \
  -i .runtime/bootstrap-inventory.yaml \
  ansible/playbooks/management-access.yml \
  -e management_network_tailscale_runtime_approved=true \
  -e management_network_tailscale_auth_key_file="$PWD/.runtime/tailscale/bootstrap.authkey"
```

임시 공인 `/32` 경로를 유지한 채 `make bootstrap-firewall`로 세 노드를 `serial: 1` 적용한다.
각 노드에서 Tailscale 신원 확인, MagicDNS 경유 OpenSSH 확인, Tailscale 허용 방화벽 적용과
재확인이 끝난 뒤 다음 노드로 이동한다.

```bash
export ALIGNER_TAILSCALE_AUTH_KEY_FILE="$PWD/.runtime/tailscale/bootstrap.authkey"
export ALIGNER_GABIA_LB_PRIVATE_IP="<lb-private-ip>"
make bootstrap-firewall
```

role은 인증된 MagicDNS Ansible OpenSSH 연결, Tailscale 허용 방화벽 증거, `Running`, hostname,
`tag:aligner-prod`를 모두 확인한 후에만 방화벽을 적용한다. 서버 등록이 끝나면 Tailscale
콘솔에서 bootstrap auth key를 revoke한다.
등록이 일부 노드에서 실패해도 원격 임시 key 파일은 role의 `always` 단계에서 제거된다.
실패한 bootstrap auth key도 즉시 revoke하고 새 key로만 재시도한다.

## 접근 검증

```bash
tailscale ping k3s-01
tailscale ping k3s-02
tailscale ping k3s-03
ssh ubuntu@k3s-01 true
ssh ubuntu@k3s-02 true
ssh ubuntu@k3s-03 true
kubectl --server=https://k3s-01:6443 get --raw=/readyz
```

## Tailscale kubeconfig 연결

로컬 context가 없으면 Tailscale VPN을 켜고 MagicDNS가 동작하는 상태에서 한 server의 K3s
kubeconfig를 Git 밖 `.runtime`에 저장한다. 명령의 표준 출력이나 PR에 파일 내용을 붙이지 않는다.

```bash
install -m 700 -d .runtime
umask 077
ssh ubuntu@k3s-01 'sudo cat /etc/rancher/k3s/k3s.yaml' > .runtime/kubeconfig
kubectl --kubeconfig .runtime/kubeconfig config set-cluster default --server=https://k3s-01:6443
export KUBECONFIG="$PWD/.runtime/kubeconfig"
kubectl get --raw=/readyz
```

연결 뒤에만 nodes, etcd, Cilium, Argo CD, Traefik, cert-manager, CNPG, B2 설정을 read-only로
확인한다. kubeconfig가 없거나 API가 응답하지 않으면 runtime 상태를 증명했다고 기록하지 않는다.

`make site`는 승인값과 K3s/B2 시크릿을 담은 Git 밖의 0600 runtime vars 파일을
`ALIGNER_RUNTIME_VARS_FILE`로 요구한다. `make site`, `make verify`, `make verify-cilium`은 private topology inventory 뒤에
`ansible/inventories/tailscale/hosts.yml`을 합성해 `ansible_host`만 MagicDNS 이름으로
덮어쓴다. 방화벽 적용은 각 노드에서 Tailscale 신원과 SSH를 다시 확인한 후
`firewall_runtime_approved=true`, `firewall_tailscale_access_proven=true`로 serial 1 실행한다.

## 노드·사용자 폐기

- 서버 재설치: 기존 machine을 콘솔에서 삭제하고 새 일회용 auth key로 다시 등록한다.
- 운영자 탈퇴·장비 분실: Users/Machines에서 해당 사용자와 device를 제거한다.
- Tailscale 장애: [break-glass](break-glass.md)의 가비아 웹 콘솔또는 임시 `/32` SSH를 사용한다.

## 공인망 차단 Gate

`verify-management-exposure.yml`에 노드별 MagicDNS OpenSSH 3개, 공인 22/6443/5432/6379
negative check 4개, K3s 설치 후 API check 3개를 Git 밖 vars로 제공한다.
실행 시각·break-glass 연습·임시 규칙 삭제 증적이 없으면 fail-closed한다.
