from crudeoil_chain.cli import build_parser, main


def test_crudeoil_cli_accepts_a_manual_one_cycle_run() -> None:
    args = build_parser().parse_args(["--segment", "morning", "--once"])

    assert args.segment == "morning"
    assert args.once is True


def test_crudeoil_dry_run_does_not_require_credentials(capsys) -> None:
    assert main(["--segment", "afternoon", "--dry-run"]) == 0

    assert "DRY_RUN" in capsys.readouterr().out


def test_crudeoil_cli_reports_missing_configuration_without_connecting(monkeypatch, capsys) -> None:
    monkeypatch.delenv("FYERS_CLIENT_ID", raising=False)

    assert main(["--segment", "morning", "--once"]) == 2

    assert "CONFIGURATION_ERROR" in capsys.readouterr().out

