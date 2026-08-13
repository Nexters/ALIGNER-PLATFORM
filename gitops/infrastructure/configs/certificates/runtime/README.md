# Certificate runtime gate

Replace the placeholder email and hostname in this directory only after public
DNS resolves to the Gabia External LB and the LB passes its Traefik health
checks. Add `gateway/runtime` and this directory to their parent
`kustomization.yaml` together, with the Gateway initially referencing
`aligner-api-tls-staging`.

Wait for `Certificate/aligner-api-staging` to report `Ready=True` and verify
the HTTP-01 challenge from the public Internet. Only then add
`production-certificate.yaml`, wait for `Certificate/aligner-api` to be Ready,
and switch the Gateway reference to `aligner-api-tls`. This prevents a real
Let's Encrypt issuance while the repository contains placeholder values.
