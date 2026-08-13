# External Secrets 운영

## 사전 승인 및 bootstrap

1. Infisical에서 사람 계정 2FA, `aligner-runtime` project 소유권, `/apps/aligner-api` 읽기 전용
   Machine Identity를 승인자가 확인한다. `aligner-infra` project에는 권한을 주지 않는다.
2. 승인된 운영자가 `aligner` namespace에만 `infisical-runtime-credentials`를 생성한다. 이
   Secret은 Git·터미널 기록·스크린샷에 남기지 않으며 `clientId`, `clientSecret` 두 key를 가진다.
3. Argo CD sync 후 `ExternalSecret/aligner-api-runtime` Ready와 target Secret의 **이름과 key
   목록만** 확인한다. 값 출력(`kubectl get secret -o yaml`, `describe`)은 금지한다.

`external-secrets` Argo CD Application이 `CreateNamespace=true`와
`managedNamespaceMetadata`로 `aligner` namespace를 단독 생성·관리한다. 생성 시
restricted Pod Security Admission label을 적용하므로 namespaced ESO controller와
`aligner-api-runtime` SecretStore/ExternalSecret은 namespace가 준비된 뒤 sync된다.

## 권한 검증

runtime identity가 `/apps/aligner-api` 경로의 세 key를 읽고 ESO sync가 Ready인지 확인한다.
같은 `aligner` namespace에서 `aligner-infra` path를 `remoteRef.key`로 참조하는 일회성
`ExternalSecret`은 Infisical에서 거부되고 Ready가 `False`여야 한다. 별도 namespace의
`ExternalSecret`도 `infisical-runtime` SecretStore를 참조할 수 없어 Ready가 `False`여야 한다.
테스트 객체와 target Secret을 즉시 삭제하고 Argo CD source에는 추가하지 않는다. identity의 허용
경로를 넓혀 통과시키지 않는다.

## 회전과 폐기

1. Infisical에서 새 Universal Auth client secret을 발급하고 기존 credential을 즉시 폐기하지 않는다.
2. 승인된 운영자가 클러스터의 bootstrap Secret만 갱신하고 ESO sync와 앱 health를 확인한다.
3. 성공 후 이전 credential을 Infisical에서 폐기하고 재동기화·앱 health를 다시 확인한다.
4. 실패하면 새 credential을 폐기하고 이전 credential으로 되돌린 뒤 원인을 기록한다.

## 로그·diff 노출 대응

ESO/Argo CD 로그와 diff는 Secret의 이름, key, 상태만 확인한다. 값 또는 credential이 보이면
출력을 공유·저장하지 말고 접근 가능한 로그 보존본을 최소 권한으로 격리한다. 노출된 credential을
Infisical에서 즉시 폐기·재발급하고, 영향 범위와 회전 시각을 보안 사고 기록에 남긴다.

CI는 `trufflehog git file://. --no-verification`으로 Git 변경을 검사한다. Argo CD diff에서
Secret 데이터가 보이면 diff masking/redaction 설정을 적용하기 전 sync를 진행하지 않는다.
