# Booksmith Rename Design

## Summary

This design fully renames the product from `book-translation-cli` / `Book Translator` to `Booksmith`. The rename is not cosmetic. It covers the GitHub repository, local project directory, Python package namespace, CLI command, GUI entry point, README set, documentation, and visible product labels. The old name is not kept as an alias.

The rename must be completed in a controlled order so the project remains buildable and testable throughout the migration. Code-level and packaging-level changes are completed first inside the current repository checkout, then verified, then pushed and merged, and only after that are the GitHub repository name and local filesystem directory renamed.

## Goals

- Replace every user-facing primary name with `Booksmith`.
- Replace every code-facing primary namespace with `booksmith`.
- Remove public use of the old CLI and module names rather than keeping compatibility aliases.
- Keep CLI and GUI as parallel entry points after the rename.
- Preserve all existing engineering, publishing, PDF, EPUB, GUI, and audit capabilities.

## Non-Goals

- No workflow redesign beyond what the rename requires.
- No simultaneous implementation of the later reviewer-hardening and publication-polish subprojects.
- No backward-compatibility layer for `book-translator`, `book-translator-gui`, `book_translator`, or `book-translation-cli`.

## Problem Statement

The current product name was chosen when the project was only a CLI translator. It no longer fits the product:

- the project now has both CLI and GUI entry points
- it supports engineering and publishing workflows
- it produces polished PDF and EPUB outputs
- it includes source-aware review, deep-review, gate reports, and QA artifacts

`Booksmith` better matches the current product direction. To avoid a half-renamed system, this migration must be complete and consistent across packaging, imports, docs, repo naming, and local paths.

## Recommended Approach

### Option A: Full hard cut

Rename all layers in one coordinated migration and do not preserve the old names.

Pros:
- cleanest long-term identity
- no dual-name maintenance burden
- easiest for documentation and onboarding once complete

Cons:
- broad change surface
- every entry point and import path must be updated correctly

### Option B: Product-name-only rename

Update GUI, docs, and branding to `Booksmith` while keeping `book_translator` and `book-translator` internally.

Pros:
- smaller code diff

Cons:
- directly conflicts with the requirement for a full rename
- leaves permanent product/code mismatch

### Option C: Compatibility transition

Add new `Booksmith` names while keeping the old commands and module names for a deprecation window.

Pros:
- lowest migration risk for existing users

Cons:
- directly conflicts with the requirement to avoid old aliases
- prolongs the rename rather than finishing it

### Recommendation

Use Option A. The user explicitly wants a full hard cut with no compatibility aliases.

## Scope

### Product and documentation names

Rename visible product references from variants of `Book Translation CLI`, `Book Translator`, and `book-translation-cli` to `Booksmith`.

This includes:

- `README.md`
- `README.zh-CN.md`
- `README.ja.md`
- GUI window title and display labels
- packaging metadata strings
- future-facing docs that identify the product by name

### Python package and module namespace

Rename the package directory:

- `src/book_translator` -> `src/booksmith`

Update all imports accordingly:

- `book_translator.*` -> `booksmith.*`

Update module entry points accordingly:

- `python -m book_translator` -> `python -m booksmith`
- `python -m book_translator.gui` -> `python -m booksmith.gui`

### CLI and GUI commands

Rename scripts:

- `book-translator` -> `booksmith`
- `book-translator-gui` -> `booksmith-gui`

No old command aliases remain.

### Packaging metadata

Update `pyproject.toml` so the package metadata reflects the new product:

- project name: `booksmith`
- script entry points: `booksmith`, `booksmith-gui`
- descriptive text updated to `Booksmith`

Generated `egg-info` metadata should also move to the new package name after reinstall/build.

### Repository and local directory names

After code and documentation changes are complete and merged:

- GitHub repository rename:
  - `ZWLF/book-translation-cli` -> `ZWLF/booksmith`
- local directory rename:
  - `H:\AI_Apps\book-translation-cli` -> `H:\AI_Apps\booksmith`

This is intentionally deferred until after the code-level rename is verified.

## Migration Order

### Phase 1: Code and packaging rename inside the current repo path

Perform the full code rename while still working in the existing local directory and existing GitHub repository.

Changes include:

- package directory rename
- import updates
- `pyproject.toml` updates
- CLI command updates
- GUI entry point updates
- README and docs updates
- tests updated to new commands and module paths

### Phase 2: Local verification

Before touching the repository name or local directory path, verify:

- `python -m booksmith`
- `booksmith`
- `python -m booksmith.gui`
- `booksmith-gui`
- `ruff`
- `pytest`

The codebase must be stable while still located in the old path.

### Phase 3: Push, PR, and merge

Push the rename branch, open a PR, fix CI if needed, and merge to `main`.

### Phase 4: GitHub repository rename

Rename the GitHub repository to `ZWLF/booksmith`.

After this step, links in docs and version notes should point to the new repository URL.

### Phase 5: Local project directory rename

Rename the local directory to:

- `H:\AI_Apps\booksmith`

Then verify the project still runs from the renamed directory.

## File Structure

### Modify

- `pyproject.toml`
- `README.md`
- `README.zh-CN.md`
- `README.ja.md`
- CLI and GUI tests that reference old commands or old module names
- docs that identify the project by the old name
- code files across `src/book_translator` once moved into the new package path

### Rename

- `src/book_translator` -> `src/booksmith`
- `src/book_translation_cli.egg-info` will be regenerated under the new name after install/build

### Verify references

Search for and eliminate public or code-facing references to:

- `book-translation-cli`
- `Book Translation CLI`
- `Book Translator`
- `book-translator`
- `book-translator-gui`
- `book_translator`

Any remaining references must be either historical documentation explicitly explaining the rename, or generated paths that will disappear after reinstall.

## Risks And Mitigations

### Risk: import breakage after package rename

Mitigation:

- update imports systematically
- run full `pytest`
- run real module-entry commands, not only unit tests

### Risk: stale generated metadata or editable-install confusion

Mitigation:

- reinstall the project after renaming package metadata
- verify generated script entry points are updated

### Risk: docs and code drift

Mitigation:

- scan for old-name references before claiming completion
- update all command examples and module examples

### Risk: repo/path rename breaks local tooling

Mitigation:

- perform repo and local path rename only after merge
- re-run smoke verification from the renamed local directory

## Testing Strategy

### Unit and integration verification

- existing test suite must pass after the package rename
- GUI smoke tests must pass under the new module path
- CLI tests must pass under the new command names

### Command verification

Run and verify:

- `python -m booksmith --help`
- `booksmith --help`
- `python -m booksmith.gui`
- `booksmith-gui`

### Reference scan

Before final completion, scan the repo for the old names and resolve all active references.

### Post-rename repository verification

After GitHub repo rename and local directory rename:

- verify `git remote -v` points to the new repository URL
- verify the project runs from `H:\AI_Apps\booksmith`

## Acceptance Criteria

The rename is complete only if all of the following are true:

- project metadata identifies the product as `Booksmith`
- the Python package namespace is `booksmith`
- CLI command is `booksmith`
- GUI command is `booksmith-gui`
- GUI module entry is `python -m booksmith.gui`
- README and multilingual docs use `Booksmith`
- GitHub repository is `ZWLF/booksmith`
- local project directory is `H:\AI_Apps\booksmith`
- no public old-name aliases remain
- tests and command-entry verification pass
