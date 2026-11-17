from kakao_client import _driving_route_cached, driving_route, search_place
from realtime_client import fetch_jeju_status
import llm_agent


def test_kakao_client_falls_back_without_key(monkeypatch):
    monkeypatch.delenv("KAKAO_REST_API_KEY", raising=False)
    assert search_place("성산일출봉") is None
    assert driving_route(33.4, 126.5, 33.5, 126.6) is None


def test_kakao_driving_route_parses_minutes_and_distance(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"routes": [{"summary": {"duration": 754, "distance": 8420}}]}

    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-key")
    monkeypatch.setattr("kakao_client.requests.get", lambda *args, **kwargs: FakeResponse())
    _driving_route_cached.cache_clear()
    route = driving_route(33.4, 126.5, 33.5, 126.6)
    assert route == {"minutes": 13, "distance_km": 8.4, "source": "Kakao Mobility"}


def test_realtime_client_falls_back_without_key(monkeypatch):
    monkeypatch.delenv("DATA_GO_KR_SERVICE_KEY", raising=False)
    data, error = fetch_jeju_status()
    assert data == {}
    assert "인증키" in error


def test_gemini_falls_back_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert llm_agent.parse_with_gemini("성산일출봉") is None
    ok, msg = llm_agent.check_connection()
    assert not ok and "GEMINI_API_KEY" in msg


def test_gemini_model_order(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-없는-모델")
    llm_agent.STATE["model"] = None
    models = llm_agent._models()
    assert models[0] == "gemini-없는-모델" and "gemini-2.5-flash-lite" in models


def test_json_fence_is_stripped():
    assert llm_agent._json('```json\n{"place":"성산"}\n```') == {"place": "성산"}


def test_gemini_switches_model_when_not_found(monkeypatch):
    """설정한 모델이 없으면(404) 다음 후보 모델로 넘어가 응답을 받는다."""
    import sys
    import types

    class NotFound(Exception):
        code = 404

    class FakeModels:
        def generate_content(self, model, contents, config):
            if model == "gemini-없는-모델":
                raise NotFound("models/gemini-없는-모델 is not found")
            return types.SimpleNamespace(text='{"place":"성산일출봉","intent":"recommend"}')

    fake_genai = types.SimpleNamespace(Client=lambda api_key: types.SimpleNamespace(models=FakeModels()))
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setitem(sys.modules, "google", types.SimpleNamespace(genai=fake_genai))
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-없는-모델")
    llm_agent.STATE.update(model=None, last_error=None)
    parsed = llm_agent.parse_with_gemini("성산일출봉 근처 충전소")
    assert parsed["place"] == "성산일출봉"
    assert llm_agent.STATE["model"] == "gemini-2.5-flash-lite"
