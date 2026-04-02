from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(slots=True)
class RenderedPage:
    page_number: int
    output_path: str
    width: int
    height: int


def parse_page_spec(spec: str, *, total_pages: int) -> list[int]:
    pages: set[int] = set()
    for raw_part in spec.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", maxsplit=1)
            start = int(start_text.strip())
            end = int(end_text.strip())
            if start > end:
                raise ValueError(f"Invalid page range: {part}")
            pages.update(range(start, end + 1))
            continue
        pages.add(int(part))

    if not pages:
        raise ValueError("No pages selected.")

    invalid = sorted(page for page in pages if page < 1 or page > total_pages)
    if invalid:
        raise ValueError(f"Page numbers out of range: {invalid}")
    return sorted(pages)


def choose_sample_pages(total_pages: int) -> list[int]:
    if total_pages < 1:
        return []
    if total_pages <= 12:
        return list(range(1, total_pages + 1))

    pages = {
        1,
        2,
        3,
        4,
        5,
        total_pages // 2,
        (total_pages // 2) + 1,
        total_pages - 2,
        total_pages - 1,
        total_pages,
    }
    return sorted(page for page in pages if 1 <= page <= total_pages)


def pdf_page_count(pdf_path: Path) -> int:
    fitz = _import_fitz()
    with fitz.open(str(pdf_path)) as document:
        return document.page_count


def render_pdf_pages(
    *,
    pdf_path: Path,
    output_dir: Path,
    pages: list[int],
    dpi: int = 144,
) -> list[RenderedPage]:
    fitz = _import_fitz()
    if dpi < 72:
        raise ValueError("dpi must be at least 72")

    output_dir.mkdir(parents=True, exist_ok=True)
    scale = dpi / 72
    matrix = fitz.Matrix(scale, scale)
    rendered: list[RenderedPage] = []

    with fitz.open(str(pdf_path)) as document:
        for page_number in pages:
            page = document.load_page(page_number - 1)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            output_path = output_dir / f"page-{page_number:03d}.png"
            pixmap.save(str(output_path))
            rendered.append(
                RenderedPage(
                    page_number=page_number,
                    output_path=str(output_path),
                    width=pixmap.width,
                    height=pixmap.height,
                )
            )
    return rendered


def write_qa_summary(
    *,
    pdf_path: Path,
    summary_path: Path,
    output_dir: Path,
    total_pages: int,
    rendered_pages: list[RenderedPage],
    dpi: int,
) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(
            {
                "pdf_path": str(pdf_path),
                "output_dir": str(output_dir),
                "total_pages": total_pages,
                "rendered_pages": [page.page_number for page in rendered_pages],
                "dpi": dpi,
                "artifacts": [asdict(page) for page in rendered_pages],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _import_fitz():
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF is required for PDF page rasterization. Install project dependencies first."
        ) from exc
    return fitz
