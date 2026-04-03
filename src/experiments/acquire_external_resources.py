#!/usr/bin/env python3
"""Build an acquisition manifest for external datasets and baseline resources.

The helper does two things:
1. Always writes a machine-readable manifest describing official access paths.
2. Optionally downloads public GitHub-hosted resources by trying both main and
   master archive URLs.

Licensed clinical corpora and request-gated benchmarks are recorded in the
manifest but are never fetched automatically.
"""
from __future__ import annotations

import argparse
import json
import shutil
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


EXPERIMENTS_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST_PATH = EXPERIMENTS_DIR / "external_resource_acquisition_manifest.json"
DEFAULT_DOWNLOAD_ROOT = EXPERIMENTS_DIR / "external_data" / "resource_cache"


def _github_archive_candidates(owner_repo: str) -> list[str]:
    return [
        f"https://github.com/{owner_repo}/archive/refs/heads/main.zip",
        f"https://github.com/{owner_repo}/archive/refs/heads/master.zip",
    ]


RESOURCES: list[dict[str, Any]] = [
    {
        "id": "i2b2_dataset",
        "category": "Clinical Corpus",
        "resource": "i2b2 / n2c2 Clinical NLP Datasets",
        "purpose": "Licensed PHI-style source corpus for normalized clinical exports.",
        "official_url": "https://www.i2b2.org/NLP/DataSets/",
        "access_mode": "licensed_access",
        "notes": "Requires an approved DUA; the repository does not attempt automated download.",
    },
    {
        "id": "harvard_dbmi_portal",
        "category": "Clinical Corpus",
        "resource": "Harvard DBMI Data Portal",
        "purpose": "Official portal for approved i2b2/n2c2 data access.",
        "official_url": "https://portal.dbmi.hms.harvard.edu/",
        "access_mode": "portal_access",
        "notes": "Portal access is institution- and approval-dependent.",
    },
    {
        "id": "cord_dataset",
        "category": "OCR-heavy Dataset",
        "resource": "CORD (Consolidated Receipt Dataset)",
        "purpose": "Public receipt benchmark for OCR-heavy parsing and entity extraction.",
        "official_url": "https://github.com/clovaai/cord",
        "access_mode": "public_github_archive",
        "archive_candidates": _github_archive_candidates("clovaai/cord"),
        "cache_subdir": "cord_dataset",
        "notes": "The official repository documents the public sample release and Hugging Face mirrors.",
    },
    {
        "id": "funsd_dataset",
        "category": "OCR-heavy Dataset",
        "resource": "FUNSD (Form Understanding Dataset)",
        "purpose": "Noisy scanned form benchmark for post-OCR structured extraction.",
        "official_url": "https://huggingface.co/datasets/funsd",
        "access_mode": "landing_page_only",
        "notes": "The manuscript cites the Hugging Face landing page; pin a stable snapshot URL before automated download.",
    },
    {
        "id": "sroie_dataset",
        "category": "OCR-heavy Dataset",
        "resource": "SROIE (Scanned Receipt OCR and IE)",
        "purpose": "Receipt-style OCR benchmark for layout parsing and information extraction.",
        "official_url": "https://huggingface.co/datasets/sroie",
        "access_mode": "landing_page_only",
        "notes": "The manuscript cites the Hugging Face landing page; pin a stable snapshot URL before automated download.",
    },
    {
        "id": "docile_benchmark",
        "category": "OCR-heavy Dataset",
        "resource": "DocILE Benchmark",
        "purpose": "Business-document benchmark for invoice and reimbursement workflows.",
        "official_url": "https://docile.rossum.ai/",
        "access_mode": "request_gated_benchmark",
        "request_url": "https://forms.gle/poJqGXrxoftWrUsc8",
        "helper_repo_url": "https://github.com/rossumai/docile",
        "helper_archive_candidates": _github_archive_candidates("rossumai/docile"),
        "cache_subdir": "docile_helper_repo",
        "notes": "Dataset access requires a request form; the helper repository is public and can be cached locally.",
    },
    {
        "id": "presidio_docs",
        "category": "External Baseline",
        "resource": "Presidio (Microsoft)",
        "purpose": "Enterprise-style PII detection and redaction reference pipeline.",
        "official_url": "https://microsoft.github.io/presidio/",
        "access_mode": "documentation_only",
        "notes": "Documentation reference for the released Presidio-class approximation.",
    },
    {
        "id": "philter_lite_repo",
        "category": "External Baseline",
        "resource": "Philter-lite",
        "purpose": "Open-source clinical de-identification baseline comparator.",
        "official_url": "https://github.com/SironaMedical/philter-lite",
        "access_mode": "public_github_archive",
        "archive_candidates": _github_archive_candidates("SironaMedical/philter-lite"),
        "cache_subdir": "philter_lite_repo",
        "notes": "Repository-side acquisition only; runtime compatibility still needs separate validation.",
    },
    {
        "id": "clinideid_repo",
        "category": "External Baseline",
        "resource": "CliniDeID",
        "purpose": "Clinical text de-identification toolkit for named baseline reruns.",
        "official_url": "https://github.com/Clinacuity/CliniDeID",
        "access_mode": "public_github_archive",
        "archive_candidates": _github_archive_candidates("Clinacuity/CliniDeID"),
        "cache_subdir": "clinideid_repo",
        "notes": "Repository-side acquisition only; named runtime evidence still requires local execution logs.",
    },
    {
        "id": "medspacy_repo",
        "category": "External Pipeline",
        "resource": "medSpaCy",
        "purpose": "Clinical NLP toolkit for rule-based PHI extraction workflows.",
        "official_url": "https://github.com/medspacy/medspacy",
        "access_mode": "public_github_archive",
        "archive_candidates": _github_archive_candidates("medspacy/medspacy"),
        "cache_subdir": "medspacy_repo",
        "notes": "Repository-side acquisition only; pipeline integration remains future work.",
    },
    {
        "id": "tesseract_docs",
        "category": "OCR Engine",
        "resource": "Tesseract OCR",
        "purpose": "Open-source OCR engine documentation for exact runtime pinning.",
        "official_url": "https://tesseract-ocr.github.io/tessdoc/",
        "access_mode": "documentation_only",
        "notes": "Use to pin engine version once OCR-heavy reruns are executed.",
    },
    {
        "id": "paddleocr_docs",
        "category": "OCR Engine",
        "resource": "PaddleOCR",
        "purpose": "Alternative OCR engine documentation for throughput/layout comparisons.",
        "official_url": "https://www.paddleocr.ai/",
        "access_mode": "documentation_only",
        "notes": "Use to pin engine version once OCR-heavy reruns are executed.",
    },
    {
        "id": "openai_model_docs",
        "category": "Closed Model Documentation",
        "resource": "OpenAI Model Documentation",
        "purpose": "Reference for recording exact deployed model IDs and API behavior.",
        "official_url": "https://developers.openai.com/api/docs/models",
        "access_mode": "documentation_only",
        "notes": "Documentation reference only; does not provide executable evidence by itself.",
    },
    {
        "id": "anthropic_model_docs",
        "category": "Closed Model Documentation",
        "resource": "Anthropic Model Documentation",
        "purpose": "Reference for snapshot-based Claude model identifiers.",
        "official_url": "https://docs.anthropic.com/en/docs/models-overview",
        "access_mode": "documentation_only",
        "notes": "Documentation reference only; does not provide executable evidence by itself.",
    },
]


