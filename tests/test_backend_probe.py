import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/backend_probe.py"


class BackendProbe(unittest.TestCase):
    def run_probe(self, address, port, expect):
        return subprocess.run([sys.executable, str(SCRIPT), "--ip", address,
            "--port", str(port), "--expect", expect, "--vantage", "test",
            "--run-id", "synthetic-test"], capture_output=True, text=True)

    def test_open_listener_fails_blocked_check(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            result = self.run_probe("127.0.0.1", listener.getsockname()[1], "blocked")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["observation"], "reachable")

    def test_open_listener_passes_allowed_check(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            result = self.run_probe("127.0.0.1", listener.getsockname()[1], "allowed")
        self.assertEqual(result.returncode, 0)
        self.assertTrue(json.loads(result.stdout)["expectation_met"])

    def test_closed_listener_is_only_a_reachability_observation(self):
        with socket.socket() as reserved:
            reserved.bind(("127.0.0.1", 0))
            result = self.run_probe("127.0.0.1", reserved.getsockname()[1], "blocked")
        self.assertEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertIn(report["observation"], ("refused", "timeout"))
        self.assertFalse(report["certifies_isolation"])
        self.assertEqual(report["uid"], os.getuid())

    def test_hostname_or_invalid_ip_is_not_a_pass(self):
        result = self.run_probe("missing.invalid", 8000, "blocked")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(json.loads(result.stdout)["expectation_met"])


if __name__ == "__main__":
    unittest.main()
