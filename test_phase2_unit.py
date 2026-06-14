"""
Unit tests for Phase 2 components with mocked Claude API.
Tests the structure and functionality without requiring API keys.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

sys.path.insert(0, str(Path(__file__).parent / "github-app"))

from pr_analyzer import PRAnalyzer, GitDiffParser, ImpactAnalysis
from test_updater import PlaywrightTestGenerator, generate_or_update_tests, _create_flow_from_spec
from spec import Flow, FlowStep, APICall


class TestDiffParser:
    """Test GitDiffParser without external dependencies."""

    def test_parse_selector_changes(self):
        """Test that selector changes are detected."""
        diff = """
- <button data-testid="btn-old">Click</button>
+ <button data-testid="btn-new">Click</button>
"""
        parser = GitDiffParser()
        result = parser.parse_diff(diff)
        assert len(result["selector_changes"]) > 0
        print("✅ Selector changes detected")

    def test_parse_component_changes(self):
        """Test component detection in TSX files."""
        diff = """
diff --git a/src/components/Header.tsx b/src/components/Header.tsx
- export default Header;
+ export function Header() { }
"""
        parser = GitDiffParser()
        result = parser.parse_diff(diff)
        assert result["files_changed"]
        assert "Header.tsx" in str(result["files_changed"])
        print("✅ Component changes detected")

    def test_parse_route_changes(self):
        """Test route detection."""
        diff = """
diff --git a/pages/products/index.tsx b/pages/products/index.tsx
 content here
"""
        parser = GitDiffParser()
        result = parser.parse_diff(diff)
        assert "pages/products/index.tsx" in result["files_changed"]
        print("✅ Route changes detected")

    def test_parse_api_changes(self):
        """Test API endpoint detection."""
        diff = """
- fetch('/api/v1/products')
+ fetch('/api/v2/products')
"""
        parser = GitDiffParser()
        result = parser.parse_diff(diff)
        assert len(result["api_changes"]) > 0
        assert "/api/v2/products" in result["api_changes"]
        print("✅ API changes detected")


class TestPlaywrightTestGeneration:
    """Test Playwright test generation."""

    def test_clean_code_removes_markdown(self):
        """Test that markdown wrappers are removed."""
        generator = PlaywrightTestGenerator()
        code_with_markdown = """```typescript
import { test } from '@playwright/test';
test('example', async ({ page }) => {});
```"""
        cleaned = generator._clean_code(code_with_markdown)
        assert not cleaned.startswith("```")
        assert not cleaned.endswith("```")
        assert "import" in cleaned
        print("✅ Markdown cleanup works")

    def test_format_steps(self):
        """Test step formatting for prompts."""
        steps = [
            FlowStep(action="navigate", url="/products"),
            FlowStep(action="click", data_testid="add-btn", value="test"),
            FlowStep(action="wait", selector="[loaded]")
        ]
        
        formatted = PlaywrightTestGenerator._format_steps(steps)
        assert "NAVIGATE" in formatted
        assert "CLICK" in formatted
        assert "WAIT" in formatted
        assert "products" in formatted
        print("✅ Step formatting works")

    def test_format_apis(self):
        """Test API formatting for prompts."""
        apis = [
            APICall(url="/api/users", method="GET", response={"users": []}),
            APICall(url="/api/posts", method="POST", response={"id": 1})
        ]
        
        formatted = PlaywrightTestGenerator._format_apis(apis)
        assert "/api/users" in formatted
        assert "/api/posts" in formatted
        assert "GET" in formatted
        assert "POST" in formatted
        print("✅ API formatting works")

    @patch('anthropic.Anthropic')
    def test_generate_test_code_structure(self, mock_anthropic):
        """Test that test generation produces valid-looking code."""
        # Mock Claude response
        mock_response = Mock()
        mock_response.content = [Mock(text="""import { test, expect } from '@playwright/test';

