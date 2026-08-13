# 가비아 Gen2 API 계약 조사

이 문서는 `gabiactl` 구현에 필요한 관리 콘솔 호출을 기록한다. 인증값, 프로젝트 ID,
실제 공인 IP와 호스트 IP는 기록하지 않는다.

## 검증 수준

- **콘솔 확인**: 현재 관리 콘솔의 공개 JavaScript 번들에서 method, path, request schema를 확인했다.
- **UI 확인**: 로그인한 프로젝트 화면에서 기능과 리소스 모델을 확인했다.
- **sandbox 필요**: 별도 리소스의 create → read → 재조회 → delete 실호출로 확정해야 한다.

조사 기준은 2026-08-08이며 콘솔 번들 `index-206a0ad9.js`를 사용했다. 콘솔 배포나 가격표가
바뀌면 번들 식별자와 UI 값을 다시 확인한다.

콘솔 확인만 끝난 호출은 바로 운영 자동화에 사용하지 않는다. 응답 schema, 비동기 상태,
오류 코드와 삭제 의존성까지 sandbox에서 확인한 뒤 구현한다.

## 공통 계약

| 용도 | Base URL | 검증 |
|---|---|---|
| 인증 | `https://identity-api.gabiacloud.com/api/v1` | 콘솔 확인 |
| Compute, Network, Storage | `https://cloud-api.gabiacloud.com/api/v1` | 콘솔 확인 |
| Routing Table, NAT Gateway | `https://cloud-api.gabiacloud.com/api/v2` | 콘솔 확인 |
| Load Balancer | `https://cloud-lbaas-api.gabiacloud.com/api/v1` | 콘솔 확인 |
| Quota | `https://policy-api.gabiacloud.com/api/v1` | 콘솔 확인 |

- 로그인은 `POST /sessions`, scope 변경·갱신은 `PUT /sessions`를 사용한다.
- 성공한 세션 생성 응답에서 session ID는 `.session.id`로 확인됐다. scope 필드의 위치·갱신
  동작은 아직 status/apply의 전제조건으로 사용하지 않는다.
- 관리 API 요청은 `X-Cloud-Session` 헤더를 사용한다.
- credential과 session 값은 로그, state, 문서에 남기지 않는다.
- session 갱신 조건, 만료 시간, 401 재시도는 sandbox에서 다시 검증한다.

## 리소스 호출 매트릭스

| 리소스 | List/Create | Read/Update/Delete | 추가 동작 | 검증 |
|---|---|---|---|---|
| Server | `GET/POST /servers` | `GET/PUT/DELETE /servers/{id}` | `PUT /action`, `PUT /spec`, `PUT /password`, `GET /vnc` | 콘솔 확인 |
| Volume | `GET/POST /volumes` | `GET/PUT/DELETE /volumes/{id}` | `PUT /volumes/{id}/resize` | 콘솔 확인 |
| VPC | `GET/POST /networks` | `GET/PUT/DELETE /networks/{id}` | - | 콘솔 확인 |
| Subnet | `GET/POST /subnets` | `GET/PUT/DELETE /subnets/{id}` | `GET /subnets/{id}/fixed_ips` | 콘솔 확인 |
| Security Group | `GET/POST /securitygroups` | `GET/PUT/DELETE /securitygroups/{id}` | - | 콘솔 확인 |
| Public IP | `GET/POST /floatingips` | `DELETE /floatingips/{id}` | `GET /floatingips/resource-groups` | 콘솔 확인 |
| Routing Table | `GET/POST /routing-tables` | `GET/PUT/DELETE /routing-tables/{id}` | `PUT /associate-subnet`, `PUT /route-rules`, `GET /quota` | 콘솔 확인 |
| Load Balancer | `GET/POST /lbaas/loadbalancers` | `GET/PUT/DELETE /lbaas/loadbalancers/{id}` | `GET /status`; listener, pool, member, health monitor 별도 CRUD | 콘솔 확인 |
| Project Quota | `GET /quota/{projectId}` | - | `GET /quota/{projectId}/by-fields` | 콘솔 확인 |

Server와 Volume 연결은 `POST /servers/{serverId}/volumes/{volumeId}`, 해제는 같은 경로의
`DELETE`다. NIC 추가·삭제는 `/servers/{serverId}/nics` 하위 호출을 사용한다.

