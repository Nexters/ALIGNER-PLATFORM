#!/usr/bin/env python3
"""Run fixed, credential-free read/write probes during an approved CNPG drill."""

import argparse
import datetime
import json
import subprocess
import sys
import time


KUBECTL = "kubectl"
NAMESPACE = "aligner-data"
CLUSTER = "aligner-db"
MAX_SAMPLES = 3600
WRITE_SQL = "CREATE TEMP TABLE failover_drill (id integer); INSERT INTO failover_drill VALUES (1);"
READ_SQL = "SELECT 1;"


def run_json(argv):
    completed = subprocess.run(argv, capture_output=True, text=True, check=False)
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout).strip()[:300])
    return json.loads(completed.stdout)


def primary_pod():
    cluster = run_json([KUBECTL, "-n", NAMESPACE, "get", "cluster", CLUSTER, "-o", "json"])
    primary = cluster.get("status", {}).get("currentPrimary")
    if not primary:
        raise RuntimeError("CNPG status.currentPrimary is unavailable")
    return primary


def probe(operation, sql):
    started = time.monotonic_ns()
    try:
        pod = primary_pod()
        completed = subprocess.run(
            [KUBECTL, "-n", NAMESPACE, "exec", pod, "--", "psql", "-U", "postgres", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-qAt", "-c", sql],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode:
            raise RuntimeError((completed.stderr or completed.stdout).strip()[:300])
        return {"operation": operation, "success": True, "latency_ms": round((time.monotonic_ns() - started) / 1_000_000, 3)}
    except Exception as error:
        return {"operation": operation, "success": False, "latency_ms": round((time.monotonic_ns() - started) / 1_000_000, 3), "error": str(error)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=60)
    parser.add_argument("--interval-seconds", type=float, default=1.0)
    args = parser.parse_args()
    if not 1 <= args.samples <= MAX_SAMPLES or not 0 <= args.interval_seconds <= 60:
        parser.error("samples must be 1..3600 and interval-seconds must be 0..60")

    for index in range(args.samples):
        for operation, sql in (("write", WRITE_SQL), ("read", READ_SQL)):
            record = probe(operation, sql)
            record["observed_at_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            print(json.dumps(record, sort_keys=True), flush=True)
        if index + 1 < args.samples:
            time.sleep(args.interval_seconds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
