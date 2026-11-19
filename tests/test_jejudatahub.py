import json

from jejudatahub_client import JejuDataHubClient


def test_fallback_history_is_used(tmp_path, monkeypatch):
    monkeypatch.delenv("JEJU_DATAHUB_PROJECT_KEY", raising=False)
    monkeypatch.delenv("JEJU_DATAHUB_CHARGE_DATA_CODE", raising=False)
    path = tmp_path / "history.json"
    path.write_text(json.dumps({"stations": {"F1": {"peak_hours": [16]}}}), encoding="utf-8")
    client = JejuDataHubClient(path)
    assert client.station_context("F1", hour=16)["penalty"] == 7
    assert client.station_context("F1", hour=15)["penalty"] == 3
    assert client.station_context("F1", hour=10)["penalty"] == 0


def test_403_message_does_not_expose_project_key(tmp_path, monkeypatch):
    path = tmp_path / "history.json"
    path.write_text('{"stations": {}}', encoding="utf-8")
    monkeypatch.setenv("JEJU_DATAHUB_PROJECT_KEY", "very-secret-project-key")
    monkeypatch.setenv("JEJU_DATAHUB_CHARGE_DATA_CODE", "136")
    monkeypatch.setenv("JEJU_DATAHUB_MODE", "api")

    class Forbidden:
        status_code = 403
        def raise_for_status(self):
            return None

    monkeypatch.setattr("jejudatahub_client.requests.get", lambda *args, **kwargs: Forbidden())
    status = JejuDataHubClient(path).refresh()
    assert status["state"] == "error"
    assert "403" in status["text"] and "very-secret" not in status["text"]


def test_wait_risk_combines_weekday_wait_and_floating(tmp_path, monkeypatch):
    monkeypatch.delenv("JEJU_DATAHUB_PROJECT_KEY", raising=False)
    path = tmp_path / "history.json"
    path.write_text('{"stations": {}}', encoding="utf-8")
    client = JejuDataHubClient(path)
    client.weekly = {"F1": {"월": 10, "화": 20}}
    client.wait = {"F1": 12}
    client.floating_percentile = {"성산읍": .8}
    context = client.station_context("F1", "테스트 충전소", "성산읍", weekday="화")
    assert context["level"] == "high"
    assert context["confidence"] == "높음"
    assert len(context["evidence"]) == 3
