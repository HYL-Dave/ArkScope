"""App notices are local, read-only and never imply subscription entitlement."""

from tests.test_sa_acquisition_authority import activate, begin, call, FIREFOX
from src.sa.company_collector import CompanyCollector


def test_status_read_does_not_install_storage(tmp_path):
    root = tmp_path / "absent"
    result = CompanyCollector(root / "control.db").public_status()
    assert result["configured"] is False
    assert result["status"] == "ok"
    assert not root.exists()


def test_login_and_capability_warnings_are_durable_and_exclude_secrets(tmp_path):
    collector = CompanyCollector(tmp_path / "control.db")
    activate(collector)
    permit = begin(collector)
    call(collector,"observe_restriction",FIREFOX,token=permit["token"],generation=1,reason="login_required")
    result = CompanyCollector(collector.path).public_status()
    assert result["paused_reason"] == "login_required"
    assert result["configured"] is True
    assert "token" not in str(result) and "client_id" not in str(result)
    assert "entitled" not in result


def test_local_route_uses_only_the_read_only_status(monkeypatch, tmp_path):
    from src.api.routes import seeking_alpha
    monkeypatch.setattr("src.sa.company_collector.CompanyCollector", lambda: CompanyCollector(tmp_path / "missing.db"))
    result = seeking_alpha.sa_acquisition_status()
    assert result["configured"] is False
    assert not list(tmp_path.iterdir())
