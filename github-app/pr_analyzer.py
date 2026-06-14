"""
Phase 2: Analyze PR diff and determine impact on existing flows.
"""
import anthropic
import json
from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class ImpactAnalysis:
    affected_flows: List[str]
    needs_new_tests: List[str]
    needs_updates: List[str]
    changed_files: List[str]
    reasoning: str


class PRAnalyzer:
    def __init__(self, repo_path: str, spec_json_path: str):
        self.repo_path = repo_path
        self.spec_json_path = spec_json_path
        self.client = anthropic.Anthropic()

    def analyze_diff(self, base_commit: str, pr_commit: str) -> ImpactAnalysis:
        """
        Analyze PR diff against baseline spec.
        Returns which flows are affected and what tests need updating.
        """
        
        # Get diff
        import subprocess
        diff_output = subprocess.run(
            ['git', 'diff', f'{base_commit}...{pr_commit}'],
            cwd=self.repo_path,
            capture_output=True,
            text=True
        ).stdout
        
        # Load spec
        with open(self.spec_json_path) as f:
            spec = json.load(f)
        
        # Load codebase structure
        codebase_summary = self._get_codebase_summary()
        
        # Use Claude to analyze
        prompt = f"""
        You are an E2E testing expert. Analyze this PR diff and determine test impact.
        
        PR Changes:
        ```
        {diff_output[:2000]}  # First 2000 chars of diff
        ```
        
        Baseline Flows (from spec.json):
        {json.dumps(spec.get('flows', {}), indent=2)[:1000]}
        
        Codebase Structure:
        {json.dumps(codebase_summary, indent=2)[:1000]}
        
        Determine:
        1. Which flows are affected by this change?
        2. Which flows need test updates?
        3. Do we need new tests for new flows?
        4. What changed in components/routes/APIs?
        
        Return JSON:
        {{
          "affected_flows": ["flow_id_1", "flow_id_2"],
          "needs_updates": ["flow_to_update"],
          "needs_new_tests": ["new_flow_name"],
          "changed_components": ["ComponentName"],
          "changed_routes": ["/route"],
          "reasoning": "explanation"
        }}
        """
        
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        try:
            result = json.loads(response.content[0].text)
            return ImpactAnalysis(
                affected_flows=result.get('affected_flows', []),
                needs_new_tests=result.get('needs_new_tests', []),
                needs_updates=result.get('needs_updates', []),
                changed_files=result.get('changed_components', []),
                reasoning=result.get('reasoning', '')
            )
        except json.JSONDecodeError:
            return ImpactAnalysis(
                affected_flows=[],
                needs_new_tests=[],
                needs_updates=[],
                changed_files=[],
                reasoning="Failed to parse AI response"
            )

    def _get_codebase_summary(self) -> Dict[str, Any]:
        """Get quick summary of codebase structure."""
        # Simplified version
        return {
            "main_routes": ["/", "/about", "/products"],
            "components": ["Header", "Footer", "ProductCard"],
            "api_endpoints": ["/api/products", "/api/checkout"]
        }


def analyze_pr(repo_path: str, base_commit: str, pr_commit: str, spec_path: str) -> ImpactAnalysis:
    """Main entry point for PR analysis."""
    analyzer = PRAnalyzer(repo_path, spec_path)
    return analyzer.analyze_diff(base_commit, pr_commit)
