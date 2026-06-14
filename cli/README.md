# Phase 1: Discovery

Analyze codebase architecture and crawl UI to extract user journey flows.

## Components

### `analyzer.py` — Static Code Analysis
- Extract routes and page components
- Identify API endpoints and external services
- Parse component structure
- Build dependency graph

### `flow_mapper.py` — Dynamic UI Crawling
- Uses Chrome DevTools MCP to navigate UI
- Records interactions: clicks, form fills, navigations
- Maps clickable elements to user actions
- Identifies user journeys

### `discover.py` — CLI Entry Point
```bash
e2e-discover init --repo . --app-url http://localhost:3000
```

## Output

Generates:
- `spec.json` — discovered flows (see spec.py schema)
- `tests/e2e/` — stub Playwright tests
- `.env.test` — mock API config

## Example spec.json

```json
{
  "version": "1.0",
  "flows": {
    "user_checkout": {
      "id": "user_checkout",
      "name": "User adds item and checks out",
      "steps": [
        {"action": "navigate", "url": "/products"},
        {"action": "click", "selector": "[data-testid='product-1']"},
        {"action": "click", "selector": "[data-testid='add-to-cart']"},
        {"action": "navigate", "url": "/cart"},
        {"action": "click", "selector": "[data-testid='checkout']"}
      ],
      "mocked_apis": [
        {
          "url": "https://api.payment.com/charge",
          "method": "POST",
          "response": {"status": "success"}
        }
      ]
    }
  }
}
```
