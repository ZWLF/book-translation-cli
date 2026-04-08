from __future__ import annotations

from pathlib import Path

from booksmith.provider_catalog import get_provider_option


def save_provider_api_key(env_path: Path, *, provider: str, api_key: str) -> None:
    _validate_single_line_api_key(api_key)
    option = get_provider_option(provider)
    target_key = option.api_key_env

    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    updated_lines: list[str] = []
    replaced = False

    for line in lines:
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            updated_lines.append(line)
            continue

        name, _value = line.split("=", 1)
        if name.strip() == target_key:
            updated_lines.append(f"{target_key}={api_key}")
            replaced = True
        else:
            updated_lines.append(line)

    if not replaced:
        updated_lines.append(f"{target_key}={api_key}")

    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")


def _validate_single_line_api_key(api_key: str) -> None:
    if "\n" in api_key or "\r" in api_key:
        raise ValueError("API key must be a single line.")
