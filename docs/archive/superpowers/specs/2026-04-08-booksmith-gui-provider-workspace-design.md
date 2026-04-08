# Booksmith GUI Provider And Workspace Refresh

## Context

The current Tk GUI works, but the workspace form is still too raw:

- `Input`, `Output`, `Provider`, and `Model` are not consistently bilingual.
- `Provider` and `Model` are free-text fields, which allows invalid combinations.
- There is no direct file picker for the source book.
- There is no first-class API key input for GUI users.
- `Output` is ambiguous to non-technical users because it currently looks like a file target rather than a workspace root.
- CLI and GUI share the same runtime services, but their configuration ergonomics have drifted.

The product goal is not to turn Booksmith into a giant desktop app. The goal is a restrained, clear, fast GUI for a simple job: select a book, choose a provider and model, supply credentials, and run the translation workflow with minimal confusion.

## Goals

1. Make the top-level workspace form bilingual and self-explanatory.
2. Replace provider/model free-text inputs with constrained, valid selections.
3. Add direct source-file picking for the input book.
4. Add an API key input flow that is safe by default.
5. Align CLI semantics with GUI semantics so both surfaces describe the same concepts the same way.
6. Preserve Tk startup speed and avoid unnecessary architectural churn.

## Non-Goals

- No frontend framework migration.
- No replacement of the existing Tk event/task pipeline.
- No fake support for providers that are not actually implemented.
- No silent persistence of secrets by default.
- No redesign of advanced publishing options in this slice beyond keeping the current collapsible section intact.

## User-Facing Decisions

### Workspace Labels

The workspace section will use bilingual field labels:

- `Input / 输入书籍`
- `Output / 输出目录`
- `Provider API / 服务商 API`
- `API Key / 密钥`
- `Model / 模型`

The section headings remain bilingual, but mojibake and broken localized strings must be eliminated from the Tk view layer.

### Input

`Input / 输入书籍` represents the source book path.

- The text field remains editable for direct path paste.
- A small `选择文件 / Browse` button sits to the right.
- File picker accepts `.pdf` and `.epub`.
- This slice does not add a mixed "file or folder" picker. Folder selection can be added later as a separate button if needed.

### Output

`Output / 输出目录` represents the workspace root directory where Booksmith writes run artifacts.

The GUI must explain that this is a directory, not a single exported file. A short helper line should clarify that this folder stores outputs like translated PDF, EPUB, TXT, summaries, and audit artifacts.

- The text field remains editable.
- A `选择目录 / Browse` button sits to the right.

### Provider API

`Provider API / 服务商 API` becomes a readonly dropdown backed by a provider catalog.

This slice only exposes providers that the backend can actually execute today:

- `Gemini / 谷歌 Gemini`
- `OpenAI / GPT`

The catalog structure must still be extensible so future providers such as `Zhipu / 智谱 AI` or `MiniMax / MiniMax` can be added without another GUI rewrite.

### API Key

The GUI gets a dedicated `API Key / 密钥` row below the provider selector.

It includes:

- A masked text entry by default
- A `显示` / `隐藏` toggle
- A `保存到本地 / Remember locally` checkbox

Secret handling policy:

- Default behavior: memory-only for the current run
- If the checkbox is enabled, persist the key to local `.env`
- Persistence is provider-specific and writes the correct env var for the selected provider
- If the checkbox is disabled, no local secret write occurs

### Model

`Model / 模型` becomes a readonly dropdown populated from the selected provider entry.

Rules:

- Switching provider refreshes the model list
- If the current model is no longer valid for the new provider, reset to that provider's default model
- Default model mapping:
  - Gemini -> `gemini-3.1-flash-lite-preview`
  - OpenAI -> `gpt-4o-mini`

## Architecture

### 1. Provider Catalog

Introduce a small GUI-facing provider catalog module or structure that owns:

- Provider id used by runtime services
- Bilingual display label
- API key environment variable name
- Supported model list
- Default model
- Enabled/implemented status

The GUI reads from this catalog rather than hardcoding provider strings across `views.py`, `app.py`, and `services.py`.

