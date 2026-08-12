# Cilium Gate

## Automatic, non-destructive validation

Run only against the intended pre-production cluster, after Cilium `1.20.0` is installed:

```bash
make verify-cilium
```

This target deliberately fails closed until approvals are supplied.

For an approved run, invoke Ansible directly so its fixed command list receives only reviewed
variables:

```bash
ANSIBLE_CONFIG=ansible/ansible.cfg \
ansible-playbook -i .runtime/inventory.yaml ansible/playbooks/verify-cilium.yml \
  -e cilium_gate_runtime_approved=true \
  -e cilium_gate_agent_restart_approved=true \
  -e cilium_gate_vm_stop_evidence_approved=true \
  -e cilium_gate_vm_stop_evidence_ref='CHANGE-123: reviewed VM-stop evidence'
```

The playbook uses fixed commands and two distinct disposable namespaces. It deletes both namespaces even
when a test fails. Evidence is local, secret-free, and written to
`.runtime/cilium-gate/gate-summary.yml`. It records the installed chart pin and Cilium CLI version;
the CLI version is reviewed for compatibility and is not assumed to equal the Helm chart version.

`kubectl top` requires Metrics Server. Its absence is a Gate failure, because CPU/memory evidence
would be missing. RSS and the count of non-comment Prometheus metric lines are captured from each
agent.

## Manual VM-stop evidence gate

Do not stop a VM from Ansible, CI, or this repository. Obtain a maintenance approval identifying
the target node and recovery owner, then perform this procedure manually:

1. Save the baseline: all nodes Ready, `kubectl get pods -A`, and a successful service request.
2. Stop exactly one reviewed VM using the provider console/API outside this repository.
3. From a surviving management path, record timestamps for node `NotReady`, required Pod Pending
   count, and recovery of the service request. Do not add production data for this test.
4. Start the same VM; wait for K3s and the Cilium DaemonSet to become Ready, then rerun
   `make verify-cilium`.
5. Attach the redacted evidence reference to the change record and pass it as
   `cilium_gate_vm_stop_evidence_ref` only after review.

If any item fails, the Gate is FAIL and production data remains blocked. Do not replace Cilium in
place. Record whether to rebuild a new cluster with Flannel in ADR 0006, then perform the rebuild
through the normal Day-1 order.
