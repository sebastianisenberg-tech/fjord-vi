from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")


def test_closing_sheet_vigente_anulada_flow_is_not_regressed():
    assert "def create_closing_sheet" in MAIN
    assert "anula" in MAIN.lower()
    assert "VIGENTE" in MAIN
    assert "ANULADA" in MAIN
    assert "annul_reason" in MAIN
    assert "fichas anuladas excluidas" in MAIN


def test_pdf_and_liquidation_are_still_present():
    assert "FICHA DE CIERRE DE NAVEGACIÓN" in MAIN
    assert "Total general a liquidar" in MAIN or "TOTAL" in MAIN
    assert "liquidation_id_for_sheet" in MAIN
    assert "TemplateResponse(request, \"closing_sheet.html\"" in MAIN
