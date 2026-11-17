"""LangGraph 기반 멀티턴 대화 상태 관리.

같은 thread_id에서 목적지, 배터리, 이전 추천, 제외 시설과 선호조건을 이어받는다.
무료 로컬 실행을 위해 InMemorySaver를 사용하므로 서버를 재시작하면 상태는 초기화된다.
"""
from __future__ import annotations

import re
from typing import Any
from typing_extensions import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from agent_core import extract_battery
from merchant_places import shop_query


class ConversationState(TypedDict, total=False):
    query: str
    connector: str | None
    vehicle: str | None
    battery: int
    battery_override: bool
    origin: str
    origin_lat: float | None
    origin_lon: float | None
    preference: str
    count: int
    destination: str
    excluded_ids: list[str]
    result: dict[str, Any]
    turns: list[dict[str, str]]


FOLLOWUP_WORDS = ("빼고", "말고", "제외", "다시", "다른 곳", "더 가까", "더 안정", "더 안전", "대기 위험", "이동시간")
BATTERY_ONLY = re.compile(
    r"(?:(?:지금|현재)\s*)?(?:배터리(?:\s*잔량)?(?:은|는|이|가)?\s*)?"
    r"\d{1,3}\s*(?:%|퍼센트|프로)\s*"
    r"(?:야|이야|예요|이에요|입니다|남았어(?:요)?|로\s*(?:바꿔\s*줘|다시\s*추천해\s*줘))?[.!?]?"
)


class ConversationGraph:
    def __init__(self, service):
        self.service = service
        builder = StateGraph(ConversationState)
        builder.add_node("plan", self._plan)
        builder.add_edge(START, "plan")
        builder.add_edge("plan", END)
        self.memory = InMemorySaver()
        self.graph = builder.compile(checkpointer=self.memory)

    def _has_local_place(self, query: str) -> bool:
        q = query.replace(" ", "").lower()
        spot_col = "관광지명" if "관광지명" in self.service.spots.columns else "장소명"
        known = list(self.service.spots[spot_col].dropna().astype(str))
        known += list(self.service.stations["충전소명"].dropna().astype(str))
        # 읍·면·동처럼 명확한 행정지명도 새 목적지로 취급한다.
        if shop_query(query) or any(str(place) in query for place in self.service.stations["읍면동"].dropna().unique()):
            return True
        return any(name.replace(" ", "").lower() in q for name in known if len(name) >= 2)

    def _plan(self, state: ConversationState) -> dict[str, Any]:
        query = (state.get("query") or "").strip()
        previous = state.get("result") if isinstance(state.get("result"), dict) else None
        excluded = list(dict.fromkeys(state.get("excluded_ids") or []))

        if previous and previous.get("ok") and any(w in query for w in ("빼고", "말고", "제외")):
            compact = re.sub(r"\s+", "", query.lower())
            for plan in ("A", "B"):
                station = previous.get(plan) or {}
                label = plan.lower()
                if (f"plan{label}" in compact or f"플랜{label}" in compact) and station.get("id"):
                    excluded.append(str(station["id"]))
        if previous and previous.get("ok") and "다른 곳" in query:
            station = previous.get("A") or {}
            if station.get("id"):
                excluded.append(str(station["id"]))
        excluded = list(dict.fromkeys(excluded))

        explicit_battery = extract_battery(query)
        battery_only = explicit_battery is not None and BATTERY_ONLY.fullmatch(query) is not None
        is_followup = battery_only or any(w in query for w in FOLLOWUP_WORDS)
        contextual = bool(previous and previous.get("ok") and is_followup and not self._has_local_place(query))
        context_place = previous["dest"]["name"] if contextual else None
        clarifying = bool(previous and previous.get("clarify"))
        lookup_query = query
        if clarifying and previous.get("place_retry"):
            district = re.fullmatch(r"([가-힣]{2,10}?)(?:이야|이에요|예요|이요|쪽이야)?[.!]?", query)
            if district:
                region = district[1]
                known_regions = set(self.service.stations["읍면동"].dropna().astype(str)) | {"제주시","서귀포","애월","함덕","성산","한림","중문","협재"}
                if region in known_regions:
                    lookup_query = "목적지: " + region + " " + previous["place_retry"]

        battery = int(state.get("battery", 40))
        if explicit_battery is not None:
            battery = explicit_battery
        elif previous and not state.get("battery_override", False) and (clarifying or contextual or "아까랑 같" in query or "그대로" in query):
            battery = int(previous.get("battery", previous.get("memory", {}).get("battery", battery)))

        preference = state.get("preference", "균형 추천")
        if "대기 위험" in query or "대기 적" in query or "기다릴 위험" in query or "덜 기다" in query:
            preference = "대기 위험 우선"
        elif "더 가까" in query or "이동시간" in query:
            preference = "이동시간 우선"
        elif "plan b" in query.lower() and any(w in query for w in ("안전","안정")):
            preference = "Plan B 우선"

        result = self.service.ask(
            query=lookup_query,
            vehicle=state.get("vehicle"),
            connector=state.get("connector"),
            battery=battery,
            origin_text=state.get("origin", ""),
            origin_lat=state.get("origin_lat"),
            origin_lon=state.get("origin_lon"),
            preference=preference,
            count=int(state.get("count", 3)),
            context_place=context_place,
            exclude_ids=excluded,
        )

        result["query"] = query
        turns = list(state.get("turns") or [])
        turns.append({"role": "user", "text": query})
        turns.append({"role": "assistant", "text": result.get("summary", "")})
        turns = turns[-8:]
        destination = result.get("dest", {}).get("name") if result.get("ok") else state.get("destination", "")
        result["memory"] = {
            "destination": destination,
            "battery": result.get("battery", battery),
            "excluded_count": len(excluded),
            "turn_count": len([t for t in turns if t["role"] == "user"]),
            "framework": "LangGraph",
            "persistence": "서버 실행 중 세션 기억",
        }
        result["conversation"] = turns
        return {
            "result": result,
            "destination": destination,
            "battery": int(result.get("battery", battery)),
            "preference": preference,
            "excluded_ids": excluded,
            "turns": turns,
        }

    def invoke(self, thread_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        config = {"configurable": {"thread_id": thread_id}}
        state = self.graph.invoke(payload, config=config)
        result = state["result"]
        result["thread_id"] = thread_id
        return result

    def clear(self, thread_id: str) -> None:
        self.memory.delete_thread(thread_id)
