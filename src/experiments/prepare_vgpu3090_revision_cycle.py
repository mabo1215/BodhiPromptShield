#!/usr/bin/env python3
"""Prepare, but do not execute, the vGPU-3090 revision-cycle jobs.

The manifest produced by this script is deliberately timestamp-free and
credential-free.  It records only repository-side readiness, input hashes, and
commands that can be run after the vGPU instance is authorized.  A ready job is
not an executed experiment and must not be cited as evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


EXPERIMENTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENTS_DIR.parents[1]
DATA_DIR = REPO_ROOT / "data"
MANIFEST_PATH = DATA_DIR / "revision_cycle_vgpu3090_manifest.json"
ANNOTATIONS_PATH = DATA_DIR / "cppb_full_annotations.jsonl"
TAB_INPUT_DIR = EXPERIMENTS_DIR / "external_data" / "tab"

REQUIRED_FILES = [
    "src/experiments/cppb_reconstructed_ollama_utility_pilot.py",
    "src/experiments/tab_ollama_zero_shot_baseline.py",
    "src/experiments/semantic_mitigation_probe.py",
    "src/experiments/revision_cycle_gpu_smoke.py",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _safe_tag(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
        raise ValueError("output tag must contain only letters, digits, '.', '_' or '-'")
    return value


def build_manifest(model: str, output_tag: str) -> dict[str, object]:
    output_tag = _safe_tag(output_tag)
    rows = _read_jsonl(ANNOTATIONS_PATH) if ANNOTATIONS_PATH.exists() else []
    text_test = [
        row
        for row in rows
        if row.get("split") == "test" and row.get("modality") == "Text-only"
    ]
    test_templates = sorted({str(row.get("template_id")) for row in text_test})
    required_status = {
        path: (REPO_ROOT / path).exists()
        for path in REQUIRED_FILES
    }
    tab_files = sorted(path.relative_to(REPO_ROOT).as_posix() for path in TAB_INPUT_DIR.glob("*.json"))

    cppb_ready = (
        len(rows) == 256
        and len(text_test) == 48
        and len(test_templates) == 8
        and all(required_status.values())
    )
    tab_ready = bool(tab_files and required_status["src/experiments/tab_ollama_zero_shot_baseline.py"])

    commands = {
        "RC-01_cppb_reconstructed_live_text": (
            f"python src/experiments/cppb_reconstructed_ollama_utility_pilot.py "
            f"--model {model} --output-tag {output_tag}"
        ),
        "RC-02_semantic_mitigation_probe": (
            f"python src/experiments/semantic_mitigation_probe.py "
            f"--model {model} --output-tag {output_tag}"
        ),
        "RC-06_tab_runtime_pilot": (
            f"python src/experiments/tab_ollama_zero_shot_baseline.py "
            f"--split dev --max-documents 32 --model {model} --output-tag {output_tag}"
        ),
        "GPU_smoke_only": (
            f"python src/experiments/revision_cycle_gpu_smoke.py "
            f"--output data/revision_cycle_gpu_smoke_{output_tag}.json"
        ),
    }

    return {
        "manifest_version": "revision-cycle-v1",
        "purpose": "vGPU 3090 preparation; no experiment results",
        "output_tag": output_tag,
        "model": model,
        "repository": "BodhiPromptShield",
        "inputs": {
            "cppb_annotations": {
                "path": ANNOTATIONS_PATH.relative_to(REPO_ROOT).as_posix(),
                "sha256": _sha256(ANNOTATIONS_PATH) if ANNOTATIONS_PATH.exists() else "",
                "record_count": len(rows),
                "test_text_record_count": len(text_test),
                "test_template_ids": test_templates,
                "historical_raw_prompts_recovered": False,
            },
            "tab_json_files": tab_files,
        },
        "repository_checks": {
            "required_files": required_status,
            "required_files_pass": all(required_status.values()),
        },
        "jobs": [
            {
                "id": "RC-01_cppb_reconstructed_live_text",
                "status": "ready_for_authorized_vgpu_run" if cppb_ready else "blocked_input_check",
                "command": commands["RC-01_cppb_reconstructed_live_text"],
                "scope": "48 reconstructed text-only test prompts, 8 held-out templates, four matched conditions",
                "claim_boundary": "not historical CPPB recovery; no OCR rows",
            },
            {
                "id": "RC-02_semantic_mitigation_probe",
                "status": "ready_for_authorized_vgpu_run" if required_status["src/experiments/semantic_mitigation_probe.py"] else "blocked_input_check",
                "command": commands["RC-02_semantic_mitigation_probe"],
                "scope": "frozen raw/placeholder/context-abstraction/access-control attack panel",
                "claim_boundary": "no mitigation claim until attacker/runtime/output records are complete",
            },
            {
                "id": "RC-03_same_protocol_closest_systems",
                "status": "blocked_external_implementation",
                "command": "",
                "scope": "Casper and PrivacyRestore under the frozen CPPB protocol",
                "claim_boundary": "conceptual comparison only until reproducible implementations or authorized outputs exist",
            },
            {
                "id": "RC-04_live_mapping_compromise",
                "status": "blocked_live_service",
                "command": "",
                "scope": "deployed mapping service, credential, audit, and session-isolation probes",
                "claim_boundary": "existing evidence is mechanism-level, not live-stack evidence",
            },
            {
                "id": "RC-05_independent_human_utility",
                "status": "blocked_human_raters",
                "command": "",
                "scope": "blinded UI and fixed utility rubric",
                "claim_boundary": "not a GPU experiment; model-based pilot remains separate",
            },
            {
                "id": "RC-06_tab_runtime_pilot",
                "status": "ready_for_authorized_vgpu_run" if tab_ready else "blocked_input_check",
                "command": commands["RC-06_tab_runtime_pilot"],
                "scope": "TAB dev:32 named local-model pilot",
                "claim_boundary": "external pilot only; not CPPB closure or a cross-model comparison",
            },
            {
                "id": "GPU_smoke_only",
                "status": "ready_for_local_or_vgpu_check",
                "command": commands["GPU_smoke_only"],
                "scope": "small CUDA allocation and matrix checksum",
                "claim_boundary": "execution check only; never paper evidence",
            },
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="llama3.2:latest")
    parser.add_argument("--output-tag", default="revision20260903")
    args = parser.parse_args()

    manifest = build_manifest(args.model, args.output_tag)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote preparation manifest: {MANIFEST_PATH}")
    for job in manifest["jobs"]:
        print(f"{job['id']}: {job['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
