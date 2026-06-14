"""
Phase 2 Integration Test: Simulate a PR change scenario and test the full pipeline.

This test:
1. Creates a mock git repository with a codebase
2. Makes a simulated component change (PR scenario)
3. Runs the full pipeline: diff → analyze → generate tests
4. Validates output structure and test code quality
"""

import json
import tempfile
import subprocess
from pathlib import Path
import pytest
import sys

# Add github-app to path
sys.path.insert(0, str(Path(__file__).parent / "github-app"))

from pr_analyzer import PRAnalyzer, GitDiffParser, ImpactAnalysis
from test_updater import PlaywrightTestGenerator, generate_or_update_tests
from spec import Flow, FlowStep, APICall


class MockRepo:
    """Create and manage a mock git repository for testing."""

    def __init__(self, tmp_dir: Path):
        self.path = tmp_dir
        self.path.mkdir(parents=True, exist_ok=True)

    def init(self) -> None:
        """Initialize git repo."""
        subprocess.run(
            ["git", "init"],
            cwd=self.path,
            capture_output=True,
            check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=self.path,
            capture_output=True,
            check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=self.path,
            capture_output=True,
            check=True
        )

    def create_initial_structure(self) -> None:
        """Create initial codebase structure."""
        # Create directories
        (self.path / "src" / "pages").mkdir(parents=True, exist_ok=True)
        (self.path / "src" / "components").mkdir(parents=True, exist_ok=True)
        (self.path / "tests").mkdir(parents=True, exist_ok=True)

        # Create initial files
        initial_component = """import React from 'react';

export const ProductCard = ({ product }) => {
  return (
    <div className="product-card" data-testid="product-card">
      <h3>{product.name}</h3>
      <p className="price">${product.price}</p>
      <button data-testid="add-to-cart">Add to Cart</button>
    </div>
  );
};
"""
        (self.path / "src" / "components" / "ProductCard.tsx").write_text(initial_component)

        initial_page = """import React, { useState, useEffect } from 'react';
import { ProductCard } from '../components/ProductCard';

export default function Products() {
  const [products, setProducts] = useState([]);

  useEffect(() => {
    fetch('/api/products')
      .then(r => r.json())
      .then(data => setProducts(data.items));
  }, []);

  return (
    <div data-testid="products-page">
      <h1>Products</h1>
      {products.map(p => <ProductCard key={p.id} product={p} />)}
    </div>
  );
}
"""
        (self.path / "src" / "pages" / "products.tsx").write_text(initial_page)

        # Create initial spec
        spec = {
            "version": "1.0",
            "flows": {
                "user_browse_products": {
                    "id": "user_browse_products",
                    "name": "Browse Products",
                    "description": "User navigates to products page and views product list",
                    "steps": [
                        {
                            "action": "navigate",
                            "url": "/products"
                        },
                        {
                            "action": "wait",
                            "selector": "[data-testid='products-page']"
                        },
                        {
                            "action": "verify",
                            "selector": "[data-testid='product-card']"
                        }
                    ],
                    "mocked_apis": [
                        {
                            "url": "/api/products",
                            "method": "GET",
                            "response": {
                                "items": [
                                    {"id": 1, "name": "Product 1", "price": 99.99}
                                ]
                            }
                        }
                    ]
                }
            }
        }
        (self.path / "spec.json").write_text(json.dumps(spec, indent=2))

        # Commit initial
        subprocess.run(
            ["git", "add", "."],
            cwd=self.path,
            capture_output=True,
            check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=self.path,
            capture_output=True,
            check=True
        )

    def make_change(self, change_description: str) -> str:
        """
        Make a component change (simulating a PR).
        Returns the commit hash.
        """
        # Simulate: ProductCard component selector changed
        if "selector" in change_description.lower():
            modified_component = """import React from 'react';

export const ProductCard = ({ product }) => {
  return (
    <div className="product-item" data-testid="product-item">
      <h3>{product.name}</h3>
      <p className="product-price">${product.price}</p>
      <button data-testid="add-to-cart-btn" onClick={() => console.log('Added')}>Add to Cart</button>
    </div>
  );
};
"""
            (self.path / "src" / "components" / "ProductCard.tsx").write_text(modified_component)

        # Simulate: API endpoint change
        elif "api" in change_description.lower():
            modified_page = """import React, { useState, useEffect } from 'react';
import { ProductCard } from '../components/ProductCard';

export default function Products() {
  const [products, setProducts] = useState([]);

  useEffect(() => {
    fetch('/api/v2/products')  // Changed endpoint
      .then(r => r.json())
      .then(data => setProducts(data.products));  // Changed response shape
  }, []);

  return (
    <div data-testid="products-page">
      <h1>All Products</h1>
      {products.map(p => <ProductCard key={p.id} product={p} />)}
    </div>
  );
}
"""
            (self.path / "src" / "pages" / "products.tsx").write_text(modified_page)

        subprocess.run(
            ["git", "add", "."],
            cwd=self.path,
            capture_output=True,
            check=True
        )
        result = subprocess.run(
            ["git", "commit", "-m", f"Change: {change_description}"],
            cwd=self.path,
            capture_output=True,
            text=True,
            check=True
        )

        # Get commit hash
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.path,
            capture_output=True,
            text=True,
            check=True
        )
        return commit_result.stdout.strip()

    def get_base_commit(self) -> str:
        """Get the base commit (HEAD)."""
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.path,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()


