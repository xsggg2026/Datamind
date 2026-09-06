from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


def _safe_filename(url: str, fallback_prefix: str, index: int) -> str:
    path = urlparse(url).path
    name = Path(path).name.strip()
    if name:
        return name
    return f"{fallback_prefix}_{index}.xbrl"


def read_manifest(manifest_path: Path) -> List[Dict[str, str]]:
    if manifest_path.suffix.lower() != ".csv":
        raise ValueError("Only CSV manifest is supported. Expected columns: url, filename(optional)")

    rows: List[Dict[str, str]] = []
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = (row.get("url") or "").strip()
            if not url:
                continue
            rows.append({"url": url, "filename": (row.get("filename") or "").strip()})
    return rows


def download_from_manifest(
    manifest_path: Path,
    output_dir: Path,
    timeout_seconds: int = 25,
    overwrite: bool = False,
) -> Dict[str, int]:
    rows = read_manifest(manifest_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    skipped = 0
    failed = 0

    for index, item in enumerate(rows, start=1):
        url = item["url"]
        file_name = item["filename"] or _safe_filename(url, "fund_report", index)
        file_path = output_dir / file_name

        if file_path.exists() and not overwrite:
            skipped += 1
            continue

        try:
            request = Request(url, headers={"User-Agent": "DataMind/1.0 (+public-fund-analysis)"})
            with urlopen(request, timeout=timeout_seconds) as response:
                file_path.write_bytes(response.read())
            downloaded += 1
        except (URLError, HTTPError, ValueError):
            failed += 1

    return {
        "total": len(rows),
        "downloaded": downloaded,
        "skipped": skipped,
        "failed": failed,
    }
