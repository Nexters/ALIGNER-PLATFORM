# Grafana Cloud 관측 Gate

## 적용 전 Runtime Gate

`gitops/infrastructure/controllers/alloy`는 chart `1.11.1` / Alloy `1.18.1`
DaemonSet을 배포하지만, 기본 설정은 원격 전송·discovery·scrape를 하지 않는다. 다음 증적을
운영 기록에 남기기 전에는 `runtime-config.alloy.example`을 적용하거나 Grafana Cloud를 변경하지
않는다.

1. Grafana Cloud metrics/logs endpoint와 각 username, API key를 담은 Git 밖 K8s Secret 이름을 확인한다.
   Secret 값, endpoint tenant ID, API key는 Git·터미널 출력·라벨에 기록하지 않는다.
2. node, Kubernetes, embedded etcd, Cilium, CNPG, API/JVM 각각에 대해 실제 scrape URL, 인증,
   metric family, 필요한 label과 단위를 `metric-contract` 운영 기록에 캡처한다. endpoint 또는
   metric family가 없으면 해당 수집과 경보는 **disabled** 상태로 남긴다.
3. API는 합의된 HTTP error/latency metric 및 route cardinality 정책, JVM은 필요한 heap/GC family를
   확인한다. Spring endpoint나 Prometheus metric 이름을 추정하지 않는다.
4. Cilium은 agent metrics와 현재 활성화한 DNS/drop/policy 범위만 확인한다. Hubble Relay/UI/flow
   수집은 이 Gate 범위 밖이다.
5. CNPG WAL archive·base backup 및 K3s etcd snapshot은 exporter metric이 확인되지 않으면 승인된
   synthetic probe의 성공/실패 signal을 별도 metric contract로 정한다.

## 수집과 민감정보 경계

- 허용 대상은 node, Kubernetes, etcd, Cilium, CNPG, API/JVM의 최소 메트릭과 승인된 조사 로그다.
- metric relabel에서 `pod_uid`, `container_id`, `image_id`를 제거한다. 고유 request ID, session,
  email, URL query, secret 값은 label로 만들지 않는다.
- 로그는 승인된 namespace·container만 선택하고 `loki.secretfilter`를 `loki.write` 앞에 둔다.
  API key, Bearer/JWT, password, connection URI, cookie가 포함된 시험 로그가 redaction되는지 확인한다.
- Grafana Cloud API key는 ESO가 만든 Pod 환경변수 Secret에서만 읽는다. ConfigMap, annotation,
  command line과 rendered artifact에는 넣지 않는다.

## 경보 계약과 시험

`aligner-observability-alert-contract`와 `aligner-db-alert-rules`는 evaluator에 붙일 hook이다.
metric family가 검증될 때까지 `*.disabled`는 활성 rule 파일이 아니다. 각 rule에는 owner,
severity, `for`, query, runbook URL, notification route, resolved notification을 운영 도구에
기록한다.

1. 비프로덕션 또는 승인된 maintenance 창에서 rule마다 안전한 signal을 한 번 만든다. 실제 노드
   중지, credential 손상, backup 삭제는 자동 시험하지 않는다.
2. firing 알림이 두 운영자에게 도착했는지, payload에 rule·cluster·runbook이 있는지 기록한다.
3. signal을 정상화하고 resolved 알림이 자동 도착하는지 같은 alert fingerprint로 확인한다.
4. API 오류/지연, disk, etcd, Cilium drop, replication lag, WAL/archive·backup, snapshot, certificate
   expiry, Grafana usage/cardinality를 모두 확인할 때까지 production readiness를 선언하지 않는다.

## Grafana Cloud 사용량·cardinality dashboard

`aligner-grafana-cloud-usage-dashboard-contract`의 다섯 panel을 만든다. Grafana Cloud datasource,
무료 tier 예산과 query metric은 계정별이므로 Gate에서 확정한다. job/metric/label별 active series,
ingest, namespace/container log volume, 예산 소진율과 초과 예상 시점을 매주 확인하고, budget rule은
경고 단계에서 collection을 줄이는 변경으로 연결한다.
