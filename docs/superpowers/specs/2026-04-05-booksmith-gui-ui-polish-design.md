# Booksmith GUI UI Polish Design

## Summary

Refine the local `Booksmith` desktop GUI into a calmer, cleaner, performance-first single-page workspace. Keep the existing Tkinter/ttk stack and all current runtime semantics intact. Improve layout hierarchy, bilingual labeling, option density, and result presentation so the GUI feels like a focused desktop tool rather than a rough form wrapper.

This spec covers UI structure and interaction polish only. It does not include the previously deferred subprojects for independent reviewer/arbiter integration, stronger source-aware image and layout recovery, or the future editorial review interface.

## Goals

- Make the GUI visually restrained, clean, and efficient.
- Keep startup and interaction performance effectively unchanged.
- Preserve CLI and GUI as parallel entry points with identical pipeline behavior.
- Keep novice usage simple by surfacing only the most common controls by default.
- Preserve full access to existing workflows without introducing a wizard or multiple windows.

## Non-Goals

- No technology change away from Tkinter/ttk.
- No new translation or publishing features.
- No new reviewer / arbiter functionality.
- No manual review UI.
- No file picker redesign in this iteration.
- No multi-language toggle; instead use bilingual copy in one interface.

## Design Direction

The GUI should feel like a quiet desktop utility:

- restrained, not decorative
- compact, but not dense
- fast to scan
- obvious primary action
- clear status and results

Visual quality comes from hierarchy, spacing, and reduced noise rather than heavy color, extra chrome, or card overload.

## Information Architecture

The application remains a single window with one vertical flow. The page is reorganized into five sections:

1. Header
2. Core configuration
3. Output and advanced options
4. Run status
5. Results and logs

This keeps the most common path obvious:

1. choose input/output
2. choose mode and model
3. optionally adjust output settings
4. run
5. open results

## Section Layout

### 1. Header

The header contains:

- product name: `Booksmith`
- one short Chinese primary subtitle
- one shorter English secondary subtitle

The header should not read like a welcome screen. It should behave like a title bar companion: concise and quiet.

### 2. Core Configuration

This section contains the fields most users actually need:

- input path
- output path
- mode
- provider
- model

The current “Mode” radio buttons stay, but the section is visually integrated into the same work surface as the rest of the core fields rather than feeling like a separate heavy card.

### 3. Output And Advanced Options

This section is split into:

- visible default output behavior summary
- common output toggles
- collapsible advanced publishing area

Default visible controls:

- render polished PDF
- also export PDF
- also export EPUB

Publishing-only advanced controls remain available but hidden behind an explicit “高级选项 / Advanced” expander that is collapsed by default.

The expander must not create a new window or modal. It expands inline.

### 4. Run Status

This section becomes tighter and more action-oriented. It contains:

- one primary run button
- current status
- current stage
- progress bar
- short summary text

The status area should prioritize only the most important run information. Detailed metrics continue to flow into the summary and logs rather than competing visually with the primary state.

### 5. Results And Logs

Results become more prominent than logs after completion.

Results:

- output folder
- run summary
- translated txt
- translated pdf
- translated epub
- final audit report

Logs:

- remain visible
- remain scrollable
- stay visually quieter than result actions

The result controls should only appear when the corresponding artifact exists.

## Bilingual Copy Strategy

The GUI uses bilingual labels without introducing language switching.

Rules:

- Chinese is primary.
- English is secondary.
- English appears smaller and visually lighter.
- Do not duplicate every explanatory sentence in equal weight.
- Use dual-language text only where it improves clarity.

Examples:

- `工作区` with `Workspace` as a smaller secondary label
- `输入文件 / Input`
- `开始翻译 / Run`

Header and section titles use stacked hierarchy. Field labels can use compact inline bilingual form.

## Visual Rules

### Spacing

- Increase consistency of outer padding and vertical rhythm.
- Reduce the feeling that each block is an unrelated form box.
- Keep enough whitespace to feel calm without wasting vertical space.

### Typography

- Use the default Tk stack for performance and portability.
- Rely on size, weight, and spacing changes rather than custom fonts.
- Title text is larger and bold.
- Section titles are medium emphasis.
- Secondary English text is smaller and quieter.

### Color And Contrast

- Keep the palette neutral and minimal.
- Avoid bright accent colors except where the OS or ttk theme already applies them naturally.
- Keep logs and helper text visually subdued.

### Borders And Chrome

- Reduce unnecessary framed-card heaviness.
- Keep enough grouping to orient the user.
- Do not add decorative containers or ornamental separators.

## Interaction Behavior

### Advanced Options

- Hidden by default.
- Inline expand/collapse only.
- Available when publishing mode is active.
- The collapsed state should reduce clutter for first-time users.

### Run Button

- Single primary action only.
- Disabled while a run is active.
- Re-enabled on completion or failure.

### Status Behavior

The run area highlights:

- current status
- current stage
- total progress

Secondary numbers such as chunk counts, failures, elapsed time, and estimated cost stay in the summary text and/or result summary rather than being promoted into separate high-contrast widgets.

### Error Behavior

- Errors should continue to appear inline in status and logs.
- No new modal-heavy error UX in this iteration.

### Results Behavior

- Hidden or de-emphasized until useful.
- Become the main post-run action area once a run completes.
- Preserve current open-path behavior.

## Implementation Constraints

- Keep Tkinter/ttk.
- Do not change GUI runtime request semantics.
- Do not change CLI behavior.
- Do not move pipeline logic into the view layer.
- Limit code changes mostly to `src/booksmith/gui/views.py` and small glue changes in `src/booksmith/gui/app.py`.
- Keep tests focused on structure and behavior rather than pixel-specific assertions.

## Files Expected To Change

- `H:\AI_Apps\booksmith\src\booksmith\gui\views.py`
- `H:\AI_Apps\booksmith\src\booksmith\gui\app.py`
- `H:\AI_Apps\booksmith\tests\test_gui_app.py`
- potentially a new focused view test file if needed, likely under `H:\AI_Apps\booksmith\tests\`
- README only if GUI screenshots or wording need minor alignment after implementation

## Verification Plan

### Automated

- Existing GUI tests continue to pass.
- Add or update tests for:
  - default collapsed advanced area
  - visible section structure
  - bilingual title or section labels
  - result action visibility rules
  - run-state button enable/disable behavior

### Manual Smoke Checks

- launch `python -m booksmith.gui`
- launch `booksmith-gui`
- verify engineering mode layout
- verify publishing mode layout
- verify advanced area collapse/expand
- verify run state still updates without layout breakage

## Success Criteria

This spec is considered successfully implemented when:

- the GUI remains fast and stable
- the window feels visibly calmer and more intentional
- the most common path is obvious without reading dense instructions
- publishing options no longer overwhelm default usage
- results are easier to access after completion
- no pipeline behavior regresses
