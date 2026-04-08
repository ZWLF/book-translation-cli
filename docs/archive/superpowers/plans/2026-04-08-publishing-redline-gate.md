# Publishing Redline Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add hard publishing redline checks so candidate outputs cannot be promoted when obvious translation and typesetting defects remain.

**Architecture:** Extend the publishing validation layer with content-aware redline checks over candidate text and chapter metadata, then feed those blocker counts into the release gate. Keep the first slice intentionally narrow: markdown residue, orphan numeric lines, English-only body residue, and English-only chapter titles.

**Tech Stack:** Python 3.11+, existing `booksmith` publishing pipeline, `pytest`.

---

### Task 1: Define Redline Validation In Tests

**Files:**
- Modify: `H:\AI_Apps\booksmith\tests\test_validation.py`
- Modify: `H:\AI_Apps\booksmith\tests\test_release_gate.py`
- Modify: `H:\AI_Apps\booksmith\tests\test_publishing_pipeline.py`

- [ ] Write focused failing tests for:
  - markdown residue such as `**title**` and `***`
  - orphan numeric lines such as standalone `42`
  - pure-English body lines that are not reference entries
  - pure-English chapter titles in `final_chapters.jsonl`
  - release gate failure when redline blockers are present
  - publishing pipeline gate report persisting redline counts

- [ ] Run the focused tests and verify they fail for the expected reasons.

### Task 2: Implement Content-Aware Publishing Validation

**Files:**
- Modify: `H:\AI_Apps\booksmith\src\booksmith\publishing\validation.py`
- Modify: `H:\AI_Apps\booksmith\src\booksmith\models.py`

- [ ] Add a publishing redline validator that reads candidate text and chapter metadata.
- [ ] Return a structured report with counts and blocker records.
- [ ] Keep heuristics conservative by allowing English reference lines while blocking English body residue.

- [ ] Run validation tests and verify they pass.

### Task 3: Wire Redline Checks Into The Release Gate

**Files:**
- Modify: `H:\AI_Apps\booksmith\src\booksmith\publishing\release_gate.py`
- Modify: `H:\AI_Apps\booksmith\src\booksmith\publishing\pipeline.py`

- [ ] Extend `PublishingGateInputs` with redline blocker counts.
- [ ] Fail the hard gate when any redline blockers exist.
- [ ] Replace the current hard-coded score floor with a penalty-based estimate derived from real issue counts.
- [ ] Persist the redline validation report into `final_gate_report.json`.

- [ ] Run release gate and publishing pipeline tests and verify they pass.

### Task 4: Verify The Slice End-To-End

**Files:**
- No new files expected.

- [ ] Run:

```powershell
python -m pytest H:\AI_Apps\booksmith\tests\test_validation.py H:\AI_Apps\booksmith\tests\test_release_gate.py H:\AI_Apps\booksmith\tests\test_publishing_pipeline.py -q
```

- [ ] Run:

```powershell
python -m pytest -q
```

- [ ] Summarize what this slice now blocks, and what still needs later work:
  - bilingual title completion
  - citation styling and blue footnote markers
  - PDF whitespace and layout-specific QA
