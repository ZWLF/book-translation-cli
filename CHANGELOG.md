# Changelog

All notable changes to this project are documented in this file.

The format is based on Keep a Changelog and uses project version `MAJOR.MINOR.PATCH.MICRO`.

## [Unreleased]

### Added
- Redline publishing validation that blocks release when English-only chapter titles, raw markdown markers, or orphan numeric reference lines leak into candidate outputs.
- Structured title synchronization so translated Part and Chapter overrides propagate into rebuilt TXT, EPUB, and release-gate inputs.
- Source-aware audit coverage for wrapper lines, reference-heavy tails, and structured output numbering regressions.

### Changed
- Publishing repair and audit stages now normalize synthetic wrapper text more conservatively and avoid promoting false 9.x scores for candidate books with visible output defects.
- Release gating now factors real blocker counts into final promotion decisions and aligns gate scores with observable output quality.

## [0.1.1.0] - 2026-04-08

### Added
- Publishing redline blockers for markdown residue, pure-English body leaks, English-only chapter titles, and orphan numeric lines.
- Title override propagation across rebuilt publishing outputs and gate snapshots.
- Regression tests for structure cleanup, reference-tail audits, validation edge cases, and structured output assembly.

### Changed
- Source audit now tolerates reference-heavy tails and wrapper-intro noise without misclassifying them as omissions.
- Structure normalization now strips prompt-wrapper metadata, preserves single-line body text, and repairs local ordered numbering more predictably.

## [0.1.0.0] - 2026-04-06

### Added
- Initial public baseline for Booksmith CLI and GUI workflows.
- Engineering and publishing translation pipelines.
- Windows GUI launchers and EXE build script.

### Changed
- GUI startup path optimized with lazy-loading and fast onedir packaging defaults.