Security Group의 `PUT /securitygroups/{id}` 경로는 콘솔 번들에서만 확인했다. 요청 전체
schema, `409` 동작, 기존 규칙 보존과 rollback을 redacted sandbox 증적으로 남기기 전에는
`gabiactl` write 계약으로 사용하지 않는다. 규칙 변경은 콘솔에서 각 규칙의 방향, protocol,
port와 CIDR을 비교해 임시 관리 규칙만 제거하고 나머지가 보존됐는지 확인한다.

## Server 생성 계약

관리 콘솔의 요청 schema에서 다음 구조를 확인했다.

```yaml
name: string
description: string | null
flavor_id: string
server_type: string | null
create_count: 1
volumes:
  - source: image
    is_root: true
    source_id: image-id
    size: 50
    volume_type: volume-type
  - source: blank
    is_root: false
    size: 25
    volume_type: volume-type
nics:
  - network:
      subnet_id: subnet-id
      securitygroups: [security-group-id]
      fixedip_address: null
      floating_ip: new | floating-ip-id | null
ssh_key: ssh-key-id
host_name: optional-hostname
script_content: optional-user-script
```

상품에 따라 `goods_id`, `os_goods_id`, `os_dbms_goods_id`,
`floating_ip_goods_id`가 추가된다. 실제 값과 필수 여부는 sandbox에서 확정한다.

## Network 생성 계약

공개 번들에서 Routing Table과 Security Group의 request schema를 확인했다.

```yaml
routing_table:
  name: string
  description: optional-string
  network_id: network-id
  is_default: optional-boolean
  route_rules:
    - destination: 0.0.0.0/0
      gateway_type: IGW | IP | PGW | NGW | VGW | HBCGW | LOCAL
      gateway_id: optional-id
      nexthop: optional-ip

security_group:
  name: string
  description: string
  rules:
    - direction: string
      type: string
      protocol: tcp | udp | any | other-supported-ip-protocol
      port_min: integer
      port_max: integer
      cidr: string
      description: string
    - direction: string
      type: string
      protocol: icmp | icmpv6
      icmp_type: integer | null
      icmp_code: integer | null
      cidr: string
      description: string
```

VPC와 Subnet 생성 UI는 각각 `name`, `description`, `cidr`와
`name`, `description`, `network_id`, `cidr`를 입력받는다. Public IP 생성 UI는 연결하지
않거나 NIC를 선택할 수 있다. 이 세 요청은 번들에서 raw payload를 그대로 전달하므로 정확한
key와 상품 `goods_id` 필요 여부를 sandbox request에서 확정한다.

## UI 관찰 스냅샷 (2026-08-08, 비계약 정보)

아래 값은 조사 시점의 프로젝트 상태와 콘솔 표시값이다. `gabiactl`의 검증 기준이나 비용
계산의 고정값으로 사용하지 않으며, 실행 시 API로 조회하고 변경 작업 전에 다시 확인한다.

- 기본 VPC `192.168.0.0/16`, public Subnet `192.168.0.0/24`, Routing Table이 존재한다.
- 기본 Security Group은 SSH 22, HTTPS 443, RDP 3389를 `0.0.0.0/0`에 허용한다.
- 기본 Security Group은 사용하지 않고 ALIGNER 전용 규칙을 생성한다.
- 서버 생성 화면은 Public IP 신규 할당, 복수 NIC, 데이터 Volume, user script를 지원한다.
- 서버 API에는 생성 후 VNC 정보를 조회하는 `GET /servers/{id}/vnc`가 있다.
- 프로젝트 한도는 vCPU 48 vCore, RAM 192 GB이고 현재 사용량은 0이다. Micro 서버는
  1대로 제한된다.
- Ubuntu 22.04와 24.04 이미지가 노출되며 현재 설계 대상인 Ubuntu 24.04를 선택할 수 있다.
- Standard 2 vCPU/8 GB 사양과 root Volume 기본값 50 GB를 확인했다. 이 조합은 월
  74,250원(VAT 별도)으로 표시된다.
- Standard 2 vCPU/8 GB 서버 3대는 총량 한도 안에 들어가지만 실제 image/flavor ID와
  별도 사양 제한은 아직 미확정이다.
- 서버 생성 UI에는 가용 영역 선택 항목이 노출되지 않는다. 응답의 `availability_zone` 값과
  배치 정책은 sandbox에서 확인한다.
