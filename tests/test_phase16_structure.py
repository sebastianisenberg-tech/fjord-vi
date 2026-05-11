from pathlib import Path

def test_core_directories_exist():
    required = [
        "app",
        "docs",
        "tests",
        "migrations",
        "scripts"
    ]

    for item in required:
        assert Path(item).exists()

def test_documentation_present():
    docs = [
        "ARCHITECTURE.md",
        "DEPLOYMENT.md",
        "SECURITY_CHECKLIST.md",
    ]

    for doc in docs:
        assert Path("docs", doc).exists()
