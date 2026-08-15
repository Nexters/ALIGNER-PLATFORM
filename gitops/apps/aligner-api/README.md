# ALIGNER API runtime gates

`gitops/apps/kustomization.yaml` deliberately does not include this directory.
Before an overlay can be applied, a reviewer must replace the invalid immutable
image digest; record the CI build and reviewed digest in the deployment PR.
The zero digest is a runtime gate, not a deployable image. Before enabling this
app, create `aligner-api-secrets` out of band as documented in
`docs/runbooks/kubernetes-secrets.md` and replace the digest through Server CI.

The platform repository documents port `8080`, but not Spring Boot startup,
readiness, or liveness HTTP paths. Do not guess Actuator paths. Add the three
`httpGet` probes only after the application repository documents the paths and
their semantics. Confirm that a readiness failure removes an endpoint before
declaring the PDB and rolling-deployment behavior verified.

`resources: {}` in every profile is intentional. Populate requests and limits
from a recorded load test, including the test version, concurrency, p95/p99,
CPU, memory, and one-node-failure scheduling result. Profiles only establish
the operational replica/PDB contract: normal `3/2`, degraded `2/1`, and
maintenance `1/1` (replicas/minAvailable).

`allow-data.yaml` allows the CNPG cluster selected by `cnpg.io/cluster=aligner-db`
(the `aligner-postgresql-rw` Service) on 5432 and `aligner-redis` on 6379.
Verify those endpoint labels in the cluster before rollout. The standard
Kubernetes `NetworkPolicy` implementation used by Cilium cannot express an
HTTPS hostname: no external HTTPS policy is shipped until approved destination
CIDRs are supplied. A `0.0.0.0/0:443` rule would allow any IP sharing a DNS
answer and is not an acceptable substitute; use reviewed fixed CIDRs or a
separate Cilium FQDN policy after testing DNS churn.

The HTTPRoute follows the Gateway runtime handoff. It remains unaccepted until
the existing `aligner` Namespace is labelled `gateway-access=true`; this app
directory must not recreate that Namespace. Replace the `.invalid` hostname in
both the Gateway runtime and this route only after the public-DNS/TLS gate.

Cluster execution gates: confirm Cilium policy enforcement, Service endpoints,
one-node failure with no required Pod Pending, readiness traffic removal, and
load-test evidence. Rendering is not evidence for any of those checks.
