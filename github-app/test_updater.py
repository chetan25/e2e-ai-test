"""
Phase 2: Generate or update Playwright tests based on impact analysis.
"""
import anthropic
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from spec import Flow, FlowStep, APICall


class PlaywrightTestGenerator:
    def __init__(self):
        self.client = anthropic.Anthropic()

    def generate_test_code(self, flow: Flow, app_url: str) -> str:
        """
        Generate Playwright test code for a flow using Claude.
        Returns syntactically correct TypeScript code.
        """

        prompt = f"""Generate a Playwright test for this user flow. IMPORTANT: Return ONLY valid TypeScript code.

Flow ID: {flow.id}
Flow Name: {flow.name}
Description: {flow.description or 'User interaction flow'}

Steps to automate:
{self._format_steps(flow.steps)}

Mocked APIs:
{self._format_apis(flow.mocked_apis)}

Requirements:
- Use @playwright/test
- Use data-testid selectors where possible
- Mock external APIs with route interception
- Include proper wait conditions (waitForLoadState, waitForSelector)
- Add descriptive test name based on flow
- Include before/after hooks if needed
- Use baseURL from fixtures
- Proper error handling and assertions

Generate ONLY the test code - no markdown, no explanations. Start with imports.
Make it ready to run immediately."""

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}]
        )

        test_code = response.content[0].text

        # Clean up markdown if present
        test_code = self._clean_code(test_code)

        return test_code

    def update_existing_test(self, old_code: str, flow: Flow, 
                            changes: Dict[str, Any]) -> str:
        """
        Update an existing test based on PR changes.
        """

        prompt = f"""Update this Playwright test to handle the following changes. Return ONLY valid TypeScript code.

Current test:
```typescript
{old_code[:1500]}
```

Changes in PR:
- Modified selectors/components: {', '.join(changes.get('changed_selectors', {}).get('removed', [])[:5])}
- Modified routes: {', '.join(changes.get('changed_routes', [])[:5])}
- Modified APIs: {', '.join(changes.get('changed_apis', [])[:5])}

Flow steps (updated):
{self._format_steps(flow.steps)}

Update the test to:
1. Use new selectors if components changed
2. Update navigation paths if routes changed
3. Update mock responses if APIs changed
4. Keep test structure and pass rate

Return ONLY the updated test code - no markdown or explanations."""

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}]
        )

        test_code = response.content[0].text
        return self._clean_code(test_code)

    def generate_mock_fixtures(self, flows: List[Flow]) -> str:
        """
        Generate Playwright fixtures for API mocking.
        """

        api_calls = set()
        for flow in flows:
            for api in flow.mocked_apis:
                api_calls.add((api.url, api.method, json.dumps(api.response)))

        fixture_code = """import { test as base, expect } from '@playwright/test';

export const test = base.extend({
  mockApis: async ({ page }, use) => {
    const interceptedRequests: string[] = [];
"""

        for url, method, response in api_calls:
            # Create safe mock response
            url_pattern = url.replace('/', '\\/')

            fixture_code += f"""
    // Mock {method} {url}
    await page.route('*/**{url}/**', async route => {{
      interceptedRequests.push('{url}');
      if (route.request().method() === '{method}') {{
        await route.abort('blockedbyclient');
      }}
    }});"""

        fixture_code += """

    await use(page);
    console.log('Intercepted requests:', interceptedRequests);
  },
});

export { expect } from '@playwright/test';
"""

        return fixture_code

    @staticmethod
    def _format_steps(steps: List[FlowStep]) -> str:
        """Format flow steps for prompt."""
        formatted = []
        for i, step in enumerate(steps, 1):
            selector = step.selector or step.data_testid or step.url or 'N/A'
            formatted.append(
                f"{i}. {step.action.upper()}: {selector}"
            )
            if step.value:
                formatted.append(f"   Value: {step.value}")
        return "\n".join(formatted)

    @staticmethod
    def _format_apis(apis: List[APICall]) -> str:
        """Format APIs for prompt."""
        if not apis:
            return "None"
        formatted = []
        for api in apis:
            formatted.append(
                f"- {api.method} {api.url} → {json.dumps(api.response)[:100]}"
            )
        return "\n".join(formatted)

    @staticmethod
    def _clean_code(code: str) -> str:
        """Clean up code output (remove markdown wrapper)."""
        # Remove markdown code blocks if present
        code = re.sub(r'^```typescript\n?', '', code)
        code = re.sub(r'^```ts\n?', '', code)
        code = re.sub(r'^```\n?', '', code)
        code = re.sub(r'\n?```$', '', code)
        return code.strip()


