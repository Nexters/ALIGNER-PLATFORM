# Tailscale Operator와 Argo CD UI

## 보안 경계

Tailscale Operator OAuth 값은 Git 밖에서 `tailscale/operator-oauth` Kubernetes Secret 하나로
주입한다. 별도 Infisical Project, Machine Identity, ESO controller를 만들지 않는다.

OAuth client에는 `Devices Core`, `Auth Keys`, `Services` write scope와
`tag:aligner-k8s-operator` tag만 부여한다. Tailscale policy에서 이 tag만
`tag:aligner-k8s`와 `tag:aligner-argocd`의 owner가 된다.

## Bootstrap

1. Tailscale admin console에서 위 scope와 tag로 OAuth client를 발급한다.
2. 운영자는 `tailscale` namespace를 만든 뒤 Git 밖의 0600 env 파일에 `client_id`와
   `client_secret` 두 key를 저장한다.
3. 아래 명령으로 Secret을 주입한 뒤 로컬 파일을 안전하게 폐기한다. 값은 Git, 쉘 기록, 화면 공유,
   로그에 남기지 않는다.

   ```bash
   kubectl --context <tailscale-kubectl-context> create namespace tailscale \
     --dry-run=client -o yaml | kubectl --context <tailscale-kubectl-context> apply -f -
   kubectl --context <tailscale-kubectl-context> -n tailscale create secret generic operator-oauth \
     --from-env-file=<git-outside-0600-oauth-file> \
     --dry-run=client -o yaml | kubectl --context <tailscale-kubectl-context> apply -f -
   ```

4. Argo CD에서 `tailscale-operator`와 `tailscale-argocd-ui`가 Healthy인지 확인한다. Secret 값은
   보지 않고 이름·key와 workload 상태만 본다. Secret이 없으면 Operator/UI만 Runtime Gate로 남긴다.
5. `argocd-cmd-params-cm`의 `server.insecure: "true"` 적용을 위해 `argocd-server` 파드를 롤아웃한다.

   ```bash
   kubectl --context <tailscale-kubectl-context> -n argocd rollout restart deployment/argocd-server
   ```

## 접속과 회전

UI 주소는 MagicDNS의 `aligner-argocd` 이름이다. 두 운영자는 VPN 연결만으로 HTTPS에 접속한다.
Tailscale가 TLS를 종료하므로 Argo CD server는 내부 HTTP로 동작한다. 공인 LB, port-forward,
Tailscale SSH는 사용하지 않는다.

OAuth 회전은 새 client로 `operator-oauth`를 갱신하고 Operator/ProxyGroup health를 확인한 뒤 이전
OAuth client를 revoke한다. 실패하면 새 client를 revoke하고 이전 Secret으로 되돌린다.
