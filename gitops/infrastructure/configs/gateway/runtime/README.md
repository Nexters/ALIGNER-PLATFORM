# Gateway runtime gate

Before adding this directory to `../kustomization.yaml`, replace every
`api.aligner.example.invalid` with the approved public API hostname and verify
that `aligner-api-tls` will be created in `traefik`. Do not point the External
LB at the NodePorts first.

`Gateway` only accepts the configured hostname. The HTTP redirect route is
also host-scoped; an unknown host and an HTTPS path without an attached route
must return a Gateway 404 and must not reach the API. #29 owns the example
`HTTPRoute`, the `aligner` namespace label `gateway-access: "true"`, and the
backend Service `aligner-api:8080`.

LB target contract: add all three node private IPs as TCP targets for 30080 and
30443. Use `GET /ping` on port 30080 as the health check; it is Traefik's static
ping endpoint and must return 200 without relying on a Host header or app Pod.
Keep all three targets registered. `externalTrafficPolicy: Local` means a node
without its local Traefik Pod must be unhealthy, not proxy to another node.
