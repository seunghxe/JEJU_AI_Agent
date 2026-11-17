"""Gemini(무료 등급)로 질문을 해석하고 답변 문장을 쓴다.

- .env의 GEMINI_MODEL을 먼저 쓰고, 그 모델이 없으면(404) 아래 후보 모델로 자동 전환한다.
- 호출 결과와 마지막 오류를 STATE에 남겨 화면에서 실제 사용 여부를 확인할 수 있다.
- 키가 없거나 모든 호출이 실패하면 None을 돌려주고, 앱은 규칙 기반으로 계속 동작한다.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

FALLBACK_MODELS = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash"]
STATE: dict[str, Any] = {"model": None, "last_error": None, "calls": 0, "success": 0}


def is_configured() -> bool:
    return bool(os.getenv("GEMINI_API_KEY", "").strip())


def _models() -> list[str]:
    first = [STATE["model"]] if STATE["model"] else []
    env = os.getenv("GEMINI_MODEL", "").strip()
    seen, out = set(), []
    for m in first + ([env] if env else []) + FALLBACK_MODELS:
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out


def _friendly(exc: Exception) -> str:
    text = str(exc)
    code = getattr(exc, "code", None)
    if code == 429 or "RESOURCE_EXHAUSTED" in text:
        return "무료 사용 한도 초과(잠시 후 다시 시도)"
    if code in (401, 403) or "API_KEY_INVALID" in text or "PERMISSION" in text:
        return "API 키 확인 필요"
    if code == 404 or "not found" in text.lower():
        return "모델 이름 확인 필요"
    return f"{type(exc).__name__}"


def _generate(prompt: str, json_mode: bool) -> str | None:
    if not is_configured():
        return None
    try:
        from google import genai
    except ImportError:
        STATE["last_error"] = "google-genai 패키지 미설치"
        return None
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", "").strip())
    config = {"response_mime_type": "application/json", "temperature": 0} if json_mode else {"temperature": 0.3}
    for model in _models():
        STATE["calls"] += 1
        try:
            response = client.models.generate_content(model=model, contents=prompt, config=config)
            text = (response.text or "").strip()
            if text:
                STATE.update(model=model, last_error=None)
                STATE["success"] += 1
                return text
        except Exception as exc:  # 모델이 없으면 다음 후보로, 그 외 오류는 중단
            STATE["last_error"] = _friendly(exc)
            if STATE["last_error"] != "모델 이름 확인 필요":
                return None
    return None


def _json(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        STATE["last_error"] = "응답 형식 오류"
        return None


def parse_with_gemini(query: str) -> dict[str, Any] | None:
    """질문에서 목적지·출발지·의도·추천 기준·배터리를 JSON으로 추출한다."""
    prompt = f"""
너는 제주 전기차 여행자의 질문을 분석하는 라우터다. 아래 키를 가진 JSON 하나만 반환하라.
- place: 충전하려는 목적지(관광지·충전소·읍면동 이름만). 없으면 ""
- origin: 지금 있는 곳·출발지. 없으면 ""
- intent: "recommend" 또는 "plan_b"(특정 충전소가 막혔을 때 대안을 묻는 경우)
- preference: "균형 추천" / "운영 안정성" / "대체시설 여유" 중 하나
- battery: 배터리 잔량 숫자(%) 또는 null

질문: {query}
예시: {{"place":"성판악","origin":"노형동","intent":"recommend","preference":"운영 안정성","battery":30}}
"""
    return _json(_generate(prompt, json_mode=True))


def summarize_with_gemini(facts: dict[str, Any]) -> str | None:
    """에이전트가 계산한 사실만 근거로 2~3문장 답변을 쓴다. 숫자를 새로 만들지 않는다."""
    prompt = f"""
너는 제주 전기차 여행자를 돕는 충전 안내원이다. 아래 사실(JSON)만 근거로 한국어 2~3문장으로 답하라.
- 첫 문장: 가장 추천하는 충전소와 그 이유.
- 둘째 문장: 막혔을 때 갈 대체 충전소(Plan B).
- 경고가 있으면 마지막에 짧게.
- JSON에 없는 숫자·사실은 만들지 말 것. 친근한 존댓말. 마크다운·이모지 금지.

사실: {json.dumps(facts, ensure_ascii=False)}
"""
    return _generate(prompt, json_mode=False)


def check_connection() -> tuple[bool, str]:
    """화면의 '연결 점검' 버튼용. 짧은 호출로 실제 응답 여부를 확인한다."""
    if not is_configured():
        return False, "GEMINI_API_KEY가 설정되지 않았어요"
    text = _generate("한 단어로 '정상'이라고만 답하라.", json_mode=False)
    if text:
        return True, f"정상 응답 · 모델 {STATE['model']}"
    return False, STATE["last_error"] or "응답 없음"
