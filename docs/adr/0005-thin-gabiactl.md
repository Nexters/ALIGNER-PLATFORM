# 0005. 얇은 gabiactl과 Terraform Provider 제외

## 상태

Accepted

## 결정

L1은 Go 단일 바이너리 `gabiactl`로 구축한다. Network, Subnet, Router, Security Group, Server, Volume, Public IP, Load Balancer의 초기 생성·조회·inventory·삭제만 지원한다.

```text
gabiactl validate  -f desired-infrastructure.yaml
gabiactl apply     -f desired-infrastructure.yaml
gabiactl status    -f desired-infrastructure.yaml
gabiactl inventory -f desired-infrastructure.yaml -o .runtime/inventory.yaml
gabiactl destroy   -f desired-infrastructure.yaml --confirm <environment>
gabiactl access open  -f desired-infrastructure.yaml --cidr <current-ip>/32 --targets k3s-01,k3s-02
gabiactl access close -f desired-infrastructure.yaml --targets k3s-01,k3s-02
```

## 필수 동작

- 안정적인 이름으로 원격 상태를 먼저 조회하고 없는 리소스만 생성한다.
- 401은 세션 재발급 후 한 번만 재시도하고 동시 재발급은 하나로 합친다.
- POST 실패 후 원격 상태를 재조회해 중복 생성을 막는다.
- 비동기 작업의 완료·실패 상태와 polling 간격은 sandbox에서 리소스별로 검증한 뒤 확정하며,
  검증 전에는 운영 자동화에 구현하지 않는다.
- credential과 session header를 로그에 출력하지 않는다.
- 생성 ID는 `.runtime/gabiactl-state.json`, Ansible 입력은 `.runtime/inventory.yaml`에 기록한다.
- `inventory --connect-via public|private`로 최초 WireGuard 부트스트랩과 정상 운영 경로를 구분한다.
- `access open/close`는 WireGuard 최초 설치와 break-glass의 임시 `/32` SSH 규칙만 관리한다.
- `destroy`는 요약과 환경명 확인 후 의존성 역순으로 실행한다.

## 범위 밖

- Terraform Provider와 Terraform state
- 범용 가비아 SDK
- import, update/replace planner, 완전한 drift reconciliation
- 문서화되지 않은 endpoint의 추측 구현

## 근거

초기 구축과 재구축을 자동화하면서도 9개월·단일 클러스터보다 큰 Provider 제품을 만들지 않는다. L1 결과를 inventory 하나로 L2와 연결해 도구 결합을 제한한다.

실제 endpoint와 검증 상태는 [가비아 Gen2 API 계약 조사](../architecture/gabia-gen2-api-contract.md)를 따른다.
