"""Unit tests for analyzer module."""
import pytest
from cli.analyzer import CodebaseAnalyzer


def test_analyze_simple_repo(tmp_path):
    """Test analyzing a simple repo structure."""
    # Create test repo
    (tmp_path / 'src' / 'pages').mkdir(parents=True)
    (tmp_path / 'src' / 'pages' / 'index.tsx').write_text('export default () => {}')
    
    analyzer = CodebaseAnalyzer(str(tmp_path))
    analysis = analyzer.analyze()
    
    assert '/' in analysis.routes
