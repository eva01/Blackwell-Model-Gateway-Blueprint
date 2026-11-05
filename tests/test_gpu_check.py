import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "inference"))
from gpu_check import check_gpu


def fake_torch(capability, count=1, name=None):
    torch = Mock()
    torch.cuda.device_count.return_value = count
    torch.cuda.get_device_capability.return_value = capability
    torch.cuda.get_device_properties.return_value = SimpleNamespace(
        name=name or ("NVIDIA B200 MIG 4g.90gb" if capability == (10, 0)
                      else "NVIDIA RTX PRO 6000 Blackwell Server Edition"),
        total_memory=90 * 1024**3)
    torch.__version__ = "test"
    torch.version.cuda = "test"
    torch.ones.return_value = Mock(__matmul__=Mock(return_value=Mock()))
    torch.all.return_value.item.return_value = True
    return torch


class GPUCheck(unittest.TestCase):
    def test_default_auto_detects_allocated_b200_mig_and_rtx_demo(self):
        for capability, expected in (((10, 0), "b200"), ((12, 0), "rtx-pro-6000")):
            with self.subTest(capability=capability):
                report = check_gpu(fake_torch(capability))
                self.assertEqual(report["profile"], expected)
                self.assertEqual(report["requested_profile"], "auto")
                self.assertEqual(report["mig_profile"], "4g.90gb" if expected == "b200" else None)

    def test_auto_detects_full_b200_without_claiming_mig(self):
        report = check_gpu(fake_torch((10, 0), name="NVIDIA B200"))
        self.assertEqual(report["profile"], "b200")
        self.assertIsNone(report["mig_profile"])

    def test_auto_rejects_unknown_products_and_architectures(self):
        for capability, name in (((8, 9), "NVIDIA RTX 6000 Ada"),
                                 ((10, 0), "NVIDIA GB200"), ((12, 0), "NVIDIA GeForce RTX 5090")):
            with self.subTest(name=name), self.assertRaises(ValueError):
                check_gpu(fake_torch(capability, name=name))

    def test_mig_requirement_matches_exact_profile(self):
        report = check_gpu(fake_torch((10, 0)), expected_mig="4g.90gb")
        self.assertEqual(report["mig_profile"], "4g.90gb")
        for name in ("NVIDIA B200", "NVIDIA B200 MIG 3g.90gb", "NVIDIA B200 MIG 2g.45gb",
                     "NVIDIA B200 MIG 1c.4g.90gb"):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "MIG"):
                check_gpu(fake_torch((10, 0), name=name), expected_mig="4g.90gb")

    def test_missing_mig_name_uses_only_the_allocated_uuid(self):
        torch = fake_torch((10, 0), name="NVIDIA B200")
        torch.cuda.get_device_properties.return_value.uuid = "GPU-11111111-2222-3333-4444-555555555555"
        inventory = ("GPU 0: NVIDIA B200 (UUID: GPU-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee)\n"
                     "  MIG 3g.90gb Device 0: (UUID: MIG-aaaaaaaa-2222-3333-4444-555555555555)\n"
                     "  MIG 4g.90gb Device 1: (UUID: MIG-11111111-2222-3333-4444-555555555555)\n")
        with patch("gpu_check.subprocess.check_output", return_value=inventory):
            report = check_gpu(torch, expected_mig="4g.90gb")
        self.assertEqual(report["mig_profile"], "4g.90gb")
        self.assertEqual(report["mig_profile_source"], "nvidia-smi UUID match")
        with patch("gpu_check.subprocess.check_output", return_value=inventory.replace("MIG-11111111", "MIG-99999999")):
            with self.assertRaisesRegex(ValueError, "MIG"):
                check_gpu(torch, expected_mig="4g.90gb")

    def test_missing_inventory_fails_mig_requirement_without_guessing(self):
        torch = fake_torch((10, 0), name="NVIDIA B200")
        torch.cuda.get_device_properties.return_value.uuid = "11111111-2222-3333-4444-555555555555"
        for error in (FileNotFoundError(), subprocess.TimeoutExpired("nvidia-smi", 5)):
            with self.subTest(error=type(error).__name__), patch("gpu_check.subprocess.check_output", side_effect=error):
                with self.assertRaisesRegex(ValueError, "MIG"):
                    check_gpu(torch, expected_mig="4g.90gb")

    def test_rtx_and_b200_including_mig(self):
        for profile, capability in (("rtx-pro-6000", (12, 0)), ("b200", (10, 0))):
            with self.subTest(profile=profile):
                torch = fake_torch(capability)
                report = check_gpu(torch, profile)
                self.assertEqual(report["compute_capability"], ".".join(map(str, capability)))
                self.assertEqual(report["visible_devices"], 1)
                self.assertEqual(report["cuda_smoke_test"], "passed")
                torch.cuda.synchronize.assert_called_once()
                json.dumps(report)

    def test_rejects_wrong_architecture_or_profile(self):
        for profile, capability in (("b200", (12, 0)), ("rtx-pro-6000", (10, 0)),
                                    ("rtx-pro-6000", (8, 9)), ("unknown", (10, 0))):
            with self.subTest(profile=profile, capability=capability), self.assertRaises(ValueError):
                check_gpu(fake_torch(capability), profile)

    def test_rejects_missing_or_multiple_devices(self):
        for count in (0, 2, 8):
            with self.subTest(count=count), self.assertRaises(ValueError):
                check_gpu(fake_torch((10, 0), count), "b200")

    def test_cuda_kernel_failure_is_not_accepted(self):
        torch = fake_torch((10, 0))
        torch.ones.side_effect = RuntimeError("no kernel image available")
        with self.assertRaisesRegex(RuntimeError, "no kernel image"):
            check_gpu(torch, "b200")

    def test_incorrect_cuda_result_is_not_accepted(self):
        torch = fake_torch((10, 0))
        torch.all.return_value.item.return_value = False
        with self.assertRaisesRegex(RuntimeError, "CUDA"):
            check_gpu(torch, "b200")

    def test_docker_passes_profile_and_preflight_flag(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            docker = path / "docker"
            docker.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@"\n')
            docker.chmod(0o700)
            key = path / "backend.key"
            key.write_text("synthetic-key")
            config = path / "backend.env"
            config.write_text(f'VLLM_IMAGE=test-image\nMODEL_CACHE="{path}/cache"\n'
                              f'BACKEND_KEY_FILE="{key}"\nGPU_PROFILE=b200\n')
            env = dict(os.environ, PATH=f"{path}:{os.environ['PATH']}", BACKEND_ENV=str(config))
            env.pop("SLURM_JOB_ID", None)
            result = subprocess.run(["bash", str(ROOT / "inference/prototype-docker.sh"),
                                     "--check-gpu"], env=env, capture_output=True, text=True, check=True)
            self.assertIn("GPU_PROFILE", result.stdout.splitlines())
            self.assertEqual(result.stdout.splitlines()[-1], "--check-gpu")
            self.assertNotIn("synthetic-key", result.stdout)

    def test_slurm_preserves_device_visibility_and_propagates_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            srun = path / "srun"
            srun.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$CUDA_VISIBLE_DEVICES" "$GPU_PROFILE" "$@"\nexit 17\n')
            srun.chmod(0o700)
            image, key, config = path / "image.sqsh", path / "backend.key", path / "backend.env"
            image.touch()
            key.write_text("synthetic-key")
            config.write_text(f'VLLM_SQSH="{image}"\nMODEL_CACHE="{path}/cache"\n'
                              f'BACKEND_KEY_FILE="{key}"\nGPU_PROFILE=b200\n')
            env = dict(os.environ, PATH=f"{path}:{os.environ['PATH']}",
                       BACKEND_ENV=str(config), INFERENCE_PACKAGE_ROOT=str(ROOT),
                       SLURM_JOB_ID="test-job", CUDA_VISIBLE_DEVICES="MIG-assigned")
            result = subprocess.run(["bash", str(ROOT / "inference/serve.sbatch"), "--check-gpu"],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 17)
            self.assertEqual(result.stdout.splitlines()[:2], ["MIG-assigned", "b200"])
            self.assertEqual(result.stdout.splitlines()[-1], "--check-gpu")
            self.assertIn("--container-env=HF_HOME,GPU_PROFILE,", result.stdout)
            self.assertIn("EXPECTED_MIG_PROFILE", result.stdout)
            self.assertNotIn("synthetic-key", result.stdout)

    def test_preflight_failure_stops_launch_and_check_only_never_launches(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            python = path / "python3"
            python.write_text('#!/usr/bin/env bash\necho CHECK_CALLED\nexit "${CHECK_EXIT:-0}"\n')
            python.chmod(0o700)
            vllm = path / "vllm"
            vllm.write_text('#!/usr/bin/env bash\necho MODEL_LAUNCHED\n')
            vllm.chmod(0o700)
            key = path / "backend.key"
            key.write_text("synthetic-key")
            env = dict(os.environ, PATH=f"{path}:{os.environ['PATH']}", GPU_PROFILE="b200",
                       BACKEND_KEY_FILE=str(key))
            for args, code, launched in (([], "19", False), (["--check-gpu"], "0", False),
                                         ([], "0", True)):
                with self.subTest(args=args, code=code):
                    result = subprocess.run(["bash", str(ROOT / "inference/serve.sh"), *args],
                                            env=dict(env, CHECK_EXIT=code), capture_output=True, text=True)
                    self.assertEqual(result.returncode, int(code))
                    self.assertIn("CHECK_CALLED", result.stdout)
                    self.assertEqual("MODEL_LAUNCHED" in result.stdout, launched)
                    self.assertNotIn("synthetic-key", result.stdout)


if __name__ == "__main__":
    unittest.main()
