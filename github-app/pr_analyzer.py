"""
Phase 2: Analyze PR diff and determine impact on existing flows.
"""
import anthropic
import json
import subprocess
import re
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ImpactAnalysis:
    affected_flows: List[str]
    needs_new_tests: List[str]
    needs_updates: List[str]
    changed_files: List[str]
    reasoning: str
    changed_selectors: Dict[str, List[str]] = field(default_factory=dict)
    changed_routes: List[str] = field(default_factory=list)
    changed_apis: List[str] = field(default_factory=list)


class GitDiffParser:
    """Parse git diffs to extract meaningful change information."""

    @staticmethod
    def parse_diff(diff_output: str) -> Dict[str, Any]:
        """Parse git diff output and extract patterns."""
        changes = {
            "files_changed": [],
            "lines_added": 0,
            "lines_removed": 0,
            "component_changes": [],
            "route_changes": [],
            "api_changes": [],
            "selector_changes": [],
            "raw_diff": diff_output[:2000]  # First 2000 chars for Claude
        }

        current_file = None
        for line in diff_output.split('\n'):
            # Track files
            if line.startswith("diff --git"):
                match = re.search(r'b/(.*?)$', line)
                if match:
                    current_file = match.group(1)
                    changes["files_changed"].append(current_file)

            # Count additions/removals
            if line.startswith('+') and not line.startswith('+++'):
                changes["lines_added"] += 1
            elif line.startswith('-') and not line.startswith('---'):
                changes["lines_removed"] += 1

            # Detect component changes (TSX/JSX)
            if current_file and ('.tsx' in current_file or '.jsx' in current_file):
                if line.startswith('-') and 'export' in line:
                    comp = re.search(r'export\s+(?:default\s+)?(?:const|function)?\s+(\w+)', line)
                    if comp:
                        changes["component_changes"].append(comp.group(1))

            # Detect route changes
            if current_file and 'route' in current_file.lower():
                if 'pages/' in current_file:
                    route = current_file.replace('pages/', '/').replace('.tsx', '').replace('.jsx', '')
                    changes["route_changes"].append(route)

            # Detect API changes
            if line.startswith('-') or line.startswith('+'):
                api_match = re.search(r'["\'](/api/[a-zA-Z0-9/_-]+)["\']', line)
                if api_match:
                    changes["api_changes"].append(api_match.group(1))

            # Detect selector changes (data-testid, className, id)
            if line.startswith('-') and ('data-testid' in line or 'className' in line or 'id=' in line):
                selector_match = re.search(r'["\']([^"\']+)["\']', line)
                if selector_match:
                    changes["selector_changes"].append(selector_match.group(1))

        return changes

    @staticmethod
    def get_git_diff(repo_path: str, base_commit: str, pr_commit: str) -> str:
        """Get git diff between two commits."""
        try:
            result = subprocess.run(
                ['git', 'diff', f'{base_commit}...{pr_commit}'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.stdout
        except subprocess.TimeoutExpired:
            return ""
        except Exception as e:
            print(f"Error getting git diff: {e}")
            return ""


class PRAnalyzer:
    def __init__(self, repo_path: str, spec_json_path: str):
        self.repo_path = repo_path
        self.spec_json_path = spec_json_path
        self.client = anthropic.Anthropic()
        self.diff_parser = GitDiffParser()

    def analyze_diff(self, base_commit: str, pr_commit: str) -> ImpactAnalysis:
        """
        Analyze PR diff against baseline spec.
        Returns which flows are affected and what tests need updating.
        """

        # Get and parse diff
        diff_output = self.diff_parser.get_git_diff(
            self.repo_path, base_commit, pr_commit
        )
        parsed_diff = self.diff_parser.parse_diff(diff_output)

        # Load spec
        try:
            with open(self.spec_json_path) as f:
                spec = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            spec = {"flows": {}}

        # Get codebase structure
        codebase_summary = self._get_codebase_summary()

        # Use Claude to analyze impact
        prompt = self._build_analysis_prompt(parsed_diff, spec, codebase_summary)

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )

            result = self._parse_analysis_response(response.content[0].text)
            
            # Enhance with diff-based detection
            result.changed_routes = parsed_diff.get("route_changes", [])
            result.changed_apis = parsed_diff.get("api_changes", [])
            result.changed_selectors = {"removed": parsed_diff.get("selector_changes", [])}
            
            return result
        except Exception as e:
            print(f"Error during analysis: {e}")
            return ImpactAnalysis(
                affected_flows=[],
                needs_new_tests=[],
                needs_updates=[],
                changed_files=parsed_diff.get("files_changed", []),
                reasoning=f"Analysis error: {str(e)}"
            )

    def _build_analysis_prompt(self, parsed_diff: Dict[str, Any], spec: Dict[str, Any], 
                              codebase_summary: Dict[str, Any]) -> str:
        """Build the Claude prompt for impact analysis."""
        return f"""You are an E2E testing expert. Analyze this PR diff and determine test impact.

PR Changes Summary:
- Files changed: {', '.join(parsed_diff.get('files_changed', [])[:10])}
- Components affected: {', '.join(parsed_diff.get('component_changes', []))}
- Routes affected: {', '.join(parsed_diff.get('route_changes', []))}
- APIs affected: {', '.join(parsed_diff.get('api_changes', []))}
- Selectors removed: {', '.join(parsed_diff.get('selector_changes', [])[:5])}
- Lines: +{parsed_diff['lines_added']} -{parsed_diff['lines_removed']}

Raw diff (first 1500 chars):
```
{parsed_diff['raw_diff'][:1500]}
```

Baseline Flows:
{json.dumps(spec.get('flows', {}), indent=2)[:1000]}

Codebase Structure:
{json.dumps(codebase_summary, indent=2)}

Task: Determine which flows are affected and what action is needed.

Return JSON:
{{
  "affected_flows": ["flow_id_1", "flow_id_2"],
  "needs_updates": ["flow_to_update"],
  "needs_new_tests": ["new_flow"],
  "reasoning": "explanation of impact"
}}

Return ONLY valid JSON, no markdown or extra text."""

    def _parse_analysis_response(self, response_text: str) -> ImpactAnalysis:
        """Parse Claude's analysis response."""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = json.loads(response_text)

            return ImpactAnalysis(
                affected_flows=result.get('affected_flows', []),
                needs_new_tests=result.get('needs_new_tests', []),
                needs_updates=result.get('needs_updates', []),
                changed_files=result.get('changed_components', []),
                reasoning=result.get('reasoning', 'Analysis completed')
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
        summary = {
            "main_routes": ["/", "/about", "/products"],
            "components": ["Header", "Footer", "ProductCard"],
            "api_endpoints": ["/api/products", "/api/checkout"]
        }

        # Try to scan actual codebase
        try:
            repo_path = Path(self.repo_path)
            
            # Find components
            components = set()
            for tsx_file in repo_path.glob("**/*.tsx"):
                components.add(tsx_file.stem)
            summary["components"] = list(components)[:20]

            # Find routes
            routes = set()
            pages_dir = repo_path / "pages" or repo_path / "src" / "pages"
            if pages_dir.exists():
                for page in pages_dir.glob("**/*.tsx"):
                    route = str(page.relative_to(pages_dir)).replace('.tsx', '')
                    routes.add('/' + route.replace('index', ''))
            summary["main_routes"] = list(routes)[:20]

        except Exception:
            pass

        return summary


def analyze_pr(repo_path: str, base_commit: str, pr_commit: str, spec_path: str) -> ImpactAnalysis:
    """Main entry point for PR analysis."""
    analyzer = PRAnalyzer(repo_path, spec_path)
    return analyzer.analyze_diff(base_commit, pr_commit)
