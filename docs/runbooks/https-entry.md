# HTTPS entry

## Runtime gate

Do not apply the `gateway/runtime` or `certificates/runtime` directories until
the public hostname, ACME notification email, DNS record, and Gabia LB target
approval are recorded outside Git. Replace `.invalid` placeholders locally in
an approved change. Run staging first, wait for its `Certificate` Ready
condition, then issue production and switch the Gateway Secret reference.

## LB and failure check

Register every node on NodePorts 30080 and 30443. Health check `GET /ping` on
30080 expects 200 from Traefik, independent of the API. After stopping one
node, its target must go unhealthy while the other two continue serving HTTPS;
restore the node and require the DaemonSet to be Ready on all three nodes before
closing the incident. `externalTrafficPolicy: Local` intentionally makes a
node without a local Traefik pod unhealthy.

## Route check

After TLS is Ready, verify the approved host over HTTP returns a 308 HTTPS
redirect, `https://<host>/api/...` reaches the API, and an unapproved Host or
HTTPS path outside `/api` returns a Gateway 404. Neither negative case may
reach the API.

## Alert hook contract

The monitoring owner must alert on `certmanager_certificate_expiration_timestamp_seconds`
for `secret_name="aligner-api-tls"` (expiry window) and on a non-Ready
`Certificate`/failed renewal event. The alert payload must name the Certificate,
namespace, Gateway Secret, and expiry or failure reason; route it to the two
platform operators. Alert-rule implementation belongs to the monitoring stack,
which is not installed by this change.
