# 0002. 가비아 계정은 2FA를 사용하지 않는다

## 상태

Accepted

## 결정

가비아 계정(사람·자동화 모두)에는 2FA를 적용하지 않는다. Infisical 사람 계정에는 2FA를
적용한다. 두 결정은 별개다.

## 근거

가비아가 API Key·Service Account·Application Credential을 제공하지 않아 자동화가 일반
계정 ID/PW 세션 인증에 의존한다(`identity-api` Basic 인증 → 2시간 세션 → `x-cloud-session`).
OTP는 이 흐름을 중단시킬 수 있고, 운영자 2명·9개월 규모에서 계정별 예외와 복구 절차를
관리하는 비용이 이득을 넘는다.

**이것은 보안 Best Practice가 아니라 제약을 수용한 명시적 예외다.**

## 보완 통제

```text
- 자동화 전용 최소 권한 계정 (aligner-terraform) 사용. Owner/root 자동화 금지
- 비밀번호는 Infisical aligner-infra Project 에만 저장
- Basic Authorization 헤더 · x-cloud-session 을 로그에 출력하지 않음
- 세션은 프로세스 메모리에만 보관, 만료 전 재발급
- 401 수신 시 1회만 재시도 (동시 재발급은 mutex)
- 이벤트 로그 주기 확인
- 노출·팀원 변경·프로젝트 종료 시 즉시 비밀번호 회전
```

## 재검토 조건

가비아가 서비스 계정 또는 API Key를 공식 제공하면 이 결정을 재검토한다(문의 D5).
