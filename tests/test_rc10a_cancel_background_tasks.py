from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")


def _function_source(name: str) -> str:
    tree = ast.parse(MAIN)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(MAIN, node) or ""
    raise AssertionError(f"function {name} not found")


def test_cancel_reservation_accepts_background_tasks_for_async_email():
    src = _function_source("cancel_reservation")
    assert "background_tasks: BackgroundTasks" in src
    assert "queue_email_after_response(background_tasks" in src
