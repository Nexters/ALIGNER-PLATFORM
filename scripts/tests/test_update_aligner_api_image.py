#!/usr/bin/env python3
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "update-aligner-api-image.sh"
API_DEPLOYMENT = REPO_ROOT / "gitops" / "apps" / "aligner-api" / "base" / "deployment.yaml"
SANDBOX_DEPLOYMENT = REPO_ROOT / "gitops" / "apps" / "aligner-sandbox" / "base" / "deployment.yaml"

VALID_SHA = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
VALID_DIGEST = f"sha256:{VALID_SHA}"
VALID_FULL_IMAGE = f"ghcr.io/nexters/aligner-server@{VALID_DIGEST}"
VALID_TAG_IMAGE = "ghcr.io/nexters/aligner-server:sha-1a2b3c4"


class UpdateAlignerApiImageTest(unittest.TestCase):
    def test_help_flag(self):
        result = subprocess.run([str(SCRIPT_PATH), "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("Usage:", result.stdout)
        self.assertIn("gitops/apps/aligner-api/base/deployment.yaml", result.stdout)

    def test_missing_args(self):
        result = subprocess.run([str(SCRIPT_PATH)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Image reference, tag, or digest argument is required", result.stderr)

    def test_placeholder_image_rejection(self):
        result = subprocess.run(
            [str(SCRIPT_PATH), "--dry-run", "registry.invalid/aligner-api:latest"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("placeholder 'registry.invalid'", result.stderr)

        result_zero = subprocess.run(
            [str(SCRIPT_PATH), "--dry-run", "ghcr.io/nexters/aligner-server@sha256:" + "0" * 64],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result_zero.returncode, 0)
        self.assertIn("all-zero digest", result_zero.stderr)

    def test_invalid_image_format_rejection(self):
        invalid_inputs = [
            "invalid image with spaces",
            "http://not-an-image",
            "ghcr.io/aligner::invalid",
        ]
        for inv in invalid_inputs:
            result = subprocess.run([str(SCRIPT_PATH), "--dry-run", inv], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0, f"Expected failure for: {inv}")

    def test_dry_run_does_not_modify_files(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write(API_DEPLOYMENT.read_text(encoding="utf-8"))
            temp_path = f.name
        try:
            original_content = pathlib.Path(temp_path).read_text()
            result = subprocess.run(
                [str(SCRIPT_PATH), "--file", temp_path, "--dry-run", VALID_FULL_IMAGE],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("[DRY-RUN]", result.stdout)
            self.assertIn("Dry-run validation complete. No files modified.", result.stdout)
            self.assertEqual(pathlib.Path(temp_path).read_text(), original_content)
        finally:
            os.remove(temp_path)

    def test_update_with_bare_tag(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write(API_DEPLOYMENT.read_text(encoding="utf-8"))
            temp_path = f.name
        try:
            result = subprocess.run(
                [str(SCRIPT_PATH), "--file", temp_path, "sha-9876543"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Successfully updated image reference", result.stdout)
            # Verify YAML structure
            doc = yaml.safe_load(pathlib.Path(temp_path).read_text())
            container = doc["spec"]["template"]["spec"]["containers"][0]
            self.assertEqual(container["image"], "ghcr.io/nexters/aligner-server:sha-9876543")
        finally:
            os.remove(temp_path)

    def test_update_with_bare_digest(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write(API_DEPLOYMENT.read_text(encoding="utf-8"))
            temp_path = f.name
        try:
            result = subprocess.run(
                [str(SCRIPT_PATH), "--file", temp_path, VALID_DIGEST],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            doc = yaml.safe_load(pathlib.Path(temp_path).read_text())
            container = doc["spec"]["template"]["spec"]["containers"][0]
            self.assertEqual(container["image"], f"ghcr.io/nexters/aligner-server@{VALID_DIGEST}")
        finally:
            os.remove(temp_path)

    def test_update_with_custom_repo_override(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write(API_DEPLOYMENT.read_text(encoding="utf-8"))
            temp_path = f.name
        try:
            result = subprocess.run(
                [str(SCRIPT_PATH), "--file", temp_path, "--repo", "ghcr.io/myorg/my-service", "v2.0.0"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            doc = yaml.safe_load(pathlib.Path(temp_path).read_text())
            container = doc["spec"]["template"]["spec"]["containers"][0]
            self.assertEqual(container["image"], "ghcr.io/myorg/my-service:v2.0.0")
        finally:
            os.remove(temp_path)

    def test_update_sandbox_deployment_structure(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write(SANDBOX_DEPLOYMENT.read_text(encoding="utf-8"))
            temp_path = f.name
        try:
            result = subprocess.run(
                [str(SCRIPT_PATH), "--file", temp_path, VALID_TAG_IMAGE],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            doc = yaml.safe_load(pathlib.Path(temp_path).read_text())
            container = doc["spec"]["template"]["spec"]["containers"][0]
            self.assertEqual(container["name"], "api")
            self.assertEqual(container["image"], VALID_TAG_IMAGE)
            self.assertEqual(container["securityContext"]["allowPrivilegeEscalation"], False)
        finally:
            os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
