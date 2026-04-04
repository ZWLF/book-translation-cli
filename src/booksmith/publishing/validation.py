from __future__ import annotations

from pathlib import Path
from posixpath import normpath
from xml.etree import ElementTree as ET
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
