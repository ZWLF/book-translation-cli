from __future__ import annotations

import json
from pathlib import Path


def load_manual_toc_titles(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Manual TOC file must be a JSON list.")
    titles: list[str] = []
    for item in data:
        if isinstance(item, str):
            titles.append(item.strip())
        elif isinstance(item, dict) and "title" in item:
            titles.append(str(item["title"]).strip())
        else:
            raise ValueError("Manual TOC entries must be strings or objects with a title field.")
    return [title for title in titles if title]
