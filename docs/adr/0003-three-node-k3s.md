# 0003. 통합형 3노드 K3s

## 상태

Accepted

## 결정

동일한 `2 vCPU / 8 GB` VM 세 대를 K3s server와 worker로 함께 사용하고 embedded etcd 3멤버를 구성한다.

## 근거

- 실사용자 운영 중 VM 한 대 장애와 순차 재부팅을 자동 생존한다.
- control plane 전용 노드를 추가하지 않고 크레딧을 앱과 데이터베이스 자원에 사용한다.
- K3s는 upstream Kubernetes API를 유지하면서 부트스트랩과 control plane 운영 부담을 줄인다.

## 한계

- 가비아가 물리 장애 도메인 분산을 보장하지 않으면 데이터센터 장애를 견디는 HA가 아니다.
- 한 노드 장애 후 필수 request가 두 노드 allocatable의 85% 이하여야 한다.
- 계산만으로 완료하지 않고 실제 VM 강제 정지 시험을 통과해야 한다.

## 대안

- 단일 노드 K3s: 가장 단순하지만 노드 장애와 재부팅 중 전체 중단을 허용해야 한다.
- control plane/worker 분리: 같은 예산에서 앱 가용 자원을 줄여 채택하지 않는다.
