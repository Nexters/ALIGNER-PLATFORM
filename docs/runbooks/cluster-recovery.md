# K3s etcd 복구

## 사전 조건

- 복구할 snapshot 경로와 생성 시각
- snapshot 생성 당시의 K3s server token
- 동일한 K3s 버전과 server 설정
- PostgreSQL은 etcd와 별도 백업에서 복구한다는 인식

## 절차

1. 복구 대상 세 server의 K3s를 중지한다.
2. 첫 server에 원본 token과 snapshot을 준비한다.
3. 첫 server에서 cluster reset restore를 수행한다.
4. 첫 server가 단독 etcd member로 정상 기동하는지 확인한다.
5. 나머지 server의 기존 etcd 데이터를 격리하고 한 대씩 재가입한다.
6. etcd member 3개와 API readiness를 확인한다.
7. Argo CD reconcile 후 플랫폼 리소스를 확인한다.
8. PostgreSQL은 CNPG 복구 Runbook에 따라 별도로 정합성을 검증한다.

```bash
systemctl stop k3s
k3s server --cluster-reset --cluster-reset-restore-path=<snapshot>
systemctl start k3s
kubectl get --raw=/readyz
kubectl get nodes
```

원본 token이 없으면 snapshot 복호화가 불가능할 수 있다. token 없이 실패를 일부러 재현하지 않고 사전 조건 검사로 차단한다.
