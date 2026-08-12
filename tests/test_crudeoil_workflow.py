from pathlib import Path


def test_crudeoil_workflow_has_manual_dispatch_and_dedicated_sheet_secret() -> None:
    workflow = Path(".github/workflows/crudeoil-live.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "CRUDEOIL_GOOGLE_SHEET_ID" in workflow
    assert "timeout-minutes: 360" in workflow
    assert "python -m crudeoil_chain" in workflow


def test_crudeoil_workflow_accepts_standard_sheet_secret_as_fallback() -> None:
    workflow = Path(".github/workflows/crudeoil-live.yml").read_text(encoding="utf-8")

    assert "secrets.CRUDEOIL_GOOGLE_SHEET_ID || secrets.GOOGLE_SHEET_ID" in workflow

