# 0002. 가비아 자동화 계정의 2FA 예외

## 상태

Accepted

## 결정

`gabiactl` 전용 최소 권한 계정에는 자동화를 중단시키는 2FA를 적용하지 않는다. 사람 계정은
가비아가 계정별 2FA를 지원하면 적용한다. 사람 계정과 자동화 계정을 분리할 수 없다면 전 계정
예외를 유지하고 그 제약을 이 ADR에 기록한다.

## 근거

가비아가 API Key·Service Account·Application Credential을 제공하지 않아 자동화가 일반
계정 ID/PW 세션 인증에 의존한다(`identity-api` Basic 인증 → 2시간 세션 → `x-cloud-session`).
OTP는 이 흐름을 중단시킬 수 있다. 자동화 계정의 예외를 사람 계정까지 불필요하게 확장하지 않는다.

**이것은 보안 Best Practice가 아니라 제약을 수용한 명시적 예외다.**

## 보완 통제

```text
- 자동화 전용 최소 권한 계정 (`aligner-gabiactl`) 사용. Owner/root 자동화 금지
- 비밀번호는 Git 밖의 운영자 전용 로컬 시크릿 파일에만 저장
- Basic Authorization 헤더 · x-cloud-session 을 로그에 출력하지 않음
- 세션은 프로세스 메모리에만 보관, 만료 전 재발급
- 401 수신 시 1회만 재시도 (동시 재발급은 mutex)
- 이벤트 로그 주기 확인
- 노출·팀원 변경·프로젝트 종료 시 즉시 비밀번호 회전
```

## 재검토 조건

가비아가 서비스 계정, API Key, 자동화와 호환되는 2FA를 제공하면 이 결정을 재검토한다.
