# Kubernetes 애플리케이션 Secret 운영

## 정본과 생성

운영 값의 정본은 `ALIGNER-SERVER` 루트의 Git 제외 `application-secret.properties`다. 키 목록은
두 저장소에서 같아야 하며 값·Secret manifest는 Git, PR, CI 로그에 남기지 않는다.

```bash
scripts/bootstrap-aligner-api-secret.sh \
  <tailscale-kubectl-context> \
  ../ALIGNER-SERVER/application-secret.properties
```

스크립트는 값이 아닌 key 일치만 검사하고 `aligner/aligner-api-secrets`를 생성하거나 갱신한다.
Deployment가 이미 존재하면 새 값을 읽도록 rollout을 재시작하고 5분 안에 Ready인지 확인한다.
실행 전에 Tailscale 경유 context와 K3s Secret encryption을 확인한다.

## Runtime Gate

다음을 모두 충족하기 전에는 `gitops/apps/kustomization.yaml`에 앱을 추가하지 않는다.

1. `aligner-api-secrets`의 key가 `runtime-secret.keys`와 정확히 일치한다.
2. Server CI가 만든 실제 `ghcr.io/nexters/aligner-server@sha256:...` digest가 반영됐다.
3. private GHCR를 사용하면 별도 pull credential을 Git 밖에서 준비했다.
4. Argo CD 동기화 뒤 Pod가 Secret 값을 출력하지 않고 기동한다.

Secret을 바꾸면 기존 Pod 환경변수는 자동으로 바뀌지 않는다. 승인된 운영자가 Deployment를
rolling restart하고 새 Pod의 readiness와 오류율을 확인한다. 정적 검사나 렌더 성공은 runtime
proof가 아니다.