test('test_user_flow', async ({ page }) => {
  await page.goto('/products');
  await page.waitForSelector('[data-testid="product-list"]');
  await expect(page).toHaveTitle(/Products/);
});
""")]
        mock_anthropic.return_value.messages.create.return_value = mock_response

        generator = PlaywrightTestGenerator()
        flow = Flow(
            id="test_flow",
            name="Test Flow",
            description="Test",
            steps=[FlowStep(action="navigate", url="/products")],
            mocked_apis=[]
        )

        code = generator.generate_test_code(flow, "http://localhost:3000")

        assert "@playwright/test" in code
        assert "test(" in code or "test.describe" in code
        assert code.count("{") == code.count("}")
        print("✅ Generated test code structure is valid")

    @patch('anthropic.Anthropic')
    def test_mock_fixtures_structure(self, mock_anthropic):
        """Test that fixtures are properly formatted."""
        generator = PlaywrightTestGenerator()
        flows = [
            Flow(
                id="flow1",
                name="Flow 1",
                steps=[],
                mocked_apis=[
                    APICall(url="/api/data", method="GET", response={"data": []})
                ]
            )
        ]

        fixtures = generator.generate_mock_fixtures(flows)

        assert "@playwright/test" in fixtures
        assert "extend" in fixtures
        assert "mockApis" in fixtures
        assert "/api/data" in fixtures
        assert "GET" in fixtures
        print("✅ Fixtures structure is valid")


class TestFlowCreation:
    """Test flow creation from spec."""

    def test_create_flow_from_spec(self):
        """Test creating a flow from spec data."""
        spec = {
            "flows": {
                "test_flow": {
                    "id": "flow1",
                    "name": "Test Flow",
                    "description": "Description",
                    "steps": [
                        {
                            "action": "navigate",
                            "url": "/test"
                        }
                    ],
                    "mocked_apis": [
                        {
                            "url": "/api/test",
                            "method": "GET",
                            "response": {}
                        }
                    ],
                    "components_involved": ["Component"]
                }
            }
        }

        flow = _create_flow_from_spec("test_flow", spec)

        assert flow is not None
        assert flow.id == "flow1"
        assert flow.name == "Test Flow"
        assert len(flow.steps) == 1
        assert len(flow.mocked_apis) == 1
        print("✅ Flow created from spec")

    def test_create_flow_nonexistent(self):
        """Test that nonexistent flow returns None."""
        spec = {"flows": {}}
        flow = _create_flow_from_spec("nonexistent", spec)
        assert flow is None
        print("✅ Nonexistent flow returns None")


class TestImpactAnalysisDataclass:
    """Test ImpactAnalysis dataclass."""

    def test_impact_analysis_creation(self):
        """Test creating ImpactAnalysis."""
        impact = ImpactAnalysis(
            affected_flows=["flow1", "flow2"],
            needs_new_tests=["flow3"],
            needs_updates=["flow1"],
            changed_files=["file.tsx"],
            reasoning="Test changes",
            changed_apis=["/api/new"],
            changed_routes=["/new"]
        )

        assert len(impact.affected_flows) == 2
        assert len(impact.needs_updates) == 1
        assert len(impact.changed_apis) == 1
        assert impact.reasoning == "Test changes"
        print("✅ ImpactAnalysis dataclass works")


class TestGenerateOrUpdateTests:
    """Test the main generate_or_update_tests function."""

    @patch('anthropic.Anthropic')
    def test_generate_tests_output_structure(self, mock_anthropic):
        """Test the output structure of generate_or_update_tests."""
        # Mock Claude for test generation
        mock_response = Mock()
        mock_response.content = [Mock(text="""import { test } from '@playwright/test';
test('test', async ({ page }) => {});
""")]
        mock_anthropic.return_value.messages.create.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / "tests"
            
            spec = {
                "flows": {
                    "flow1": {
                        "id": "flow1",
                        "name": "Flow 1",
                        "description": "Test",
                        "steps": [{"action": "navigate", "url": "/"}],
                        "mocked_apis": []
                    }
                }
            }

            impact = {
                "affected_flows": ["flow1"],
                "needs_new_tests": ["flow1"],
                "needs_updates": [],
                "changed_files": [],
                "changed_routes": [],
                "changed_apis": [],
                "changed_selectors": {}
            }

            result = generate_or_update_tests(impact, spec, test_dir)

            assert isinstance(result, dict)
            assert "generated_tests" in result
            assert "updated_tests" in result
            assert "fixtures_created" in result
            assert "errors" in result
            assert isinstance(result["errors"], list)
            print("✅ generate_or_update_tests output structure is correct")


class TestPRAnalyzer:
    """Test PRAnalyzer with mocked Claude."""

    @patch('anthropic.Anthropic')
    def test_pr_analyzer_initialization(self, mock_anthropic):
        """Test PRAnalyzer initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_file = Path(tmpdir) / "spec.json"
            spec_file.write_text(json.dumps({"flows": {}}))

            analyzer = PRAnalyzer(tmpdir, str(spec_file))
            
            assert analyzer.repo_path == tmpdir
            assert analyzer.spec_json_path == str(spec_file)
            assert isinstance(analyzer.diff_parser, GitDiffParser)
            print("✅ PRAnalyzer initialization works")

    @patch('anthropic.Anthropic')
    def test_parse_analysis_response(self, mock_anthropic):
        """Test parsing Claude's analysis response."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_file = Path(tmpdir) / "spec.json"
            spec_file.write_text(json.dumps({"flows": {}}))

            analyzer = PRAnalyzer(tmpdir, str(spec_file))
            
            response_text = """{
                "affected_flows": ["flow1"],
                "needs_updates": ["flow1"],
                "needs_new_tests": [],
                "reasoning": "Component changed"
            }"""

            result = analyzer._parse_analysis_response(response_text)

            assert result.affected_flows == ["flow1"]
            assert result.needs_updates == ["flow1"]
            assert result.reasoning == "Component changed"
            print("✅ Analysis response parsing works")


if __name__ == "__main__":
    import traceback

    tests = [
        TestDiffParser(),
        TestPlaywrightTestGeneration(),
        TestFlowCreation(),
        TestImpactAnalysisDataclass(),
        TestGenerateOrUpdateTests(),
        TestPRAnalyzer(),
    ]

    total = 0
    passed = 0

    for test_class in tests:
        for method_name in dir(test_class):
            if method_name.startswith("test_"):
                total += 1
                try:
                    method = getattr(test_class, method_name)
                    method()
                    passed += 1
                except Exception as e:
                    print(f"❌ {test_class.__class__.__name__}.{method_name}")
                    traceback.print_exc()

    print(f"\n{'='*60}")
    print(f"Results: {passed}/{total} tests passed")
    print(f"{'='*60}")
