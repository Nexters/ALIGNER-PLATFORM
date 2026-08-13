# 관리망 비상 접근

## 발동 조건

- Tailscale tailnet 또는 세 노드 모두 접근 불가
- Tailscale 또는 host firewall 오설정으로 관리 경로 잠김
- 신규 노드가 관리망 구성 전에 실패

## 1순위 — 가비아 Gen2 웹 콘솔

1. 가비아 콘솔에서 대상 VM과 이벤트 로그를 확인한다.
2. 웹 콘솔 또는 터미널 접속으로 로그인한다.
3. `systemctl status tailscaled`, `tailscale status`, firewall 상태를 확인한다.
4. 마지막 Ansible 변경을 기준으로 설정을 복원한다.
5. Tailscale로 k3s-01·02·03 SSH를 다시 확인한다.

## 2순위 — 웹 콘솔에서 host firewall 복원 후 임시 SSH `/32`

Gen2 웹 콘솔 또는 provider가 보장하는 out-of-band serial console에 로그인할 수 있을 때만
사용한다. 콘솔 없이 보안그룹 `/32`만 추가해도 host nftables가 public 22/TCP를 계속
차단하므로 복구 경로가 되지 않는다. out-of-band console이 없으면 임의 규칙을 추가하지
말고 가비아 지원을 통해 rescue 접근을 확보할 때까지 중단한다.

1. 현재 운영자 공인 IP를 별도 네트워크에서 확인한다.
2. 가비아 보안그룹에 `k3s-03:22/TCP source=<current-ip>/32` 규칙을 추가한다.
3. out-of-band console에서 root-only `/etc/nftables.conf.aligner-pre-firewall`이 있으면
   `nft --check --file /etc/nftables.conf.aligner-pre-firewall` 성공 후 해당 백업을
   `/etc/nftables.conf`로 복원해 `nft --file /etc/nftables.conf`를 실행한다. 최초 적용처럼
   이전 설정이 없으면 `nft list table inet aligner_firewall`로 전용 table만 확인하고
   `nft --check destroy table inet aligner_firewall` 성공 후 같은 명령에서 `--check`만
   제거해 실행한다. 다른 nftables table이나 전체 ruleset은 flush하지 않는다.
4. SSH key로 접속하고 관리망을 복구한다. 패스워드와 root 원격 로그인은 허용하지 않는다.
5. Tailscale 경유 OpenSSH 성공 직후 임시 보안그룹 규칙을 삭제한다.
6. 보안그룹 규칙의 방향·프로토콜·포트·CIDR을 전후 비교하고, 22/6443이 다시
   차단됐는지 외부에서 확인한다.
7. 발동 원인, 변경 시각, 삭제 시각을 장애 기록에 남긴다.

임시 SSH 규칙을 상시 fallback으로 남기지 않는다.

## 예행연습 완료 기준

공인 관리 포트 차단 전, Tailscale이 불가한 상황을 가정해 위 1순위 또는 2순위를
실제로 한 번 수행한다. 복구 후에는 Tailscale에서 k3s-01·02·03
SSH를 확인하고, 임시 `/32` 규칙·임시 계정이 없는 read-only 화면/조회 증적과 삭제 시각을
장애 기록에 남긴다. API 계약이 확정되기 전에는 `gabiactl access open|close`로 이 절차를
수행하지 않는다. 둘 다 fail-closed이며 cloud 변경을 만들지 않는다.
