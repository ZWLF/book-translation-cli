from __future__ import annotations


def normalize_lexicon_records(records: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for record in records:
        source = record.get("source", "").strip()
        translation = record.get("translation", "").strip()
        if not source or not translation:
            continue

        item = (source, translation)
        if item in seen:
            continue

        seen.add(item)
        normalized.append({"source": source, "translation": translation})

    return normalized


def merge_lexicon_overrides(generated: dict[str, str], overrides: dict[str, str]) -> dict[str, str]:
    merged = {
        str(key): str(value).strip()
        for key, value in generated.items()
        if str(value).strip()
    }
    for key, value in overrides.items():
        cleaned_value = str(value).strip()
        if not cleaned_value:
            continue
        merged[str(key)] = cleaned_value
    return merged
