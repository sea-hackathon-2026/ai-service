"""Guard the dependency direction claimed by the architecture documentation."""

import ast
from pathlib import Path

BOUNDARIES = {
    Path("services/ai_api/domain"): (
        "fastapi",
        "sqlalchemy",
        "openai",
        "google",
        "services.ai_api.infrastructure",
    ),
    Path("services/ai_api/application"): (
        "fastapi",
        "sqlalchemy",
        "openai",
        "google",
        "services.ai_api.infrastructure",
    ),
    Path("services/rag_service/domain"): (
        "fastapi",
        "openai",
        "services.rag_service.infrastructure",
    ),
    Path("services/rag_service/application"): (
        "fastapi",
        "openai",
        "services.rag_service.infrastructure",
    ),
}


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            values.append(node.module)
    return values


def test_inner_layers_do_not_import_frameworks_or_infrastructure() -> None:
    violations: list[str] = []
    for root, forbidden_prefixes in BOUNDARIES.items():
        for path in root.rglob("*.py"):
            for imported_module in _imports(path):
                if imported_module.startswith(forbidden_prefixes):
                    violations.append(f"{path}: {imported_module}")

    assert violations == []
