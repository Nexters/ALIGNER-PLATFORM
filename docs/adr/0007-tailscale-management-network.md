# 0007. Tailscale 관리망

## 상태

Accepted

## 결정

운영자 2명과 k3s 서버 3대의 관리망은 Tailscale Personal을 사용한다. 서버는
`tag:aligner-prod`로 등록한다. Tailnet 정책의 `group:aligner-operators`에서 해당 태그의
22/TCP와 6443/TCP만 허용한다. 이 그룹의 구성원은 두 운영자로 유지하며, Tailscale console
관리자 권한과 서버 접근 권한을 같은 것으로 취급하지 않는다. Tailscale SSH는 끄고 기존 OpenSSH
key를 사용한다.

노드 간 K3s·etcd·CNI 트래픽은 가비아 VPC 사설 IP를 유지한다. Tailscale은 운영자
접근과 클러스터 API 관리에만 사용한다. Argo CD UI는 `tag:aligner-argocd`를 단
Tailscale HA ProxyGroup으로 노출하며, `group:aligner-operators`만 443/TCP로 접근한다.
이 경로는 공인 LB·DNS·cert-manager를 사용하지 않는다.

## 근거

- 현재 용도는 비상업 사이드 프로젝트이며 Personal 무료 플랜의 적용 범위다.
- 운영자는 VPN 프로필을 수동 전환하지 않고 MagicDNS 이름으로 각 노드에 직접 접근한다.
- 두 게이트웨이의 SNAT·peer key·프로필 배포 계약을 제거한다.

## 보안과 운영 경계

- reusable auth key는 최초 등록에만 쓰고 Git에 저장하지 않는 0600 파일로 주입한다.
- 3대 등록 후 auth key는 Tailscale 콘솔에서 revoke한다. 태그된 노드의 node key
  expiry는 자동 비활성이지만 소유자 변경·분실·침해 시 즉시 노드를 삭제한다.
- 가비아 웹 콘솔과 현재 운영자 `/32` 임시 SSH를 break-glass로 유지한다.
- 상업 용도로 변경되면 Personal 적합성을 즉시 재평가한다.
