param(
    [switch]$OneFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root

$python = "python"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$workPath = Join-Path $root "build\gui_build_$stamp"
$tmpDistPath = Join-Path $root "dist\_tmp_gui_$stamp"
$finalDistPath = Join-Path $root "dist"

Write-Host "[Booksmith] Building GUI EXE with PyInstaller..."

$pyiArgs = @(
    "--noconfirm",
    "--clean",
    "--windowed",
    "--exclude-module", "PyQt5",
    "--exclude-module", "PyQt6",
    "--exclude-module", "PySide2",
    "--exclude-module", "PySide6",
    "--name", "Booksmith-GUI",
    "--workpath", "$workPath",
    "--distpath", "$tmpDistPath",
    "--paths", "$root\src"
)

if ($OneFile) {
    $pyiArgs += "--onefile"
} else {
    # Default to onedir for much faster cold start than onefile unpacking.
    $pyiArgs += "--onedir"
}

$pyiArgs += "$root\src\booksmith\gui\__main__.py"

try {
    & $python -m PyInstaller @pyiArgs

    New-Item -ItemType Directory -Path $finalDistPath -Force | Out-Null
    if ($OneFile) {
        Copy-Item -LiteralPath (Join-Path $tmpDistPath "Booksmith-GUI.exe") -Destination (Join-Path $finalDistPath "Booksmith-GUI.exe") -Force
        Write-Host "[Booksmith] Build complete: $finalDistPath\Booksmith-GUI.exe"
    } else {
        $finalBundlePath = Join-Path $finalDistPath "Booksmith-GUI"
        if (Test-Path $finalBundlePath) {
            Remove-Item -LiteralPath $finalBundlePath -Recurse -Force
        }
        Copy-Item -LiteralPath (Join-Path $tmpDistPath "Booksmith-GUI") -Destination $finalDistPath -Recurse -Force
        Write-Host "[Booksmith] Build complete: $finalBundlePath\Booksmith-GUI.exe"
    }
} finally {
    if (Test-Path $tmpDistPath) {
        Remove-Item -LiteralPath $tmpDistPath -Recurse -Force
    }
    if (Test-Path $workPath) {
        Remove-Item -LiteralPath $workPath -Recurse -Force
    }
}
