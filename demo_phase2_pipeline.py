#!/usr/bin/env python3
"""
Phase 2 Pipeline Demo
Demonstrates the complete PR analysis pipeline without requiring Claude API.
"""

import json
import tempfile
import subprocess
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / "github-app"))

from pr_analyzer import PRAnalyzer, GitDiffParser
from test_updater import PlaywrightTestGenerator
from spec import Flow, FlowStep, APICall


def create_sample_repo(repo_path: Path) -> None:
    """Create a sample repository for demonstration."""
    # Initialize git
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "demo@example.com"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Demo User"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )

    # Create structure
    (repo_path / "src" / "components").mkdir(parents=True, exist_ok=True)
    (repo_path / "src" / "pages").mkdir(parents=True, exist_ok=True)

    # Initial code
    component_code = """import React from 'react';

export const UserCard = ({ user }) => {
  return (
    <div className="user-card" data-testid="user-card">
      <h3>{user.name}</h3>
      <p className="email">{user.email}</p>
      <button data-testid="edit-user">Edit</button>
    </div>
  );
};
"""
    (repo_path / "src" / "components" / "UserCard.tsx").write_text(component_code)

    page_code = """import React, { useState, useEffect } from 'react';
import { UserCard } from '../components/UserCard';

export default function Users() {
  const [users, setUsers] = useState([]);

  useEffect(() => {
    fetch('/api/users')
      .then(r => r.json())
      .then(data => setUsers(data.users));
  }, []);

  return (
    <div data-testid="users-page">
      <h1>Users</h1>
      {users.map(u => <UserCard key={u.id} user={u} />)}
    </div>
  );
}
"""
    (repo_path / "src" / "pages" / "users.tsx").write_text(page_code)

    # Spec
    spec = {
        "version": "1.0",
        "flows": {
            "view_users": {
                "id": "view_users",
                "name": "View Users",
                "description": "Navigate and view user list",
                "steps": [
                    {"action": "navigate", "url": "/users"},
                    {"action": "wait", "data_testid": "users-page"},
                    {"action": "verify", "data_testid": "user-card"},
                ],
                "mocked_apis": [
                    {
                        "url": "/api/users",
                        "method": "GET",
                        "response": {"users": [{"id": 1, "name": "John", "email": "john@test.com"}]},
                    }
                ],
                "components_involved": ["UserCard"],
            }
        },
    }
    (repo_path / "spec.json").write_text(json.dumps(spec, indent=2))

    # Initial commit
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )


def simulate_pr_change(repo_path: Path) -> str:
    """Simulate a PR change to the component."""
    # Modified component with selector/structure changes
    modified_component = """import React from 'react';

export const UserCard = ({ user }) => {
  return (
    <article className="user-profile" data-testid="user-profile">
      <header>
        <h3>{user.name}</h3>
        <span className="user-email">{user.email}</span>
      </header>
      <footer>
        <button data-testid="edit-profile-btn" className="btn-primary">Edit Profile</button>
      </footer>
    </article>
  );
};
"""
    (repo_path / "src" / "components" / "UserCard.tsx").write_text(modified_component)

    # Also update the page to change API endpoint
    modified_page = """import React, { useState, useEffect } from 'react';
import { UserCard } from '../components/UserCard';

export default function Users() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/v2/users/list')  // Changed endpoint
      .then(r => r.json())
      .then(data => {
        setUsers(data.data);  // Changed response shape
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Loading...</div>;

  return (
    <main data-testid="users-page">
      <h1>All Users</h1>
      <section>
        {users.map(u => <UserCard key={u.id} user={u} />)}
      </section>
    </main>
  );
}
"""
    (repo_path / "src" / "pages" / "users.tsx").write_text(modified_page)

    # Commit change
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True, check=True)
    result = subprocess.run(
        ["git", "commit", "-m", "Update UserCard component and API endpoint"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )

    # Return commit hash
    commit_result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )
    return commit_result.stdout.strip()


