import contextlib
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from backup import backup
from bootstrap import validate_url
import keys


class Helpers(unittest.TestCase):
    def test_key_listing_never_prints_stored_credentials(self):
        response = {"resources": [{"kind": "llm.apiKey", "id": "key-resource-id",
            "revision": 1, "createdAt": "2026-11-05T00:00:00Z", "updatedAt": "2026-11-05T00:00:00Z",
            "value": {"key": "synthetic-raw-secret", "keyHash": "sha256:synthetic-secret-hash",
                "metadata": {"name": "alice", "user": "alice", "privateNote": "synthetic-private-note"},
                "allowedModels": ["qwen-coder"], "budgets": []}}]}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            credentials = root / "runtime/secrets/admin.json"
            credentials.parent.mkdir(parents=True)
            credentials.write_text(json.dumps({"url": "http://unused.invalid", "username": "admin", "password": "test-only"}))
            output = io.StringIO()
            with patch.object(keys, "ROOT", root), patch.object(keys.Admin, "request", return_value=response), \
                    patch.object(sys, "argv", ["keys.py", "list"]), contextlib.redirect_stdout(output):
                keys.main()
        rendered = output.getvalue()
        for secret in ("synthetic-raw-secret", "sha256:synthetic-secret-hash", "synthetic-private-note"):
            self.assertNotIn(secret, rendered)
        self.assertIn("key-resource-id", rendered)
        self.assertIn("alice", rendered)
        self.assertIn("qwen-coder", rendered)

    def test_backend_url_rejects_credentials_and_injection(self):
        self.assertEqual(validate_url("http://node:8000/v1/"), "http://node:8000/v1")
        for value in ("http://user:secret@node/v1", "http://node", "http://node/v1?key=x", "http://node/v1\nX=Y", "http://$HOST/v1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_url(value)

    def test_online_backup_preserves_committed_wal_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temp:
            src, dst = Path(temp) / "live.db", Path(temp) / "backup.db"
            with sqlite3.connect(src) as db:
                db.execute("PRAGMA journal_mode=WAL")
                db.execute("CREATE TABLE keys (name TEXT)")
                db.execute("INSERT INTO keys VALUES ('alice')")
                db.commit()
                backup(src, dst)
                with sqlite3.connect(dst) as restored:
                    self.assertEqual(restored.execute("SELECT name FROM keys").fetchall(), [("alice",)])
                with self.assertRaises(FileExistsError):
                    backup(src, dst)
                self.assertEqual(dst.stat().st_mode & 0o777, 0o600)

    def test_launch_command_parameters_and_invalid_context(self):
        env = dict(os.environ, MAX_MODEL_LEN="262144", MAX_NUM_SEQS="1", CUDA_VISIBLE_DEVICES="MIG-test")
        command = ["bash", str(ROOT / "inference/serve.sh"), "--dry-run"]
        result = subprocess.run(command, env=env, capture_output=True, text=True, check=True)
        self.assertIn("--max-model-len 262144", result.stdout)
        self.assertIn("--enable-prompt-tokens-details", result.stdout)
        self.assertNotIn("--api-key", result.stdout)
        env["MAX_MODEL_LEN"] = "bad;echo unsafe"
        self.assertNotEqual(subprocess.run(command, env=env, capture_output=True).returncode, 0)

    def test_default_context_matches_client_and_supports_200k_input(self):
        env = {k: v for k, v in os.environ.items() if k not in ("MAX_MODEL_LEN", "MAX_NUM_SEQS", "GPU_PROFILE")}
        command = ["bash", str(ROOT / "inference/serve.sh"), "--dry-run"]
        result = subprocess.run(command, env=env, capture_output=True, text=True, check=True)
        client = json.loads((ROOT / "client/opencode.json").read_text())
        limit = client["provider"]["inference"]["models"]["qwen-coder"]["limit"]
        self.assertEqual(limit["context"], 262144)
        self.assertIn(f'--max-model-len {limit["context"]}', result.stdout)
        self.assertGreaterEqual(limit["context"] - limit["output"], 200000)
        self.assertIn("--max-num-seqs 1", result.stdout)


if __name__ == "__main__":
    unittest.main()
