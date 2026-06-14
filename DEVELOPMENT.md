# E2E AI Test v0.1.0

## Phases Implemented

### ✅ Phase 1: Discovery (scaffold complete)
- `cli/analyzer.py` — Static code analysis
- `cli/flow_mapper.py` — Chrome DevTools MCP integration (skeleton)
- `cli/discover.py` — CLI entry point with AI synthesis
- `spec.py` — Spec schema

### ✅ Phase 2: PR Analysis (scaffold complete)
- `github-app/pr_analyzer.py` — PR diff analysis with Claude
- `github-app/test_updater.py` — Generate/update Playwright tests
- `.github/workflows/e2e-ai.yml` — GitHub Action workflow

## Next Steps

1. **Integrate Chrome DevTools MCP** into `flow_mapper.py`
2. **Test Phase 1 discovery** on a real Next.js/React app
3. **Refine test generation** with real Playwright patterns
4. **Deploy GitHub Action** and test on PRs
5. **Add fallback handling** for flaky selectors

## Development

```bash
# Install
pip install -e .

# Phase 1: Discover flows
e2e-discover init --repo /path/to/app --app-url http://localhost:3000

# Phase 2: GitHub Action (runs automatically on PR)
```

## Architecture Notes

- AI components use Claude 3.5 Sonnet for analysis
- Spec format: JSON with flows, mocks, coverage metadata
- Tests: Playwright with data-testid selectors and API mocking
- No code mocking; all flows are user journey tests