- 공개 번들의 서버 생성 요청은 `volumes[]`에 root image Volume과 복수의 blank data
  Volume을 담을 수 있다. UI의 데이터 Volume 개수·용량 제한은 추가 확인한다.
- 독립 블록 스토리지는 SSD 10 GB가 기본값이며 월 1,150원(VAT 별도)으로 표시된다.
  한 요청에서 최대 20개를 추가할 수 있다.
- 공인 IP는 자원에 연결하지 않은 상태로도 생성할 수 있고 월 4,000원(VAT 별도)이다.
  자원에 바로 연결하려면 외부망 연결 Routing Table을 사용하는 Subnet이어야 한다.
- Load Balancer는 Subnet에 배치되며 월 15,000원(VAT 별도)으로 표시된다. 기본 Listener는
  HTTP/80, timeout 50초, Round Robin, session persistence 미사용이다.
- Load Balancer Listener 보안 규칙은 최대 50개이며 미지정 시 모든 대역을 허용한다.
  health monitoring protocol/path와 여러 Listener를 설정할 수 있다.
- 사용자 VPC는 RFC1918 주소만 허용하고 CIDR prefix는 `/8`부터 `/24`까지 입력할 수 있다.
  프로젝트당 최대 3개이며 무료다. 테스트 입력 `10.20.0.0/16`은 UI 검증을 통과했다.
- Subnet CIDR은 `/24`로 고정되어 있고 선택한 VPC 범위 안에 있어야 한다. Subnet 자체는 무료다.
- Routing Table은 VPC에 속하고 여러 Subnet을 연결할 수 있다. 외부망 연결을 사용하면
  `0.0.0.0/0 -> 외부망 연결` 규칙이 생기며 연결된 Subnet의 인터넷 통신이 가능하다.
- Routing Table을 명시하지 않은 Subnet은 VPC 기본 Routing Table에 연결된다. 공인 IP
  자원이 있는 Subnet은 외부망이 없는 Routing Table로 변경할 수 없다.
- Security Group 생성 UI도 inbound SSH/22, HTTPS/443, RDP/3389 전체 공개와 outbound
  ALL 전체 허용을 기본으로 제시한다. 자동화 요청에서는 기본 inbound 규칙을 명시적으로
  제거하고 필요한 규칙만 보낸다.

## `gabiactl` 안전 기본값

- `gabiactl plan -f ...`와 승인 없는 `gabiactl apply -f ...`는 로컬 state와 목표를 비교해
  계획만 출력한다. `apply --approve <environment>`도 create payload·비동기 완료 계약이
  sandbox에서 확정될 때까지 write API를 호출하지 않고 중단한다.
- `gabiactl status -f ...`는 `GABIACLOUD_USERNAME`과 `GABIACLOUD_PASSWORD`를 프로세스
  환경에서 읽는다. password 환경변수가 없고 TTY가 있으면 echo를 끈 TTY 입력만 사용한다.
  session은 메모리에만 보관하며 state·출력·오류에 기록하지 않는다.
- status의 live read는 현재 sandbox로 상세 GET이 확인된 Subnet에만 한정한다. VPC,
  Server, Routing Table, Security Group, Volume, Public IP, Load Balancer는 상세 응답
  계약과 API version이 확정되기 전까지 `read-contract-gated`로 보고하고 변경하지 않는다.
- 구현 시 Load Balancer Listener 보안 규칙이 생략된 요청을 거부한다.
- 공개 Listener는 80/443과 명시적인 허용 CIDR만 사용하며 관리 포트는 허용하지 않는다.

## sandbox 캡처 체크리스트

request/response는 저장 전에 `X-Cloud-Session`, `Authorization`, Cookie, project/resource ID,
실제 공인·호스트 IP, SSH key material, user script, 사용자 식별 이름을 placeholder로 치환한다.

1. List 응답의 ID, 이름, 상태, pagination 구조
2. Create 요청 body와 응답 body
3. Create 직후부터 완료까지 상태 전이와 polling 간격
4. 동일 이름 재조회에 사용할 query parameter
5. API 오류의 HTTP status, error code, message 구조
6. 연결·해제와 삭제 순서
7. 같은 목표를 재실행했을 때 `No changes` 판정에 필요한 필드

최소 실증 순서는 VPC → Subnet → Routing Table → Security Group → Public IP → Volume →
Server → Load Balancer 생성, 역순 삭제다. 운영 리소스가 아니라 별도 sandbox 이름을 사용한다.