def _write_access_note(resource: dict[str, Any], destination: Path) -> None:
    lines = [
        f"Resource: {resource['resource']}",
        f"Category: {resource['category']}",
        f"Purpose: {resource['purpose']}",
        f"Official URL: {resource['official_url']}",
        f"Access mode: {resource['access_mode']}",
        f"Notes: {resource['notes']}",
    ]
    request_url = resource.get("request_url")
    if request_url:
        lines.append(f"Request URL: {request_url}")
    helper_repo_url = resource.get("helper_repo_url")
    if helper_repo_url:
        lines.append(f"Helper repo: {helper_repo_url}")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _download_first_available(candidate_urls: list[str], archive_path: Path) -> str | None:
    for candidate_url in candidate_urls:
        try:
            with urllib.request.urlopen(candidate_url) as response, archive_path.open("wb") as handle:
                shutil.copyfileobj(response, handle)
            return candidate_url
        except urllib.error.URLError:
            continue
    return None


def _extract_zip(archive_path: Path, destination_dir: Path) -> None:
    if destination_dir.exists():
        shutil.rmtree(destination_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "r") as archive:
        archive.extractall(destination_dir)


def _selected_resources(resource_ids: list[str]) -> list[dict[str, Any]]:
    if not resource_ids or resource_ids == ["all"]:
        return RESOURCES
    selected = {resource_id.strip().lower() for resource_id in resource_ids}
    return [resource for resource in RESOURCES if resource["id"] in selected]


