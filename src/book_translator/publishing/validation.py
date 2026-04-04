from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile


def validate_primary_output(path: Path, output_kind: str) -> dict[str, object]:
    if output_kind == "pdf":
        exists = path.exists()
        size = path.stat().st_size if exists else 0
        return {
            "passed": exists and size > 0,
            "kind": "pdf",
            "path": str(path),
            "reason": None if exists and size > 0 else "missing_or_empty_file",
            "size_bytes": size,
        }
    if output_kind == "epub":
        return validate_epub_output(path)
    raise ValueError(f"Unsupported output kind: {output_kind}")


def validate_epub_output(path: Path) -> dict[str, object]:
    if not path.exists():
        return {
            "passed": False,
            "kind": "epub",
            "path": str(path),
            "reason": "missing_file",
            "missing": [],
        }

    with ZipFile(path) as archive:
        names = set(archive.namelist())

    required = {
        "mimetype",
        "META-INF/container.xml",
        "OEBPS/content.opf",
        "OEBPS/nav.xhtml",
    }
    missing = sorted(required - names)
    return {
        "passed": not missing,
        "kind": "epub",
        "path": str(path),
        "reason": "missing_entries" if missing else None,
        "missing": missing,
    }


def summarize_visual_blockers(blockers: list[dict[str, object]]) -> dict[str, object]:
    return {
        "visual_blocker_count": len(blockers),
        "blockers": blockers,
    }
