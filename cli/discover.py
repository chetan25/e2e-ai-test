"""
Phase 1 CLI: Discover and generate initial test spec.
"""
import click
import json
import asyncio
from pathlib import Path
from typing import Optional
from cli.analyzer import analyze_repo
from cli.flow_mapper import map_ui_flows
from spec import Spec, Flow, FlowStep, APICall
import anthropic


@click.command()
@click.option('--repo', required=True, help='Path to repository')
@click.option('--app-url', required=True, help='Running app URL (http://localhost:3000)')
@click.option('--entry-point', default='/', help='App entry point URL')
@click.option('--output', default='spec.json', help='Output spec.json path')
def main(repo: str, app_url: str, entry_point: str, output: str):
    """
    Phase 1: Discover user flows from codebase and UI.
    
    1. Static analysis: Extract routes, components, APIs
    2. Dynamic crawl: Use Playwright to map UI interactions
    3. AI synthesis: Generate user journey flows
    4. Output: spec.json + generated test stubs
    """
    
    click.echo(f"🔍 Analyzing repository: {repo}")
    analysis = analyze_repo(repo)
    
    click.echo(f"  Routes found: {len(analysis.routes)}")
    click.echo(f"  Components: {len(analysis.components)}")
    click.echo(f"  API endpoints: {len(analysis.api_endpoints)}")
    click.echo(f"  External services: {', '.join(analysis.external_services) or 'None'}")
    
    click.echo(f"\n🕷️  Crawling UI at {app_url}")
    # Dynamic flow discovery via Playwright UI crawler
    from dataclasses import asdict
    flows = asyncio.run(map_ui_flows(app_url, asdict(analysis)))
    
    click.echo(f"  Discovered flows: {len(flows)}")
    
    # Use Claude to synthesize flows from static + dynamic analysis
    click.echo(f"\n🧠 Synthesizing flows with AI...")
    synthesized_flows = _synthesize_flows_with_ai(
        analysis=analysis,
        app_url=app_url
    )
    
    click.echo(f"  Generated {len(synthesized_flows)} flows")
    
    # Create spec
    spec = Spec()
    for flow in synthesized_flows:
        spec.flows[flow.id] = flow
    
    # Save spec.json
    spec_path = Path(output)
    spec.save(str(spec_path))
    click.echo(f"\n✅ Spec saved: {spec_path}")
    
    # Generate test stubs
    _generate_test_stubs(synthesized_flows, Path(repo))
    
    click.echo(f"✅ Initial setup complete!")
    click.echo(f"   Next: npm run dev && e2e-analyze-pr")


def _synthesize_flows_with_ai(analysis, app_url: str) -> list:
    """
    Use Claude to analyze codebase and generate user journey flows.
    """
    client = anthropic.Anthropic()
    
    prompt = f"""
    You are an E2E test expert. Analyze this web app structure and suggest 3-5 key user journey flows.
    
    App Structure:
    - Routes: {', '.join(analysis.routes[:10])}
    - Components: {', '.join(analysis.components[:10])}
    - API endpoints: {', '.join(analysis.api_endpoints[:5])}
    - External services: {', '.join(analysis.external_services)}
    - Entry point: {analysis.entry_point}
    
    Generate user flows in this JSON format:
    {{
      "flows": [
        {{
          "id": "flow_login",
          "name": "User logs in",
          "description": "User navigates to login page and authenticates",
          "steps": [
            {{"action": "navigate", "url": "/login"}},
            {{"action": "fill", "selector": "[data-testid='email']", "value": "user@test.com"}},
            {{"action": "fill", "selector": "[data-testid='password']", "value": "password"}},
            {{"action": "click", "selector": "[data-testid='submit']"}}
          ],
          "mocked_apis": [
            {{"url": "/api/auth/login", "method": "POST", "response": {{"success": true, "token": "xxx"}}}}
          ]
        }}
      ]
    }}
    
    Return ONLY valid JSON, no markdown or explanation.
    """
    
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    try:
        result = json.loads(response.content[0].text)
        flows = []
        for f in result.get('flows', []):
            flow = Flow(
                id=f['id'],
                name=f['name'],
                description=f.get('description', ''),
                steps=[FlowStep(**s) for s in f.get('steps', [])],
                mocked_apis=[APICall(**api) for api in f.get('mocked_apis', [])],
            )
            flows.append(flow)
        return flows
    except json.JSONDecodeError:
        click.echo("⚠️  Failed to parse AI response")
        return []


def _generate_test_stubs(flows, repo_path: Path):
    """Generate Playwright test stub files."""
    test_dir = repo_path / 'tests' / 'e2e'
    test_dir.mkdir(parents=True, exist_ok=True)
    
    for flow in flows:
        test_file = test_dir / f"{flow.id}.spec.ts"
        test_code = _generate_playwright_stub(flow)
        test_file.write_text(test_code)
    
    click.echo(f"  Generated {len(flows)} test files in tests/e2e/")


def _generate_playwright_stub(flow: Flow) -> str:
    """Generate a Playwright test stub for a flow."""
    return f"""import {{ test, expect }} from '@playwright/test';

test('{flow.name}', async ({{ page }}) => {{
  // TODO: Implement test for flow: {flow.id}
  // Steps:
{chr(10).join(f'  // - {step.action.title()}: {step.selector or step.url}' for step in flow.steps)}
  
  // Mock APIs:
{chr(10).join(f'  // - {api.method} {api.url}' for api in flow.mocked_apis)}
  
  // await page.goto('...');
  // await page.click('...');
  // await expect(...).toBeVisible();
}});
"""


if __name__ == '__main__':
    main()
