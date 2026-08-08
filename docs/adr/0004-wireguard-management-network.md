# 0004. WireGuard 관리망

## 상태

Accepted

## 결정

k3s-01과 k3s-02를 WireGuard gateway로 사용한다. 운영자 노트북에는 primary와 secondary 프로필을 두고 장애 시 수동 전환한다.

공인망에서는 22/TCP와 6443/TCP를 차단하고 두 gateway의 51820/UDP만 허용한다. Tailscale과 Headscale은 후보에서 제외한다.

## 근거

- 운영자는 유동 IP 환경에서 접속하므로 `/32` 화이트리스트를 일상 운영 경로로 사용할 수 없다.
- 유효한 키를 가진 peer만 VPC 관리 포트에 접근한다.
- gateway 두 대의 동일한 Ansible 구성과 수동 전환은 자동 HA보다 작고 복구하기 쉽다.

## 운영 경계

- peer 공개키는 Git, 개인키는 운영자 장비와 복구용 비밀 저장소에 둔다.
- 정기 회전은 하지 않고 팀원 변경·분실·노출 시 회전한다.
- 가비아 Gen2 웹 콘솔을 우선 break-glass로 검증한다. 미지원이면 현재 관리자 `/32`에 k3s-03 SSH를 일시 허용한다.
