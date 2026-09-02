#!/usr/bin/env python3
"""Run a small, non-evidentiary CUDA smoke test for the revision cycle."""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "data" / "revision_cycle_gpu_smoke.json"


def _nvidia_smi() -> str:
    try:
        return subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free,memory.used,driver_version", "--format=csv,noheader"],
            text=True,
            stderr=subprocess.STDOUT,
            timeout=30,
        ).strip()
    except (FileNotFoundError, subprocess.SubprocessError) as error:
        return f"unavailable: {error}"


def run(output_path: Path, size: int, seed: int) -> dict[str, object]:
    try:
        import torch
    except ImportError as error:
        raise RuntimeError("PyTorch is required for the CUDA smoke test") from error

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available in the current Python environment")

    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    device = torch.device("cuda:0")
    torch.cuda.synchronize(device)
    started = time.perf_counter()
    left = torch.arange(size * size, dtype=torch.float32, device=device).reshape(size, size)
    right = torch.flip(left, dims=[1])
    product = left @ right
    torch.cuda.synchronize(device)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    checksum = float(product.sum().item())
    result = {
        "test": "revision-cycle-cuda-smoke",
        "evidentiary_status": "execution_check_only",
        "torch_version": str(torch.__version__),
        "cuda_version": str(torch.version.cuda),
        "device": str(torch.cuda.get_device_name(device)),
        "device_capability": ".".join(str(value) for value in torch.cuda.get_device_capability(device)),
        "matrix_size": size,
        "seed": seed,
        "checksum": checksum,
        "elapsed_ms": round(elapsed_ms, 3),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "nvidia_smi": _nvidia_smi(),
    }
    del left, right, product
    torch.cuda.empty_cache()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--seed", type=int, default=20260903)
    args = parser.parse_args()
    if args.size < 16 or args.size > 4096:
        raise SystemExit("--size must be between 16 and 4096")
    result = run(args.output, args.size, args.seed)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
