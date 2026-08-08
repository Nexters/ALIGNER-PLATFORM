# 관리망 비상 접근

## 발동 조건

- WireGuard gateway 두 대 모두 접근 불가
- WireGuard 또는 host firewall 오설정으로 사설 관리 경로 잠김
- 신규 노드가 관리망 구성 전에 실패

## 1순위 — 가비아 Gen2 웹 콘솔

1. 가비아 콘솔에서 대상 VM과 이벤트 로그를 확인한다.
2. 웹 콘솔 또는 터미널 접속으로 로그인한다.
3. `systemctl status wg-quick@wg0`, `wg show`, firewall 상태를 확인한다.
4. 마지막 Ansible 변경을 기준으로 설정을 복원한다.
5. WireGuard primary/secondary 접속을 다시 확인한다.

## 2순위 — 임시 SSH `/32`

Gen2 웹 콘솔이 지원되지 않을 때만 사용한다.

1. 현재 운영자 공인 IP를 별도 네트워크에서 확인한다.
2. 가비아 보안그룹에 `k3s-03:22/TCP source=<current-ip>/32` 규칙을 추가한다.
3. SSH key로 접속하고 관리망을 복구한다. 패스워드와 root 원격 로그인은 허용하지 않는다.
4. WireGuard 접속 성공 직후 임시 규칙을 삭제한다.
5. 보안그룹에서 22/6443이 다시 차단됐는지 외부에서 확인한다.
6. 발동 원인, 변경 시각, 삭제 시각을 장애 기록에 남긴다.

임시 SSH 규칙을 상시 fallback으로 남기지 않는다.
