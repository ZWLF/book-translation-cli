from __future__ import annotations

from pathlib import Path


def test_build_gui_script_resolves_repo_root_from_scripts_directory() -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "build-gui-exe.ps1"
    script = script_path.read_text(encoding="utf-8")

    assert '$repoRoot = Split-Path -Parent $PSScriptRoot' in script
    assert 'Set-Location -LiteralPath $repoRoot' in script
    assert '"--specpath", "$workPath"' in script
    assert '--paths", "$repoRoot\\src"' in script
    assert '$pyiArgs += "$repoRoot\\src\\booksmith\\gui\\__main__.py"' in script
