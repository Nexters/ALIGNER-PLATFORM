# Kubernetes 애플리케이션 Secret 운영

## 정본과 생성

운영 값의 정본은 GitHub Secrets (`PROD_ENV_FILE` / `DEV_ENV_FILE`) 및 로컬 `.runtime/secrets.*.env`다.
키 목록은 `runtime-secret.keys` 계약과 일치해야 하며, 실제 값·Secret manifest는 Git, PR, CI 로그에 남기지 않는다.

```bash
# 운영 환경 시크릿 주입
scripts/bootstrap-aligner-api-secret.sh -s .runtime/secrets.prod.env -k .runtime/kubeconfig -n aligner

# 개발/샌드박스 환경 시크릿 주입
scripts/bootstrap-aligner-api-secret.sh -s .runtime/secrets.sandbox.env -k .runtime/kubeconfig -n aligner-sandbox
```

스크립트는 값이 아닌 key 일치만 검사하고 대상 네임스페이스의 `Secret: aligner-api-secrets`를 생성하거나 갱신한다.
Deployment가 이미 존재하면 새 값을 읽도록 rollout을 재시작하고 Ready 상태를 확인한다.

## Runtime Gate

1. `aligner-api-secrets`의 key가 `runtime-secret.keys`의 9개 필수 키와 정확히 일치한다.
2. Server CI가 만든 실제 `ghcr.io/nexters/aligner-server` 이미지가 정상 배포된다.
3. Argo CD 동기화 뒤 Pod가 Secret 값을 로그에 출력하지 않고 안전하게 기동한다.