def build_manifest(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    for resource in selected:
        manifest.append(
            {
                "id": resource["id"],
                "category": resource["category"],
                "resource": resource["resource"],
                "purpose": resource["purpose"],
                "official_url": resource["official_url"],
                "access_mode": resource["access_mode"],
                "notes": resource["notes"],
                "request_url": resource.get("request_url"),
                "helper_repo_url": resource.get("helper_repo_url"),
                "archive_candidates": resource.get("archive_candidates", []),
                "helper_archive_candidates": resource.get("helper_archive_candidates", []),
                "cache_subdir": resource.get("cache_subdir"),
                "current_release_status": "resource entry recorded; local download not attempted",
            }
        )
    return manifest


def _attempt_public_downloads(selected: list[dict[str, Any]], download_root: Path) -> dict[str, dict[str, str]]:
    download_root.mkdir(parents=True, exist_ok=True)
    archive_root = download_root / "_archives"
    archive_root.mkdir(parents=True, exist_ok=True)
    status_map: dict[str, dict[str, str]] = {}

    for resource in selected:
        resource_dir = download_root / resource["id"]
        resource_dir.mkdir(parents=True, exist_ok=True)
        _write_access_note(resource, resource_dir / "ACCESS_NOTE.txt")
        status_map[resource["id"]] = {"status": "recorded", "detail": "Access note written."}

        if resource["access_mode"] != "public_github_archive":
            continue

        archive_path = archive_root / f"{resource['id']}.zip"
        candidate_url = _download_first_available(resource.get("archive_candidates", []), archive_path)
        if candidate_url:
            extract_dir = resource_dir / "archive"
            _extract_zip(archive_path, extract_dir)
            status_map[resource["id"]] = {
                "status": "downloaded",
                "detail": f"Downloaded and extracted from {candidate_url}",
            }
            continue

        helper_candidates = resource.get("helper_archive_candidates", [])
        if helper_candidates:
            helper_archive_path = archive_root / f"{resource['id']}_helper.zip"
            helper_url = _download_first_available(helper_candidates, helper_archive_path)
            if helper_url:
                extract_dir = resource_dir / "helper_archive"
                _extract_zip(helper_archive_path, extract_dir)
                status_map[resource["id"]] = {
                    "status": "downloaded_helper_repo",
                    "detail": f"Downloaded helper repository from {helper_url}",
                }
                continue

        status_map[resource["id"]] = {
            "status": "download_failed",
            "detail": "No public archive candidate succeeded; keep the official URL as the access path.",
        }

    return status_map


def main() -> int:
    parser = argparse.ArgumentParser(description="Record or optionally fetch external dataset and baseline resources.")
    parser.add_argument(
        "--resource",
        action="append",
        default=[],
        help="Resource id to include; repeatable. Defaults to all.",
    )
    parser.add_argument(
        "--manifest-out",
        default=str(DEFAULT_MANIFEST_PATH),
        help="Output JSON manifest describing official access paths.",
    )
    parser.add_argument(
        "--download-root",
        default=str(DEFAULT_DOWNLOAD_ROOT),
        help="Directory for optional public GitHub archive downloads and access notes.",
    )
    parser.add_argument(
        "--download-public-github",
        action="store_true",
        help="Attempt to download public GitHub-hosted resources and extract them under --download-root.",
    )
    args = parser.parse_args()

    selected = _selected_resources(args.resource)
    manifest = build_manifest(selected)

    if args.download_public_github:
        status_map = _attempt_public_downloads(selected, Path(args.download_root))
        for entry in manifest:
            status = status_map.get(entry["id"])
            if status:
                entry["current_release_status"] = status["detail"]
                entry["download_status"] = status["status"]

    output_path = Path(args.manifest_out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"External resource acquisition manifest written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())