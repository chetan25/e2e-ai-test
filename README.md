# E2E AI Test

AI-driven end-to-end testing platform that automatically discovers user flows, generates Playwright tests, and maintains test coverage across pull requests.

## Features

- **Phase 1: Discovery** — Analyze codebase architecture and crawl UI to discover user flows
- **Phase 2: PR Integration** — Auto-detect affected flows, generate/update tests on every PR
- **Intelligent Test Maintenance** — AI detects real regressions vs flaky selectors
- **spec.json Baseline** — Living documentation of all tested flows and coverage

## Quick Start

### Installation

```bash
pip install -e .
```

### Phase 1: Initial Flow Discovery

```bash
e2e-discover init \
  --repo /path/to/app \
  --app-url http://localhost:3000 \
  --entry-point /src/pages
```

This generates:
- `spec.json` — discovered flows baseline
- `tests/e2e/` — Playwright test files
- `.env.test` — mock API configuration

### Phase 2: GitHub Integration

Configure workflow in `.github/workflows/e2e-ai.yml`:

```yaml
on: [pull_request]
jobs:
  e2e-ai-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: e2e-ai-test/github-action@v1
        with:
          app-url: "http://localhost:3000"
```

## Architecture

```
Phase 1: Discovery (CLI)
├── Static Analysis → Extract routes, components, API calls
├── Chrome DevTools MCP → Crawl UI, map interactions
└── Synthesis → Generate user journey flows

Phase 2: PR Analysis (GitHub Action)
├── Diff Analysis → What changed?
├── Impact Detection → Which flows affected?
├── Test Generation/Update → Auto-update tests
└── Run & Report → Comment results on PR
```

## Project Structure

```
e2e-ai-test/
├── cli/
│   ├── discover.py          # CLI entry point
│   ├── analyzer.py          # Static code analysis
│   ├── flow_mapper.py       # Dynamic UI crawling via Chrome DevTools MCP
│   └── test_runner.py       # Execute Playwright tests
├── codegen/
│   ├── playwright_gen.py    # Generate Playwright test code
│   ├── test_updater.py      # Update existing tests
│   └── templates/           # Playwright test templates
├── github-app/
│   ├── pr_analyzer.py       # Analyze PR diffs
│   ├── impact_detector.py   # Detect affected flows
│   ├── action.yml           # GitHub Action definition
│   └── webhook.py           # GitHub webhook handler
├── spec.py                  # spec.json schema & utilities
├── tests/                   # Unit tests
└── setup.py
```

## Development

```bash
# Install in dev mode
pip install -e ".[dev]"

# Run tests
pytest

# Build for release
python setup.py sdist bdist_wheel
```

## License

MIT
