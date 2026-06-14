from setuptools import setup, find_packages

setup(
    name="e2e-ai-test",
    version="0.1.0",
    description="AI-driven E2E testing: auto-discover flows, generate tests, maintain coverage",
    author="Chetan Dasauni",
    url="https://github.com/chetan25/e2e-ai-test",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "playwright>=1.40.0",
        "anthropic>=0.25.0",
        "pydantic>=2.0",
        "click>=8.1.0",
        "gitpython>=3.1.0",
        "pyyaml>=6.0",
        "requests>=2.31.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "ruff>=0.1.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "e2e-discover=cli.discover:main",
        ]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
