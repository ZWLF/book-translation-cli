from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path

import tiktoken


def slugify(value: str) -> str:
    slug = re.sub(r"[^\w\-]+", "-", value.strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or "book"


def file_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.resolve().as_posix().encode("utf-8"))
    stat = path.stat()
    digest.update(str(stat.st_mtime_ns).encode("utf-8"))
    digest.update(str(stat.st_size).encode("utf-8"))
    return digest.hexdigest()


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def estimate_tokens(text: str, model: str | None = None) -> int:
    if not text.strip():
        return 0
    try:
        encoding = tiktoken.encoding_for_model(model or "gpt-4o-mini")
        return len(encoding.encode(text))
    except Exception:
        return max(1, math.ceil(word_count(text) / 0.75))
