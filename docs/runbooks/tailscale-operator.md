# Tailscale Operator와 Argo CD UI

## 보안 경계

`aligner-cluster-services`는 클러스터 controller 전용 Infisical Project다.
`aligner-infra`와 `aligner-runtime`의 Machine Identity를 재사용하지 않는다. Tailscale
Operator OAuth client ID와 secret은 이 Project의 `prod` 환경 `/tailscale` path에만 저장한다.

OAuth client에는 `Devices Core`, `Auth Keys`, `Services` write scope와
`tag:aligner-k8s-operator` tag만 부여한다. Tailscale policy에서 이 tag만
`tag:aligner-k8s`와 `tag:aligner-argocd`의 owner가 된다.

## Bootstrap

1. 두 운영자는 `aligner-cluster-services` Project admin으로 등록하고 2FA를 확인한다.
2. Tailscale admin console에서 위 scope와 tag로 OAuth client를 발급해 두 값을 Infisical에 저장한다.
3. 별도 Machine Identity를 이 Project에만 Viewer로 등록한다. Universal Auth bootstrap pair는
   `tailscale` namespace의 `infisical-cluster-services-credentials` Secret에 운영자가 수동 주입한다.
   이 pair와 OAuth 값은 Git, 쉘 기록, 화면 공유, 로그에 남기지 않는다.
4. Argo CD가 `tailscale-external-secrets` → `tailscale-bootstrap` → `tailscale-operator` →
   `tailscale-argocd-ui` 순서로 Healthy인지 확인한다. Secret 값은 보지 않고 이름·key·Ready 조건만 본다.

## 접속과 회전

UI 주소는 MagicDNS의 `aligner-argocd` 이름이다. 두 운영자는 VPN 연결만으로 HTTPS에 접속한다.
Tailscale가 TLS를 종료하므로 Argo CD server는 내부 HTTP로 동작한다. 공인 LB, port-forward,
Tailscale SSH는 사용하지 않는다.

OAuth 회전은 Infisical에 새 값을 먼저 저장하고 ExternalSecret Ready와 Operator/ProxyGroup health를
확인한 뒤 이전 OAuth client를 revoke한다. 실패하면 새 client를 revoke하고 이전 값으로 되돌린다.