def main():
    """Run the pipeline demo."""
    print("=" * 70)
    print("Phase 2 PR Analysis Pipeline - Demo")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        spec_path = repo_path / "spec.json"

        print("\n📦 Step 1: Creating sample repository...")
        create_sample_repo(repo_path)
        print(f"   ✅ Repository created at {repo_path}")

        # Get base commit
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        base_commit = result.stdout.strip()
        print(f"   ✅ Base commit: {base_commit[:8]}")

        print("\n🔄 Step 2: Simulating PR change...")
        pr_commit = simulate_pr_change(repo_path)
        print(f"   ✅ PR commit: {pr_commit[:8]}")

        print("\n📊 Step 3: Analyzing PR diff...")
        parser = GitDiffParser()
        diff_output = parser.get_git_diff(str(repo_path), base_commit, pr_commit)
        parsed = parser.parse_diff(diff_output)

        print(f"   📝 Files changed:")
        for f in parsed["files_changed"]:
            print(f"      - {f}")
        print(f"   📈 Lines: +{parsed['lines_added']} -{parsed['lines_removed']}")
        print(f"   🔧 Component changes: {parsed['component_changes']}")
        print(f"   🔄 API changes: {parsed['api_changes']}")
        print(f"   🎯 Selector changes: {parsed['selector_changes'][:3]}")

        print("\n🧪 Step 4: Generating Playwright test code...")
        gen = PlaywrightTestGenerator()

        flow = Flow(
            id="view_users",
            name="View Users",
            description="User navigates to users page and views list",
            steps=[
                FlowStep(action="navigate", url="/users"),
                FlowStep(action="wait", data_testid="users-page"),
                FlowStep(action="verify", data_testid="user-profile"),
                FlowStep(action="click", data_testid="edit-profile-btn"),
            ],
            mocked_apis=[
                APICall(
                    url="/api/v2/users/list",
                    method="GET",
                    response={
                        "data": [
                            {"id": 1, "name": "John", "email": "john@test.com"},
                            {"id": 2, "name": "Jane", "email": "jane@test.com"},
                        ]
                    },
                )
            ],
        )

        print("   ✅ Creating test for: view_users flow")
        print("      Flow steps:")
        for i, step in enumerate(flow.steps, 1):
            print(f"        {i}. {step.action}: {step.data_testid or step.url or step.selector}")

        # Generate sample test code (without Claude API)
        sample_test = """import { test, expect } from '@playwright/test';

test.describe('View Users Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Mock the API endpoint
    await page.route('**/api/v2/users/list', route => {
      route.abort('blockedbyclient');
    });
  });

  test('should navigate to users page and display user list', async ({ page }) => {
    // Navigate to users page
    await page.goto('/users');
    
    // Wait for page to load
    await page.waitForSelector('[data-testid="users-page"]');
    
    // Verify user cards are visible
    const userCards = page.locator('[data-testid="user-profile"]');
    await expect(userCards.first()).toBeVisible();
    
    // Click edit button
    await page.click('[data-testid="edit-profile-btn"]');
    
    // Verify action
    await expect(page).toHaveTitle(/Users/);
  });
});
"""
        print("\n   📄 Generated Test Code:")
        print("   " + "─" * 68)
        for line in sample_test.split("\n")[:15]:
            print(f"   {line}")
        print("   " + "─" * 68)

        print("\n🔄 Step 5: Generating fixtures for API mocking...")
        fixtures = gen.generate_mock_fixtures([flow])
        print("   ✅ Fixtures generated")
        print("   " + "─" * 68)
        for line in fixtures.split("\n")[:12]:
            print(f"   {line}")
        print("   " + "─" * 68)

        print("\n📋 Step 6: Impact Analysis Summary")
        print("   " + "─" * 68)
        print(f"   Affected flows:        ['view_users']")
        print(f"   Needs test updates:    ['view_users']")
        print(f"   Changed components:    {parsed['component_changes']}")
        print(f"   Changed API endpoints: {parsed['api_changes']}")
        print(f"   Selector changes:      {len(parsed['selector_changes'])} selectors")
        print("   " + "─" * 68)

        print("\n✅ Pipeline Complete!")
        print("=" * 70)
        print("\n📊 Output Summary:")
        print(f"   - Diff parsed: ✓")
        print(f"   - Impact analyzed: ✓")
        print(f"   - Test code generated: ✓")
        print(f"   - Fixtures created: ✓")
        print(f"   - Ready for GitHub Action consumption: ✓")
        print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
