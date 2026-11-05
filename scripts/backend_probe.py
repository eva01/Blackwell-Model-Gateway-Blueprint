#!/usr/bin/env python3
"""Read-only TCP reachability evidence; does not configure or certify isolation."""
import argparse
from datetime import datetime, timezone
import errno
import ipaddress
import json
import os
import socket


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip", required=True, help="Literal backend IPv4 or IPv6 address; no DNS/proxy")
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--expect", required=True, choices=("allowed", "blocked"))
    parser.add_argument("--vantage", required=True, help="gateway, client-network or same-node; operator-supplied label")
    parser.add_argument("--run-id", required=True, help="Same identifier for the complete acceptance window")
    args = parser.parse_args()
    report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "run_id": args.run_id,
        "vantage": args.vantage, "source_host": socket.gethostname(), "uid": os.getuid(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"), "target_ip": args.ip,
        "target_port": args.port, "expected": args.expect, "expectation_met": False,
        "certifies_isolation": False}
    exit_code = 2
    try:
        address = ipaddress.ip_address(args.ip)
        if not 1 <= args.port <= 65535:
            raise ValueError("Invalid TCP port")
        family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as connection:
            connection.settimeout(3)
            connection.connect((str(address), args.port))
        report["observation"] = "reachable"
    except (ValueError, OSError) as exc:
        if isinstance(exc, TimeoutError):
            report["observation"] = "timeout"
        elif isinstance(exc, ConnectionRefusedError):
            report["observation"] = "refused"
        else:
            report["observation"] = "inconclusive"
            report["error_type"] = type(exc).__name__
            if isinstance(exc, OSError):
                report["error_code"] = errno.errorcode.get(exc.errno, "UNKNOWN")
    if report["observation"] != "inconclusive":
        report["expectation_met"] = (report["observation"] == "reachable") == (args.expect == "allowed")
        exit_code = 0 if report["expectation_met"] else 1
    print(json.dumps(report, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