### 2. GUI State Expansion

Extend `GuiFormState` to include:

- `api_key: str`
- `persist_api_key: bool`

Do not store any "show/hide password" value in runtime request state. That is purely view-local.

### 3. Runtime Request Boundary

The GUI runtime request builder must support an explicit API key override for the current run.

Desired precedence:

1. API key entered in GUI for this run
2. Saved `.env`
3. Existing environment variable

This avoids forcing GUI users to preconfigure environment state just to run a one-off task.

### 4. Local Secret Persistence

Implement a tiny local secret writer for `.env` updates:

- If the file does not exist, create it
- If the provider env key exists, replace only that line
- Otherwise append the key
- Preserve unrelated `.env` lines

This is a GUI helper, not a general config migration system.

### 5. Output Semantics

The request-building and preview helpers stay directory-root oriented. No change to workspace layout or output path computation is needed. The improvement is clarity in GUI copy and selection affordances, not a filesystem redesign.

## CLI Alignment

CLI should align with GUI semantics, but not mimic GUI interaction patterns.

This slice aligns CLI in these ways:

1. Terminology alignment
- Treat `--output` consistently as an output directory/workspace root in help text and docs
- Keep `--provider` and `--model` semantics consistent with GUI labels

2. Provider/model constraints
- CLI validation should reject unsupported provider values using the same provider catalog source of truth, or a shared config mapping
- CLI default model behavior should remain provider-driven and explicit

3. API key semantics
- CLI keeps `--api-key-env`
- Add optional direct key input only if it can be done safely and cleanly
- If direct key input is added, it must be explicit, not a hidden side channel

The minimum requirement for this slice is semantic alignment, validation alignment, and help-text alignment. GUI-only affordances such as file pickers or show/hide toggles stay GUI-only.

## Design Review Notes

The GUI should remain visually restrained:

- Keep a single-column workspace form
- Use tighter label text and remove visual ambiguity, not decorative chrome
- Buttons for browse/toggle should be compact and secondary
- Avoid turning the provider area into a busy credential dashboard
- Keep the publishing advanced area collapsed by default

This is a utility app. Clarity beats novelty.

## Testing Plan

### Unit / Service Tests

- Provider catalog returns expected display labels, env vars, and models
- GUI validation accepts only implemented providers
- Runtime request builder prefers explicit GUI API key over `.env` / environment
- `.env` persistence updates only the selected provider key
- Model selection resets correctly when provider changes

### GUI Tests

- Workspace labels render bilingual text in the expected order
- Input row shows a browse button
- Output row shows a directory browse button
- Provider field is a readonly combobox
- Model field is a readonly combobox and updates when provider changes
- API key field is masked by default
- Show/hide toggle changes entry masking state
- Remember-locally checkbox state is captured

### Smoke / QA

- `python -m pytest -q`
- `python -m ruff check .`
- Tk smoke test: instantiate `BooksmithGui`, update widgets, destroy cleanly
- Manual smoke:
  - choose a PDF or EPUB via button
  - choose output directory via button
  - select Gemini and verify Gemini models appear
  - type an API key and toggle visibility
  - run once without persisting key
  - run once with persistence enabled and verify `.env` update

## Risks

### Secret Handling Risk

Writing `.env` incorrectly can clobber local developer state.

Mitigation:

- isolated helper with line-level replace/append behavior
- tests for create/update/preserve cases

### Startup Performance Risk

Adding complex provider logic directly into Tk construction could slow cold start.

Mitigation:

- keep provider catalog static and lightweight
- no network calls at startup
- no eager provider validation outside local config/state setup

### Drift Risk Between CLI And GUI

If GUI uses a private provider list while CLI uses a different mapping, the surfaces will diverge again.

Mitigation:

- prefer shared provider metadata in config or a shared helper module

## Recommendation

Implement this as a focused GUI-plus-config slice on the current branch.

The right level of ambition is:

- improve field clarity
- constrain provider/model selection
- add safe API key handling
- align CLI semantics

Do not expand into multi-step wizards or unsupported provider marketing in this round.
