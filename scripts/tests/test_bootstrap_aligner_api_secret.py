#!/usr/bin/env python3
import os
import pathlib
import subprocess
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "bootstrap-aligner-api-secret.sh"
KEYS_PATH = REPO_ROOT / "gitops" / "apps" / "aligner-api" / "runtime-secret.keys"

EXPECTED_KEYS = [
    "DB_PASSWORD",
    "DB_URL",
    "DB_USERNAME",
    "JWT_SECRET",
    "KAKAO_CLIENT_ID",
    "KAKAO_CLIENT_SECRET",
    "SERVER_PORT",
    "SPRINGDOC_ENABLED",
    "YMOVE_API_KEY",
]


class BootstrapAlignerApiSecretTest(unittest.TestCase):
    def test_runtime_secret_keys_file(self):
        self.assertTrue(KEYS_PATH.exists(), f"{KEYS_PATH} must exist")
        keys = [line.strip() for line in KEYS_PATH.read_text().splitlines() if line.strip()]
        self.assertEqual(EXPECTED_KEYS, keys)
        self.assertEqual(sorted(keys), keys, "Keys in runtime-secret.keys must be sorted alphabetically")

    def test_missing_args(self):
        result = subprocess.run([str(SCRIPT_PATH)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Secret file argument is required", result.stderr)

    def test_nonexistent_secret_file(self):
        result = subprocess.run([str(SCRIPT_PATH), "/nonexistent/path/secrets.env"], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not exist or is not a regular file", result.stderr)

    def test_missing_required_keys(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write("DB_PASSWORD=secret\nDB_URL=jdbc:...\n")
            temp_file = f.name
        try:
            result = subprocess.run([str(SCRIPT_PATH), temp_file], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing required keys", result.stderr)
            self.assertIn("DB_USERNAME", result.stderr)
            self.assertIn("JWT_SECRET", result.stderr)
            self.assertIn("KAKAO_CLIENT_ID", result.stderr)
            self.assertIn("KAKAO_CLIENT_SECRET", result.stderr)
            self.assertIn("SERVER_PORT", result.stderr)
            self.assertIn("SPRINGDOC_ENABLED", result.stderr)
            self.assertIn("YMOVE_API_KEY", result.stderr)
        finally:
            os.remove(temp_file)

    def test_all_keys_validation_success(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write("""# Test Secret file
DB_PASSWORD="mysecretpassword"
DB_URL="jdbc:postgresql://aligner-postgresql-rw.aligner-data.svc:5432/aligner_dev"
export DB_USERNAME=aligner_user
JWT_SECRET=thisisalongjwtsecret1234567890123456
KAKAO_CLIENT_ID='kakao-app-id'
export KAKAO_CLIENT_SECRET="kakao-secret-key"
SERVER_PORT=8080
SPRINGDOC_ENABLED=true
YMOVE_API_KEY="ymove-key-12345"
""")
            temp_file = f.name
        try:
            # We run with an invalid mock kubeconfig that exists to verify it passes validation and reaches kubectl
            with tempfile.NamedTemporaryFile("w", delete=False) as kf:
                kf.write("apiVersion: v1\nkind: Config\nclusters: []\ncontexts: []\nusers: []\n")
                kubeconfig_file = kf.name
            try:
                result = subprocess.run([str(SCRIPT_PATH), temp_file, kubeconfig_file, "aligner"], capture_output=True, text=True)
                # It should validate all 9 keys successfully before attempting kubectl operations
                self.assertIn("Secret file validated against runtime-secret.keys (all 9 keys present)", result.stdout)
            finally:
                os.remove(kubeconfig_file)
        finally:
            os.remove(temp_file)

    def test_nonexistent_kubeconfig_arg(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            for k in EXPECTED_KEYS:
                f.write(f"{k}=val\n")
            temp_file = f.name
        try:
            result = subprocess.run([str(SCRIPT_PATH), temp_file, "/nonexistent/kubeconfig", "aligner"], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Kubeconfig file '/nonexistent/kubeconfig' not found", result.stderr)
        finally:
            os.remove(temp_file)


if __name__ == "__main__":
    unittest.main()
