# Security Policy

이 저장소는 Public이지만 보안을 비공개성에 의존하지 않는다. 인증, 최소 권한, 방화벽,
암호화, 키 관리로 보안을 보장한다.

## Git에 저장하지 않는 것

다음은 이 저장소에 절대 커밋되지 않는다. 발견 시 즉시 신고해 달라.

```text
- 가비아 ID·비밀번호·세션 토큰
- GitHub PAT · GitHub App Private Key
- R2 · AWS · Grafana Cloud Access Token
- Tailscale Auth Key
- WireGuard Private Key
- K3s server token
- kubeconfig client certificate · private key
- Terraform state · plan
- 실제 terraform.tfvars · backend.hcl
- 클라우드 리소스 ID가 포함된 generated inventory
```

민감값의 정본은 **Infisical Cloud**다. GitHub Actions는 OIDC로 단기 토큰을 발급받는다.

## 취약점 신고

이 저장소나 여기서 관리하는 인프라에서 보안 취약점을 발견하면 Public 이슈로 등록하지 말고
아래로 비공개 신고해 달라.

- GitHub Security Advisory: 이 저장소의 "Security" 탭 → "Report a vulnerability"

## 스캐닝

모든 push와 PR에서 [gitleaks](https://github.com/gitleaks/gitleaks)로 커밋 이력을 스캔한다
(`.github/workflows/secret-scan.yml`). GitHub Secret Scanning과 Push Protection도 활성화돼
있다.

> **Organization 저장소로 옮기는 경우**: `gitleaks-action`은 Organization 소유 저장소에서
> 무료 라이선스(`GITLEAKS_LICENSE`)를 요구한다. [gitleaks.io](https://gitleaks.io)에서
> 발급받아 저장소 Secret으로 등록한다. Personal 계정 저장소는 필요 없다.
