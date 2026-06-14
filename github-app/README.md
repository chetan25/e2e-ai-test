# Phase 2: PR Analysis & Test Maintenance

Analyze pull requests, detect affected flows, generate/update tests, run and report.

## Components

### `pr_analyzer.py` — PR Diff Analysis
Uses Claude to analyze what changed and impact on existing flows.

### `impact_detector.py` — Flow Impact Detection
Determines which flows are affected by the PR changes.

### `test_updater.py` — Test Generation/Update
Generates new tests or updates existing ones based on impact analysis.

### `github-action/` — GitHub Integration
- `action.yml` — GitHub Action definition
- `webhook.py` — Webhook handler for PR events

## Flow

```
PR Opened
  ↓
Read diff, spec.json, codebase
  ↓
Claude analyzes impact
  ↓
Detect affected flows
  ↓
Generate/update Playwright tests
  ↓
Run tests
  ↓
Comment PR with results
  ↓
Merge → Run full suite
```