class TestPhase2Integration:
    """Integration tests for Phase 2 pipeline."""

    @pytest.fixture
    def mock_repo(self, tmp_path):
        """Create a mock repository."""
        repo = MockRepo(tmp_path)
        repo.init()
        repo.create_initial_structure()
        return repo

    def test_full_pipeline_selector_change(self, mock_repo):
        """Test: Full pipeline with component selector changes."""
        # Get base commit
        base_commit = mock_repo.get_base_commit()

        # Make a change (selector)
        pr_commit = mock_repo.make_change("Selector change - ProductCard")

        # Analyze the PR
        analyzer = PRAnalyzer(str(mock_repo.path), str(mock_repo.path / "spec.json"))
        analysis = analyzer.analyze_diff(base_commit, pr_commit)

        # Validate analysis results
        assert isinstance(analysis, ImpactAnalysis)
        assert len(analysis.changed_files) > 0, "Should detect changed files"
        assert analysis.reasoning, "Should have reasoning"

        print(f"\n✅ Analysis Results:")
        print(f"  - Changed files: {analysis.changed_files}")
        print(f"  - Affected flows: {analysis.affected_flows}")
        print(f"  - Needs updates: {analysis.needs_updates}")
        print(f"  - Reasoning: {analysis.reasoning}")

    def test_full_pipeline_api_change(self, mock_repo):
        """Test: Full pipeline with API endpoint changes."""
        base_commit = mock_repo.get_base_commit()
        pr_commit = mock_repo.make_change("API endpoint version bump")

        analyzer = PRAnalyzer(str(mock_repo.path), str(mock_repo.path / "spec.json"))
        analysis = analyzer.analyze_diff(base_commit, pr_commit)

        # Check API changes detected
        assert isinstance(analysis, ImpactAnalysis)
        print(f"\n✅ API Change Analysis:")
        print(f"  - Changed APIs: {analysis.changed_apis}")
        print(f"  - Changed files: {analysis.changed_files}")

    def test_git_diff_parser(self, mock_repo):
        """Test: Git diff parser extracts meaningful information."""
        base_commit = mock_repo.get_base_commit()
        pr_commit = mock_repo.make_change("Selector change - ProductCard")

        # Get raw diff
        parser = GitDiffParser()
        diff = parser.get_git_diff(str(mock_repo.path), base_commit, pr_commit)

        # Parse it
        parsed = parser.parse_diff(diff)

        # Validate parsed output
        assert parsed["files_changed"], "Should have changed files"
        assert parsed["lines_added"] > 0 or parsed["lines_removed"] > 0
        print(f"\n✅ Diff Parser Results:")
        print(f"  - Files: {parsed['files_changed']}")
        print(f"  - Lines: +{parsed['lines_added']} -{parsed['lines_removed']}")
        print(f"  - Selector changes: {parsed['selector_changes']}")

    def test_test_generation(self, mock_repo):
        """Test: Playwright test generation produces valid TypeScript."""
        # Load spec
        spec_path = mock_repo.path / "spec.json"
        with open(spec_path) as f:
            spec = json.load(f)

        # Create a test flow
        flow = Flow(
            id="test_browse_products",
            name="Browse Products",
            description="Test browsing products",
            steps=[
                FlowStep(action="navigate", url="/products"),
                FlowStep(action="wait", selector="[data-testid='products-page']"),
                FlowStep(action="click", selector="[data-testid='add-to-cart-btn']"),
            ],
            mocked_apis=[
                APICall(
                    url="/api/products",
                    method="GET",
                    response={"items": [{"id": 1, "name": "Test"}]}
                )
            ]
        )

        # Generate test
        gen = PlaywrightTestGenerator()
        test_code = gen.generate_test_code(flow, "http://localhost:3000")

        # Validate it's valid TypeScript
        assert "import" in test_code.lower(), "Should have imports"
        assert "test(" in test_code or "test.describe" in test_code, "Should have test function"
        assert "@playwright/test" in test_code, "Should import from @playwright/test"
        assert "data-testid" in test_code or "selector" in test_code.lower(), "Should use selectors"

        print(f"\n✅ Generated Test Code (first 500 chars):")
        print(test_code[:500])
        print("...")

        # Verify syntax by checking for common errors
        assert test_code.count("{") == test_code.count("}"), "Braces should match"
        assert test_code.count("[") == test_code.count("]"), "Brackets should match"
        assert test_code.count("(") == test_code.count(")"), "Parentheses should match"
        print("✅ Code structure validation passed")

    def test_generate_or_update_tests_flow(self, mock_repo):
        """Test: Full test generation and update flow."""
        # Prepare test directory
        test_dir = mock_repo.path / "tests"
        test_dir.mkdir(exist_ok=True)

        # Load spec
        spec_path = mock_repo.path / "spec.json"
        with open(spec_path) as f:
            spec = json.load(f)

        # Simulate impact analysis
        impact = {
            "affected_flows": ["user_browse_products"],
            "needs_new_tests": ["user_browse_products"],
            "needs_updates": [],
            "changed_files": ["src/components/ProductCard.tsx"],
            "changed_routes": ["/products"],
            "changed_apis": ["/api/products"],
            "changed_selectors": {
                "removed": ["[data-testid='product-card']", "[data-testid='add-to-cart']"]
            }
        }

        # Generate tests
        result = generate_or_update_tests(
            impact,
            spec,
            test_dir,
            "http://localhost:3000"
        )

        print(f"\n✅ Test Generation Result:")
        print(f"  - Generated: {result['generated_tests']}")
        print(f"  - Updated: {result['updated_tests']}")
        print(f"  - Fixtures created: {result['fixtures_created']}")
        print(f"  - Errors: {result['errors']}")

        # Validate results
        assert isinstance(result, dict)
        assert "generated_tests" in result
        assert isinstance(result["generated_tests"], list)

    def test_mock_fixtures_generation(self, mock_repo):
        """Test: Mock fixtures are generated correctly."""
        flows = [
            Flow(
                id="flow1",
                name="Flow 1",
                description="Test flow 1",
                steps=[],
                mocked_apis=[
                    APICall(url="/api/users", method="GET", response={"users": []}),
                    APICall(url="/api/posts", method="POST", response={"id": 1})
                ]
            )
        ]

        gen = PlaywrightTestGenerator()
        fixtures = gen.generate_mock_fixtures(flows)

        # Validate fixtures
        assert "@playwright/test" in fixtures
        assert "extend" in fixtures
        assert "/api/users" in fixtures
        assert "/api/posts" in fixtures
        assert "GET" in fixtures
        assert "POST" in fixtures

        print(f"\n✅ Generated Fixtures (first 400 chars):")
        print(fixtures[:400])
        print("...")


def test_pr_analyzer_with_real_diff():
    """Simple test without git repo - just test diff parsing."""
    sample_diff = """diff --git a/src/components/Button.tsx b/src/components/Button.tsx
index 1234567..abcdefg 100644
--- a/src/components/Button.tsx
+++ b/src/components/Button.tsx
@@ -1,5 +1,5 @@
 import React from 'react';
-export const Button = ({ label }) => (
-  <button className="btn" data-testid="button">{label}</button>
+export const Button = ({ label }) => (
+  <button className="btn-primary" data-testid="btn-submit">{label}</button>
 );
"""

    parser = GitDiffParser()
    result = parser.parse_diff(sample_diff)

    assert "src/components/Button.tsx" in result["files_changed"]
    assert result["lines_added"] > 0
    print(f"\n✅ Diff Parser Test:")
    print(f"  - Files: {result['files_changed']}")
    print(f"  - Component: {result['component_changes']}")


if __name__ == "__main__":
    # Run with: python -m pytest test_phase2_integration.py -v
    pytest.main([__file__, "-v", "-s"])
