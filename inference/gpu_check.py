#!/usr/bin/env python3
"""Check the allocated GPU and run a small CUDA operation inside the serving image."""
import json
import os
import re
import subprocess
import uuid

PROFILES = {"rtx-pro-6000": (12, 0), "b200": (10, 0)}


def normalized_uuid(value):
    if not isinstance(value, str):
        return None
    try:
        return uuid.UUID(re.sub(r"^(GPU-|MIG-)", "", value, flags=re.I))
    except ValueError:
        return None


def mig_identity(props):
    match = re.search(r"\bMIG\s+(\S+)", props.name, re.I)
    if match:
        return match.group(1).lower(), "CUDA device name"
    allocated_uuid = normalized_uuid(getattr(props, "uuid", None))
    if allocated_uuid is not None:
        try:
            listing = subprocess.check_output(["nvidia-smi", "-L"], text=True,
                                              stderr=subprocess.DEVNULL, timeout=5)
        except (OSError, subprocess.SubprocessError):
            return None, "unavailable"
        matches = [profile.lower() for profile, device_uuid in re.findall(
            r"MIG\s+(\S+)\s+Device\s+\d+:\s*\(UUID:\s*(MIG-[^)\s]+)\)", listing)
            if normalized_uuid(device_uuid) == allocated_uuid]
        if len(matches) == 1:
            return matches[0], "nvidia-smi UUID match"
    return None, "unavailable"


def check_gpu(torch, profile="auto", expected_mig=None):
    if profile not in ("auto", *PROFILES):
        raise ValueError(f"Unknown GPU_PROFILE={profile!r}; choose auto, rtx-pro-6000 or b200")
    count = torch.cuda.device_count()
    if count != 1:
        raise ValueError(f"Expected exactly one visible GPU/MIG device, got {count}; check allocation")
    capability = torch.cuda.get_device_capability(0)
    props = torch.cuda.get_device_properties(0)
    if capability == PROFILES["b200"] and re.search(r"\bB200\b", props.name, re.I):
        detected = "b200"
    elif (capability == PROFILES["rtx-pro-6000"]
          and "RTX PRO 6000" in props.name.upper() and "BLACKWELL" in props.name.upper()):
        detected = "rtx-pro-6000"
    else:
        raise ValueError(f"Unsupported device {props.name!r} (SM{capability[0]}{capability[1]}); "
                         "expected B200 or RTX PRO 6000 Blackwell")
    if profile != "auto" and profile != detected:
        raise ValueError(f"GPU_PROFILE={profile} does not match detected {detected}; check allocation")
    mig_profile, mig_source = mig_identity(props)
    if expected_mig and (detected != "b200" or mig_profile != expected_mig):
        raise ValueError(f"Required B200 MIG {expected_mig}, but CUDA reports {props.name!r}; "
                         "confirm the Slurm allocation and CUDA/nvidia-smi identity; memory size is not profile proof")
    tensor = torch.ones((32, 32), device="cuda", dtype=torch.float16)
    result = tensor @ tensor
    torch.cuda.synchronize()
    if not torch.all(result == 32).item():
        raise RuntimeError("CUDA smoke test returned an incorrect result")
    return {
        "profile": detected, "requested_profile": profile, "mig_profile": mig_profile,
        "mig_profile_source": mig_source,
        "device": props.name, "visible_devices": count,
        "compute_capability": f"{capability[0]}.{capability[1]}",
        "memory_bytes": props.total_memory, "torch_version": torch.__version__,
        "cuda_runtime": torch.version.cuda, "cuda_smoke_test": "passed",
        "scope": "Device and basic CUDA check only; NVFP4 model startup and requests still required",
    }


if __name__ == "__main__":
    import torch

    try:
        print(json.dumps(check_gpu(torch, os.environ.get("GPU_PROFILE") or "auto",
                                   os.environ.get("EXPECTED_MIG_PROFILE"))), flush=True)
    except (ValueError, RuntimeError) as error:
        raise SystemExit(f"GPU preflight failed: {error}")
