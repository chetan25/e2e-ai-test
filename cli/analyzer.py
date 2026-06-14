"""
Phase 1: Static code analysis
Extracts routes, components, API calls from codebase.
"""
import os
import json
import re
from pathlib import Path
from typing import Dict, List, Set, Any
from dataclasses import dataclass


@dataclass
class CodeAnalysis:
    routes: List[str]
    components: List[str]
    api_endpoints: List[str]
    external_services: List[str]
    entry_point: str


class CodebaseAnalyzer:
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)

    def analyze(self) -> CodeAnalysis:
        """Analyze codebase structure and extract key information."""
        routes = self._extract_routes()
        components = self._extract_components()
        api_endpoints = self._extract_api_endpoints()
        external_services = self._detect_external_services()
        entry_point = self._find_entry_point()

        return CodeAnalysis(
            routes=routes,
            components=components,
            api_endpoints=api_endpoints,
            external_services=external_services,
            entry_point=entry_point,
        )

    def _extract_routes(self) -> List[str]:
        """Extract routes from Next.js/React Router/Vue Router etc."""
        routes = []
        
        # Next.js app router (pages directory)
        pages_dir = self.repo_path / 'src' / 'pages'
        if pages_dir.exists():
            for f in pages_dir.rglob('*.tsx'):
                route = str(f.relative_to(pages_dir)).replace('.tsx', '').replace(os.sep, '/')
                if route.endswith('_app') or route.endswith('_document'):
                    continue
                routes.append(f"/{route}")

        # Next.js app router (app directory)
        app_dir = self.repo_path / 'src' / 'app'
        if app_dir.exists():
            for f in app_dir.rglob('page.tsx'):
                route = str(f.parent.relative_to(app_dir)).replace(os.sep, '/')
                if route == '.':
                    routes.append('/')
                else:
                    routes.append(f"/{route}")

        # React Router config
        for f in self.repo_path.rglob('routes.ts*'):
            routes.extend(self._parse_react_router_config(f))

        return sorted(set(routes))

    def _extract_components(self) -> List[str]:
        """Extract component names."""
        components = []
        comp_dirs = ['src/components', 'src/ui', 'components']
        
        for comp_dir in comp_dirs:
            path = self.repo_path / comp_dir
            if path.exists():
                for f in path.rglob('*.tsx'):
                    name = f.stem
                    if not name.startswith('_'):
                        components.append(name)

        return sorted(set(components))

    def _extract_api_endpoints(self) -> List[str]:
        """Extract API endpoints from code."""
        endpoints = []
        
        # Look for API route files
        for f in self.repo_path.rglob('route.ts'):
            route = str(f.parent.relative_to(self.repo_path)).replace(os.sep, '/').replace('app', '')
            endpoints.append(f"/api{route}")

        # Parse fetch/axios calls
        for f in self.repo_path.rglob('*.ts*'):
            if f.name.startswith('.'):
                continue
            try:
                content = f.read_text()
                # Simple regex: capture fetch/axios calls
                fetch_urls = re.findall(r'fetch\([\'"]([^"\']+)[\'"]', content)
                endpoints.extend(fetch_urls)
            except:
                pass

        return sorted(set(endpoints))

    def _detect_external_services(self) -> List[str]:
        """Detect external API services (Stripe, Auth0, etc.)."""
        services = set()
        
        # Check package.json for common service SDKs
        pkg_json = self.repo_path / 'package.json'
        if pkg_json.exists():
            try:
                with open(pkg_json) as f:
                    pkg = json.load(f)
                    deps = {**pkg.get('dependencies', {}), **pkg.get('devDependencies', {})}
                    
                    service_mappings = {
                        'stripe': 'Stripe',
                        '@auth0/auth0-react': 'Auth0',
                        '@supabase/supabase-js': 'Supabase',
                        'firebase': 'Firebase',
                        'aws-amplify': 'AWS Amplify',
                        'next-auth': 'NextAuth',
                    }
                    
                    for package, service in service_mappings.items():
                        if package in deps:
                            services.add(service)
            except:
                pass

        return sorted(services)

    def _find_entry_point(self) -> str:
        """Find app entry point."""
        candidates = ['index.tsx', 'App.tsx', 'main.tsx', 'index.ts']
        for candidate in candidates:
            if (self.repo_path / 'src' / candidate).exists():
                return f"src/{candidate}"
        return "src/index.tsx"

    def _parse_react_router_config(self, filepath: Path) -> List[str]:
        """Parse React Router configuration file."""
        # Simplified parser
        try:
            content = filepath.read_text()
            routes = re.findall(r'path:\s*[\'"]([^\'"]+)[\'"]', content)
            return routes
        except:
            return []


def analyze_repo(repo_path: str) -> CodeAnalysis:
    """Main entry point for static analysis."""
    analyzer = CodebaseAnalyzer(repo_path)
    return analyzer.analyze()