def generate_or_update_tests(
    impact_analysis: Dict[str, Any],
    spec_json: Dict[str, Any],
    test_dir: Path,
    app_url: str = "http://localhost:3000"
) -> Dict[str, Any]:
    """
    Main entry point: generate new tests or update existing ones.
    Returns report with generated/updated test files.
    """

    gen = PlaywrightTestGenerator()
    result = {
        "generated_tests": [],
        "updated_tests": [],
        "fixtures_created": False,
        "errors": []
    }

    # Ensure test directory exists
    test_dir.mkdir(parents=True, exist_ok=True)

    # Generate new tests
    for flow_name in impact_analysis.get('needs_new_tests', []):
        try:
            flow = _create_flow_from_spec(flow_name, spec_json)
            if flow:
                test_code = gen.generate_test_code(flow, app_url)
                test_file = test_dir / f"{flow.id}.spec.ts"
                test_file.write_text(test_code)
                result["generated_tests"].append(str(test_file))
            else:
                result["errors"].append(f"Could not create flow: {flow_name}")
        except Exception as e:
            result["errors"].append(f"Error generating test for {flow_name}: {str(e)}")

    # Update existing tests
    for flow_name in impact_analysis.get('needs_updates', []):
        try:
            test_file = test_dir / f"{flow_name}.spec.ts"
            if test_file.exists():
                old_code = test_file.read_text()
                
                # Get updated flow
                flow = _create_flow_from_spec(flow_name, spec_json)
                if not flow:
                    flow = Flow(
                        id=flow_name,
                        name=flow_name,
                        description="",
                        steps=[]
                    )
                
                updated_code = gen.update_existing_test(
                    old_code, flow, impact_analysis
                )
                test_file.write_text(updated_code)
                result["updated_tests"].append(str(test_file))
            else:
                result["errors"].append(f"Test file not found: {test_file}")
        except Exception as e:
            result["errors"].append(f"Error updating test for {flow_name}: {str(e)}")

    # Generate fixtures if we have flows
    all_flows = impact_analysis.get('needs_new_tests', []) + impact_analysis.get('needs_updates', [])
    if all_flows:
        try:
            flows_to_mock = [
                _create_flow_from_spec(fname, spec_json)
                for fname in all_flows
            ]
            flows_to_mock = [f for f in flows_to_mock if f]

            if flows_to_mock:
                fixtures_code = gen.generate_mock_fixtures(flows_to_mock)
                fixtures_file = test_dir / "fixtures.ts"
                fixtures_file.write_text(fixtures_code)
                result["fixtures_created"] = True
        except Exception as e:
            result["errors"].append(f"Error generating fixtures: {str(e)}")

    return result


def _create_flow_from_spec(flow_name: str, spec: Dict[str, Any]) -> Optional[Flow]:
    """Extract or create a flow definition from spec."""
    flow_data = spec.get('flows', {}).get(flow_name)
    if not flow_data:
        return None

    try:
        steps = []
        for s in flow_data.get('steps', []):
            if isinstance(s, dict):
                steps.append(FlowStep(**s))
            else:
                steps.append(s)

        apis = []
        for a in flow_data.get('mocked_apis', []):
            if isinstance(a, dict):
                apis.append(APICall(**a))
            else:
                apis.append(a)

        return Flow(
            id=flow_data.get('id', flow_name),
            name=flow_data.get('name', flow_name),
            description=flow_data.get('description', ''),
            steps=steps,
            mocked_apis=apis,
            components_involved=flow_data.get('components_involved', [])
        )
    except Exception as e:
        print(f"Error creating flow {flow_name}: {e}")
        return None
