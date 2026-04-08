from __future__ import annotations

import json
import re
from pathlib import Path
from posixpath import normpath
from xml.etree import ElementTree as ET
from zipfile import ZipFile

_REFERENCE_LINE_RE = re.compile(r"^\s*\d{2,4}\s+\S")
_URL_LINE_RE = re.compile(r"^\s*(?:https?://|www\.)\S+\s*$", re.IGNORECASE)
_TRAILING_REFERENCE_RE = re.compile(r"\s\d{2,4}[.)]?\s*$")
_REFERENCE_QUOTE_RE = re.compile(r"[\"“”‘’鈥]")
_REFERENCE_KEYWORD_RE = re.compile(
    r"\b(?:podcast|blog|speech|conference|interview|account|youtube|commencement|combinator)\b",
    re.IGNORECASE,
)
_ASCII_LETTER_RE = re.compile(r"[A-Za-z]")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_MARKDOWN_DECORATION_RE = re.compile(
    r"(^|[\s\"“”'‘’(\[])"
    r"(?P<marker>\*\*|__)"
    r"(?=\S)"
    r".+?"
    r"(?<=\S)(?P=marker)"
    r"(?=$|[\s\"“”'‘’).,!?:;\]])"
)


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
        missing = _validate_epub_archive(archive=archive, names=names)

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


def validate_publishing_redlines(
    *,
    text_path: Path,
    chapters_path: Path | None = None,
) -> dict[str, object]:
    blockers: list[dict[str, object]] = []
    markdown_artifact_count = 0
    orphan_numeric_line_count = 0
    english_body_line_count = 0
    english_title_line_count = 0

    if text_path.exists():
        for line_number, raw_line in enumerate(
            text_path.read_text(encoding="utf-8", errors="replace").splitlines(),
            start=1,
        ):
            line = raw_line.strip()
            if not line:
                continue
            if _has_markdown_artifact(line):
                markdown_artifact_count += 1
                blockers.append(
                    {
                        "type": "markdown_artifact",
                        "line_number": line_number,
                        "line": line,
                    }
                )
                continue
            if _is_orphan_numeric_line(line):
                orphan_numeric_line_count += 1
                blockers.append(
                    {
                        "type": "orphan_numeric_line",
                        "line_number": line_number,
                        "line": line,
                    }
                )
                continue
            if _is_english_body_line(line):
                english_body_line_count += 1
                blockers.append(
                    {
                        "type": "english_body_line",
                        "line_number": line_number,
                        "line": line,
                    }
                )

    if chapters_path and chapters_path.exists():
        for chapter_index, title in enumerate(_load_chapter_titles(chapters_path), start=1):
            if not _is_english_only_line(title):
                continue
            english_title_line_count += 1
            blockers.append(
                {
                    "type": "english_title_line",
                    "chapter_index": chapter_index,
                    "line": title,
                }
            )

    return {
        "passed": not blockers,
        "path": str(text_path),
        "chapters_path": str(chapters_path) if chapters_path else None,
        "blocker_count": len(blockers),
        "markdown_artifact_count": markdown_artifact_count,
        "orphan_numeric_line_count": orphan_numeric_line_count,
        "english_body_line_count": english_body_line_count,
        "english_title_line_count": english_title_line_count,
        "blockers": blockers,
    }


def _validate_epub_archive(*, archive: ZipFile, names: set[str]) -> list[str]:
    missing: list[str] = []
    required = {"mimetype", "META-INF/container.xml"}
    missing.extend(sorted(required - names))
    if missing:
        return missing

    rootfile_path = _read_rootfile_path(archive=archive)
    if rootfile_path is None:
        return ["META-INF/container.xml"]

    if rootfile_path not in names:
        missing.append(rootfile_path)
        return missing

    nav_path = _read_nav_path(archive=archive, rootfile_path=rootfile_path)
    if nav_path is None:
        missing.append(f"{_rootfile_parent(rootfile_path)}/nav.xhtml")
        return missing

    if nav_path not in names:
        missing.append(nav_path)

    return missing


def _read_rootfile_path(*, archive: ZipFile) -> str | None:
    try:
        container_xml = archive.read("META-INF/container.xml")
    except KeyError:
        return None

    try:
        root = ET.fromstring(container_xml)
    except ET.ParseError:
        return None

    namespace = {"container": "urn:oasis:names:tc:opendocument:xmlns:container"}
    rootfile = root.find("container:rootfiles/container:rootfile", namespace)
    if rootfile is None:
        return None

    full_path = (rootfile.attrib.get("full-path") or "").strip()
    return full_path or None


def _read_nav_path(*, archive: ZipFile, rootfile_path: str) -> str | None:
    try:
        opf = archive.read(rootfile_path)
    except KeyError:
        return None

    try:
        root = ET.fromstring(opf)
    except ET.ParseError:
        return None

    namespace = {"opf": "http://www.idpf.org/2007/opf"}
    manifest_items = root.findall("opf:manifest/opf:item", namespace)
    for item in manifest_items:
        properties = (item.attrib.get("properties") or "").split()
        if "nav" not in properties:
            continue
        href = (item.attrib.get("href") or "").strip()
        if not href:
            continue
        return _resolve_zip_path(rootfile_path, href)
    return None


def _resolve_zip_path(rootfile_path: str, href: str) -> str:
    package_root = _rootfile_parent(rootfile_path)
    if package_root:
        return normpath(f"{package_root}/{href}")
    return normpath(href)


def _rootfile_parent(path: str) -> str:
    parent = str(Path(path).parent).replace("\\", "/")
    return "" if parent == "." else parent


def _has_markdown_artifact(line: str) -> bool:
    stripped = line.strip()
    if stripped == "***":
        return True
    return _MARKDOWN_DECORATION_RE.search(stripped) is not None


def _is_orphan_numeric_line(line: str) -> bool:
    return line.isdigit()


def _is_english_body_line(line: str) -> bool:
    return _is_english_only_line(line) and not _is_reference_like_line(line)


def _is_english_only_line(line: str) -> bool:
    return bool(_ASCII_LETTER_RE.search(line)) and not bool(_CJK_RE.search(line))


def _is_reference_like_line(line: str) -> bool:
    stripped = line.strip()
    if _REFERENCE_LINE_RE.match(stripped):
        return True
    if _URL_LINE_RE.match(stripped):
        return True
    if _TRAILING_REFERENCE_RE.search(stripped) is not None:
        return True
    if _REFERENCE_KEYWORD_RE.search(stripped):
        return True
    if _REFERENCE_QUOTE_RE.search(stripped) and "," in stripped and stripped.endswith("."):
        return True
    return False


def _load_chapter_titles(path: Path) -> list[str]:
    titles: list[str] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        title = str(
            payload.get("translated_title")
            or payload.get("title")
            or ""
        ).strip()
        if title:
            titles.append(title)
    return titles
