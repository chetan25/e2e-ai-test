"""
Phase 2: Generate or update Playwright tests based on impact analysis.
"""
import anthropic
import json
import re
from pathlib import Path
from typing import Dict, List, Any
from spec import Flow, FlowStep, APICall


class PlaywrightTestGenerator:
    def __init__(self):
        self.client = anthropic.Anthropic()

    def generate_test_code(self, flow: Flow, app_url: str) -> str:
        """
        Generate Playwright test code for a flow using Claude.
        """
        
        prompt = f"""
        Generate a Playwright test for this user flow. Use modern best practices:
        - Use data-testid for selectors
        - Include proper wait conditions
        - Mock external APIs via fixtures
        - Clear test documentation
        
        Flow: {flow.name}
        Description: {flow.description}
        
        Steps:
        {chr(10).join(f'  - {s.action}: {s.selector or s.url}' for s in flow.steps)}
        
        Mocks:
        {chr(10).join(f'  - {a.method} {a.url}' for a in flow.mocked_apis)}
        
        Generate the test as a TypeScript string with:
        - Proper imports from @playwright/test
        - test() function named after flow ID
        - Before/after hooks for setup/teardown
        - Clear assertions
        
        Return ONLY the TypeScript code, no markdown formatting.
        """
        
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text

    def update_existing_test(self, old_code: str, changes: Dict[str, Any]) -> str:
        """
        Update an existing test based on PR changes.
        """
        
        prompt = f"""
        Update this Playwright test to handle the following changes:
        
        Current test:
        ```typescript
        {old_code}
        ```
        
        Changes in PR:
        {json.dumps(changes, indent=2)[:500]}
        
        Keep the test structure but update:
        - Selectors if components changed
        - Mock responses if APIs changed
        - Navigation paths if routes changed
        - Add new steps if flows changed
        
        Return the updated test code, no markdown formatting.
        """
        
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text

    def generate_mock_fixtures(self, flows: List[Flow]) -> str:
        """
        Generate Playwright fixtures for API mocking.
        """
        
        api_calls = set()
        for flow in flows:
            for api in flow.mocked_apis:
                api_calls.add((api.url, api.method))
        
        fixture_code = """import { test as base } from '@playwright/test';

export const test = base.extend({
  mockApis: async ({ page }, use) => {
    // Intercept and mock external API calls
"""
        
        for url, method in api_calls:
            fixture_code += f"""
    await page.route('**/{re.escape(url)}/**', route => {{
      if (route.request().method() === '{method}') {{
        route.abort('blockedbyclient');
      }}
    }});
"""
        
        fixture_code += """
    await use(page);
  },
});

export { expect } from '@playwright/test';
"""
        
        return fixture_code


def generate_or_update_tests(
    impact_analysis: Dict[str, Any],
    spec_json: Dict[str, Any],
    test_dir: Path,
    app_url: str
) -> List[str]:
    """
    Main entry point: generate new tests or update existing ones.
    Returns list of generated/updated test files.
    """
    
    gen = PlaywrightTestGenerator()
    test_files = []
    
    # Generate new tests
    for flow_name in impact_analysis.get('needs_new_tests', []):
        # Create flow from spec or generate new
        flow = _create_flow_from_spec(flow_name, spec_json)
        if flow:
            test_code = gen.generate_test_code(flow, app_url)
            test_file = test_dir / f"{flow.id}.spec.ts"
            test_file.write_text(test_code)
            test_files.append(str(test_file))
    
    # Update existing tests
    for flow_name in impact_analysis.get('needs_updates', []):
        test_file = test_dir / f"{flow_name}.spec.ts"
        if test_file.exists():
            old_code = test_file.read_text()
            updated_code = gen.update_existing_test(old_code, impact_analysis)
            test_file.write_text(updated_code)
            test_files.append(str(test_file))
    
    return test_files


def _create_flow_from_spec(flow_name: str, spec: Dict[str, Any]) -> Flow:
    """Extract or create a flow definition."""
    flow_data = spec.get('flows', {}).get(flow_name)
    if not flow_data:
        return None
    
    return Flow(
        id=flow_data.get('id', flow_name),
        name=flow_data.get('name', flow_name),
        description=flow_data.get('description', ''),
        steps=[FlowStep(**s) for s in flow_data.get('steps', [])],
        mocked_apis=[APICall(**a) for a in flow_data.get('mocked_apis', [])]
    )
