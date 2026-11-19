"""화면과 분리된 에이전트 실행 계층.

질문 하나를 받아 다음 순서로 판단하고, 화면이 그대로 그릴 수 있는 JSON을 돌려준다.
질문 이해 → 장소 찾기 → 주변 후보 비교 → 실시간 반영 → 배터리 확인 → Plan B 계산 → 답변 작성
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any

import pandas as pd

import llm_agent
from agent_core import (
    apply_live, distance_km, extract_battery, kakao_link, live_text, load_station_data,
    load_tourist_spots, range_check, recommend, recommend_near_coordinate, reliability_text,
    resolve_place, station_warnings,
)
from kakao_client import driving_route, search_place, search_places
from merchant_places import shop_query, resolve_shop
from request_progress import mark
from jejudatahub_client import JejuDataHubClient
from realtime_client import fetch_jeju_status, now_kst_text

PREFERENCES = ["균형 추천", "이동시간 우선", "대기 위험 우선", "Plan B 우선"]
QUICK_PLACES = [
    {"label": "성산일출봉", "query": "성산일출봉 가는데 근처 충전소 알려줘"},
    {"label": "한라산 어리목", "query": "내일 어리목에서 한라산 탐방해"},
    {"label": "협재해수욕장", "query": "협재해수욕장 근처에서 충전하고 싶어"},
    {"label": "중문관광단지", "query": "중문관광단지 근처 충전소"},
    {"label": "함덕해수욕장", "query": "함덕해수욕장 가는 길에 충전하고 싶어"},
    {"label": "우도", "query": "우도 들어가기 전에 충전할 곳"},
]


def _num(v, default=None):
    try:
        return default if v is None or pd.isna(v) else float(v)
    except (TypeError, ValueError):
        return default


def _place_key(value: Any) -> str:
    """상호 후보 비교용 문자열. 주소·괄호·공백 차이는 무시한다."""
    import re
    return re.sub(r"[^0-9a-z가-힣]", "", str(value or "").lower())


def _needs_place_choice(query: str, candidates: list[dict[str, Any]]) -> bool:
    """검색어와 관련된 제주 후보가 둘 이상이면 사용자의 지점 선택을 받는다."""
    if len(candidates) < 2:
        return False
    q = _place_key(query)
    generic = {"카페", "식당", "베이커리", "커피숍", "충전소", "근처", "제주"}
    for word in generic:
        q = q.replace(word, "")
    if len(q) < 2:
        return True
    related = [c for c in candidates if q in _place_key(c.get("name")) or _place_key(c.get("name")) in q]
    if len(related) >= 2:
        return True
    # 카카오가 동일 상호를 지점명과 함께 돌려주는 경우를 위해 공통 앞부분도 확인한다.
    names = [_place_key(c.get("name")) for c in candidates]
    return len(names) >= 2 and names[0][:max(2, min(len(q), 4))] in names[1]


def _place_candidates_payload(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """브라우저가 다시 전달해도 안전한 최소 장소 정보만 노출한다."""
    return [{
        "id": str(c.get("id") or ""),
        "name": str(c.get("name") or ""),
        "address": str(c.get("address") or "주소 미확인"),
        "category": str(c.get("category") or "장소"),
        "lat": float(c["lat"]),
        "lon": float(c["lon"]),
        "source": "Kakao Local API",
    } for c in candidates[:5]]


class AgentService:
    def __init__(self, data_dir: str | Path):
        data_dir = Path(data_dir)
        self.stations = load_station_data(data_dir / "stations.csv")
        self.spots = load_tourist_spots(data_dir / "tourist_spots.csv")
        self.vehicles = pd.read_csv(data_dir / "vehicles.csv")
        self.by_id = self.stations.set_index("시설 ID")
        self.datahub = JejuDataHubClient(data_dir.parent / "static" / "charge_history.json")
        if self.datahub.configured:
            # 서버 시작을 막지 않고 백그라운드에서 허브 데이터를 준비한다.
            threading.Thread(target=self.datahub.refresh, daemon=True, name="jeju-datahub-refresh").start()
        self._live: dict[str, dict] = {}
        self._live_error: str | None = None
        self._live_time: str | None = None
        self._live_at = 0.0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ 연결 상태
    @property
    def live_ready(self) -> bool:
        return bool(os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip())

    @property
    def kakao_ready(self) -> bool:
        return bool(os.getenv("KAKAO_REST_API_KEY", "").strip())

    def live(self, force: bool = False) -> dict[str, dict]:
        """실시간 상태를 5분간 캐시한다."""
        if not self.live_ready:
            return {}
        with self._lock:
            if force or time.time() - self._live_at > 300:
                data, error = fetch_jeju_status()
                self._live_error = error
                self._live_at = time.time()
                if not data:
                    self._live = {}; self._live_time = None
                if data:
                    self._live, self._live_time = data, now_kst_text()
        return self._live

    def status(self) -> dict[str, Any]:
        live = self.live()
        if not llm_agent.is_configured():
            gemini = {"state": "off", "text": "꺼짐"}
        elif llm_agent.STATE["last_error"]:
            gemini = {"state": "error", "text": llm_agent.STATE["last_error"]}
        else:
            gemini = {"state": "on", "text": llm_agent.STATE["model"] or "준비됨"}
        if live:
            live_s = {"state": "on", "text": f"{self._live_time} 기준 · {len(live):,}곳"}
        elif self.live_ready:
            live_s = {"state": "error", "text": self._live_error or "연결 실패"}
        else:
            live_s = {"state": "off", "text": "꺼짐 · 과거 기록으로 안내"}
        return {"live": live_s, "gemini": gemini, "datahub": self.datahub.status(),
                "kakao": {"state": "on" if self.kakao_ready else "off", "text": "켜짐" if self.kakao_ready else "꺼짐"}}

    def meta(self) -> dict[str, Any]:
        vehicles = [{"name": r["차량명"], "kwh": float(r["사용가능배터리_kWh"]), "eff": float(r["대표전비_km_per_kWh"])}
                    for _, r in self.vehicles.iterrows()]
        return {"vehicles": vehicles, "quick": QUICK_PLACES, "preferences": PREFERENCES,
                "status": self.status(), "stations": len(self.stations)}

    def station_points(self) -> list[list]:
        """첫 화면 지도용: [위도, 경도, 이름, 상태 톤]. 실시간이 있으면 우선한다."""
        self.live()
        out = []
        for _, r in self.stations.iterrows():
            live = self._live_of(r["시설 ID"])
            tone = live["tone"] if live else reliability_text(r.get("상태위험축"))[1]
            out.append([round(float(r["위도"]), 5), round(float(r["경도"]), 5), r["충전소명"],
                        tone, {"address":str(r.get("주소","")), "chargers":int(_num(r.get("조건충족충전기수"),0)),
                               "live":live, "reliability":{"text":reliability_text(r.get("상태위험축"))[0]},
                               "backup":None if pd.isna(r.get("PlanB대표충전소명")) else str(r["PlanB대표충전소명"]),
                               "directions":kakao_link(r["충전소명"],r["위도"],r["경도"])}])
        return out

    def station_live(self, facility_id: str, force: bool = False) -> dict[str, Any]:
        """선택 시설의 최신 상태를 화면의 Plan B 전환 감시에 제공한다."""
        self.live(force=force)
        info = self._live_of(facility_id)
        return {"ok": info is not None, "facility_id": facility_id, "live": info,
                "checked_at": self._live_time}

    # ------------------------------------------------------------------ 직렬화 도우미
    def _live_of(self, facility_id) -> dict | None:
        live = self._live if self.live_ready else {}
        if not live or facility_id not in self.by_id.index:
            return None
        t = live_text(live.get(str(self.by_id.loc[facility_id, "대표충전소 ID"])))
        return {"text": t[0], "tone": t[1]} if t else None

    def _station(self, row, dest=None) -> dict[str, Any]:
        rel = reliability_text(row.get("상태위험축"))
        lat, lon = _num(row.get("위도")), _num(row.get("경도"))
        out = {
            "id": row["시설 ID"], "name": row["충전소명"], "address": row.get("주소", ""),
            "lat": lat, "lon": lon, "chargers": int(_num(row.get("조건충족충전기수"), 0)),
            "reliability": {"text": rel[0], "tone": rel[1]}, "live": self._live_of(row["시설 ID"]),
            "directions": kakao_link(row["충전소명"], lat, lon),
            "alt3km": int(_num(row.get("3km이내대체시설수"), 0)),
            "history": self.datahub.station_context(
                row["시설 ID"], row.get("충전소명"), row.get("읍면동")
            ),
        }
        score = _num(row.get("최종추천점수"), _num(row.get("사용자추천점수")))
        if score is not None:
            out["score"] = int(round(min(max(score, 0), 100)))
        if dest is not None and lat is not None:
            out["from_dest_km"] = round(distance_km(dest["lat"], dest["lon"], lat, lon), 2)
        return out

    def _plan_b(self, row) -> dict[str, Any] | None:
        name = row.get("PlanB대표충전소명")
        if pd.isna(name) or not str(name).strip():
            return None
        lat, lon = _num(row.get("PlanB_위도")), _num(row.get("PlanB_경도"))
        rel = reliability_text(row.get("PlanB_상태위험축"))
        plan_b_id = row.get("PlanB시설그룹아이디")
        plan_b_dong = None
        if plan_b_id in self.by_id.index:
            plan_b_dong = self.by_id.loc[plan_b_id].get("읍면동")
        return {"id": plan_b_id, "address":str(self.by_id.loc[plan_b_id].get("주소","")) if plan_b_id in self.by_id.index else "", "name": name, "lat": lat, "lon": lon,
                "from_a_km": round(_num(row.get("Plan B 거리(km)"), 0), 2),
                "chargers": int(_num(row.get("PlanB_충전기수"), 0)),
                "reliability": {"text": rel[0], "tone": rel[1]},
                "live": self._live_of(row.get("PlanB시설그룹아이디")),
                "directions": kakao_link(name, lat, lon),
                "history": self.datahub.station_context(plan_b_id, name, plan_b_dong)}

    def _select_plan_b(self, row, exclude_ids=None):
        """기존 Plan B가 막히거나 미확인이면 같은 권역 10km 내 확인 가능한 대안을 탐색."""
        original = self._plan_b(row)
        excluded = {str(x) for x in (exclude_ids or [])}
        if original and str(original.get("id")) in excluded:
            original = None
        if not self.live_ready or not self._live:
            return original, {"state": "unverified", "changed": False,
                              "message": "실시간 상태를 확인하지 못해 과거 자료의 대체 후보를 표시합니다. 출발 전 상태를 확인해 주세요."}
        if original and original.get("live") and original["live"]["tone"] == "good":
            return original, {"state": "available", "changed": False, "message": "현재 API상 충전 가능한 기존 Plan B입니다."}
        region = row.get("도로권역")
        if pd.isna(region) or not str(region).strip():
            return None, {"state": "none", "changed": False, "message": "도로권역을 확인하지 못해 독립적인 대안을 확정하지 않았습니다."}
        candidates = self.stations[
            (self.stations["도로권역"] == region) &
            (~self.stations["시설 ID"].astype(str).isin(excluded | {str(row["시설 ID"])}))
        ].copy()
        if candidates.empty:
            return None, {"state": "none", "changed": bool(original), "message": "같은 도로권역에서 현재 이용 가능한 대체시설을 찾지 못했습니다."}
        candidates["_backup_km"] = candidates.apply(
            lambda r: distance_km(float(row["위도"]), float(row["경도"]), float(r["위도"]), float(r["경도"])), axis=1)
        # 같은 지점·인접 주차면과 과도하게 먼 대안은 자동 대체하지 않는다.
        candidates = candidates[(candidates["_backup_km"] > 0.05) & (candidates["_backup_km"] <= 10)]
        candidates = candidates.sort_values(["_backup_km", "시설 ID"])
        for _, candidate in candidates.iterrows():
            current = self._live_of(candidate["시설 ID"])
            if not current or current["tone"] != "good":
                continue
            result = self._station(candidate)
            result["from_a_km"] = round(float(candidate["_backup_km"]), 2)
            return result, {"state": "available", "changed": True,
                            "previous_name": original["name"] if original else None,
                            "message": "기존 대안이 이용불가·미확인이거나 없어 같은 도로권역의 직선 10km 이내에서 현재 충전 가능한 Plan B를 다시 찾았습니다."}
        return None, {"state": "none", "changed": bool(original),
                      "previous_name": original["name"] if original else None,
                      "message": "같은 도로권역의 직선 10km 이내에서 현재 충전 가능 상태가 확인된 대안을 찾지 못했습니다. 상태 미확인은 이용 가능으로 간주하지 않았습니다."}

    def recheck_plan_b(self, facility_id, exclude_ids=None):
        if facility_id not in self.by_id.index:
            return {"ok": False, "message": "충전시설을 찾지 못했습니다."}
        self.live()
        row = self.by_id.loc[facility_id].copy()
        row["시설 ID"] = facility_id
        b, search = self._select_plan_b(row, exclude_ids)
        if b and b.get("lat") is not None:
            b["driving"] = driving_route(float(row["위도"]), float(row["경도"]), b["lat"], b["lon"])
        return {"ok": True, "B": b, "plan_b_search": search, "checked_at": self._live_time}

    # ------------------------------------------------------------------ 실행
    def ask(self, query: str, vehicle: str | None = None, battery: int = 40, origin_text: str = "",
            origin_lat: float | None = None, origin_lon: float | None = None,
            preference: str = "균형 추천", count: int = 3,
            context_place: str | None = None, exclude_ids: list[str] | None = None,
            connector: str | None = None, selected_place: dict[str, Any] | None = None) -> dict[str, Any]:
        query = (query or "").strip()
        if vehicle and "기타" in vehicle:
            if not connector or connector == "모름":
                return {"ok": False, "query": query, "trace": [],
                        "summary": "기타 전기차의 충전 규격을 선택해 주세요. 잘 모르겠다면 차량 설명서 또는 충전구 표기를 확인해 주세요. 호환 여부가 확인되기 전에는 추천하지 않습니다."}
            if connector != "DC콤보":
                return {"ok": False, "query": query, "trace": [],
                        "summary": f"선택한 규격은 {connector}입니다. 현재 보유한 추천 데이터는 DC콤보·50kW 이상 시설이므로 해당 규격에 맞는 Plan A·Plan B를 제공할 수 없습니다. 규격이 확인된 다른 충전소 검색 서비스를 이용해 주세요."}
        trace: list[dict[str, str]] = []
        v = self.vehicles[self.vehicles["차량명"] == vehicle]
        v = (v if not v.empty else self.vehicles).iloc[0]
        kwh, eff = float(v["사용가능배터리_kWh"]), float(v["대표전비_km_per_kWh"])

        parsed = llm_agent.parse_with_gemini(query) if llm_agent.is_configured() else None
        if parsed:
            how = f"Gemini {llm_agent.STATE['model']}"
        elif llm_agent.is_configured():
            how = f"규칙 기반 (Gemini {llm_agent.STATE['last_error'] or '응답 없음'})"
        else:
            how = "규칙 기반"
        chosen = None
        if selected_place:
            try:
                chosen = {
                    "id": str(selected_place.get("id") or ""),
                    "name": str(selected_place["name"])[:200],
                    "lat": float(selected_place["lat"]),
                    "lon": float(selected_place["lon"]),
                    "address": str(selected_place.get("address") or "")[:300],
                    "source": "사용자가 선택한 Kakao 장소",
                }
                if not (32.8 <= chosen["lat"] <= 34.0 and 125.8 <= chosen["lon"] <= 127.3):
                    chosen = None
            except (KeyError, TypeError, ValueError):
                chosen = None
        merchant = None if chosen else shop_query(context_place or query)
        place_text = chosen["name"] if chosen else (merchant or context_place or (parsed or {}).get("place") or query)
        origin_text = (parsed or {}).get("origin") or origin_text or ""
        rule_b = any(w in query for w in ["고장", "막히", "막혔", "못 쓰", "대신", "대안"])
        intent = (parsed or {}).get("intent") or ("plan_b" if rule_b else "recommend")
        pref = preference
        pref = pref if pref in PREFERENCES else "균형 추천"
        try:
            battery = int(extract_battery(query) or (battery if "아까랑 같" in query or "그대로" in query else (parsed or {}).get("battery")) or battery)
        except (TypeError, ValueError):
            pass
        battery = max(1, min(int(battery), 100))
        remaining = kwh * eff * battery / 100
        trace.append({"step": "질문 이해", "tag": how,
                      "detail": f"가는 곳 '{place_text}' · 배터리 {battery}% (약 {remaining:.0f}km)"
                                + (f" · 지금 있는 곳 '{origin_text}'" if origin_text else "")})

        mark(2)
        kakao = search_place if self.kakao_ready else None
        dest = chosen
        if dest is None and merchant:
            # 비짓제주에 고정된 장소는 먼저 확정하고, 외부 검색만 복수 후보를 확인한다.
            dest = resolve_shop(merchant, None)
            if dest is None and self.kakao_ready:
                candidates = search_places(merchant)
                if _needs_place_choice(merchant, candidates):
                    return {"ok": False, "query": query, "battery": battery, "trace": trace,
                            "place_retry": merchant, "clarify": True, "clarification_type": "place_candidates",
                            "preference": pref, "place_candidates": _place_candidates_payload(candidates),
                            "summary": f"‘{merchant}’과 이름이 비슷한 장소가 여러 곳이에요. 주소를 보고 가려는 지점을 선택해 주세요."}
                dest = resolve_shop(merchant, lambda _: candidates[0] if candidates else None)
        elif dest is None:
            # 내장 관광지·충전소·읍면동을 먼저 찾고, 없을 때만 카카오 후보를 조회한다.
            dest = resolve_place(self.stations, self.spots, place_text, None)
            if dest is None and self.kakao_ready:
                candidates = search_places(place_text)
                if _needs_place_choice(place_text, candidates):
                    return {"ok": False, "query": query, "battery": battery, "trace": trace,
                            "place_retry": place_text, "clarify": True, "clarification_type": "place_candidates",
                            "preference": pref, "place_candidates": _place_candidates_payload(candidates),
                            "summary": f"‘{place_text}’ 검색 결과가 여러 곳이에요. 주소를 보고 가려는 장소를 선택해 주세요."}
                dest = candidates[0] if candidates else None
        if merchant and dest is None:
            return {"ok": False, "query": query, "battery": battery, "trace": trace,
                    "place_retry": merchant, "clarify": True, "preference": pref,
                    "summary": f"‘{merchant}’은 어느 동네에 있는 곳인가요? 동네와 지점명, 또는 대신 기준으로 삼을 가까운 명소를 알려주세요."}
        if dest is None and place_text != query:
            dest = resolve_place(self.stations, self.spots, query, kakao)

        mark(3)
        if (intent == "plan_b" and not merchant) or dest is None:
            _, results = recommend(self.stations, place_text, pref, max(count + 8, 12))
            if dest is None and not results.empty:
                f = results.iloc[0]
                dest = {"name": f["충전소명"], "lat": float(f["위도"]), "lon": float(f["경도"]), "source": "충전소 데이터"}
            if not results.empty and dest is not None:
                results = results.copy()
                results["목적지거리km"] = results.apply(lambda r: distance_km(dest["lat"], dest["lon"], r["위도"], r["경도"]), axis=1)
        else:
            results = recommend_near_coordinate(self.stations, dest["name"], dest["lat"], dest["lon"], pref, max(count + 8, 12))

        exclude_ids = [str(x) for x in (exclude_ids or []) if x]
        if exclude_ids and not results.empty:
            results = results[~results["시설 ID"].astype(str).isin(exclude_ids)].copy()

        if not results.empty:
            # 제주데이터허브 과거 충전 이력: 현재 시간이 과거 피크와 겹치면 소폭 감점한다.
            # 운영 상태와 거리를 압도하지 않도록 최대 7점으로 제한한다.
            score_col = "최종추천점수" if "최종추천점수" in results else "사용자추천점수"
            penalties = results.apply(
                lambda r: (self.datahub.station_context(
                    r["시설 ID"], r.get("충전소명"), r.get("읍면동")
                ) or {}).get("penalty", 0), axis=1
            )
            results[score_col] = results[score_col] - penalties
            results = results.sort_values([score_col, "상태위험축"], ascending=[False, True], na_position="last")

        if dest is None or results.empty:
            trace.append({"step": "장소 찾기", "tag": "", "detail": "일치하는 장소를 찾지 못했어요"})
            return {"ok": False, "query": query, "trace": trace, "clarify": True,
                    "battery": battery, "preference": pref,
                    "summary": (f"‘{dest['name']}’ 주변에는 현재 조건에 맞는 후보가 없어요. 어느 인근 장소까지 찾아볼까요?" if dest else
                                "어느 동네로 가시나요? 정확한 가게 이름이나 기준으로 삼을 가까운 명소를 알려주세요.")}

        trace.append({"step": "장소 찾기", "tag": dest.get("source", ""), "detail": dest["name"]})
        if context_place:
            trace.append({"step": "대화 맥락 복원", "tag": "LangGraph Memory", "detail": f"이전 목적지 '{context_place}' 유지"})
        if exclude_ids:
            trace.append({"step": "후속 조건 반영", "tag": f"제외 {len(exclude_ids)}곳", "detail": "이전 추천에서 제외 요청한 시설을 후보에서 제거"})
        trace.append({"step": "주변 충전소 비교", "tag": f"후보 {len(results)}곳",
                      "detail": "과거 운영 기록 · 제주데이터허브 혼잡 시간대 · 급속충전기 수 · 거리"})
        mark(4)
        live = self.live()
        if live:
            results = apply_live(results, live)
            trace.append({"step": "실시간 상태 반영", "tag": f"환경공단 {self._live_time}", "detail": "지금 비어 있는 곳을 앞으로"})
        else:
            trace.append({"step": "실시간 상태", "tag": "미연결", "detail": "과거 관측 기록으로 판단"})

        origin = None
        if origin_lat is not None and origin_lon is not None:
            origin = {"name": "내 위치", "lat": float(origin_lat), "lon": float(origin_lon), "source": "기기 위치"}
        elif origin_text:
            origin = resolve_place(self.stations, self.spots, origin_text, kakao)
        start = origin or dest
        pool = results.copy()
        # Do not trade confirmed availability for a marginally faster trip.
        pool["_availability"] = pool["시설 ID"].map(lambda fid: {"good":0,"muted":1,"warn":2,"bad":2}.get((self._live_of(fid) or {}).get("tone"),1))
        pool["_distance"] = pool.apply(lambda r: distance_km(start["lat"],start["lon"],r["위도"],r["경도"]),axis=1)
        pool["_range"] = pool["_distance"].map(lambda d: 0 if not origin or range_check(remaining,d)[0] else 1)
        pool = pool.sort_values(["_range","_availability"],kind="stable")
        eligible = pool[(pool["_range"]==pool.iloc[0]["_range"]) & (pool["_availability"]==pool.iloc[0]["_availability"])].copy()
        basis = "거리·운영기록·충전 이력 종합"
        if pref == "이동시간 우선":
            from concurrent.futures import ThreadPoolExecutor
            eligible = eligible.sort_values("_distance",kind="stable").head(5).copy()
            def lookup(r):
                return driving_route(start["lat"],start["lon"],r["위도"],r["경도"]) if self.kakao_ready else None
            with ThreadPoolExecutor(max_workers=3) as executor:
                routes = list(executor.map(lookup,(row for _,row in eligible.iterrows())))
            if any(routes):
                eligible["_time"] = [route["minutes"] if route else float("inf") for route in routes]
                eligible = eligible.sort_values(["_time","_distance"])
                basis = "인접 후보 중 확인된 차량시간 비교"
            else:
                basis = "차량시간 미확인 · 직선거리 순"
        elif pref == "대기 위험 우선":
            def congestion(r):
                ctx = self.datahub.station_context(r["시설 ID"],r.get("충전소명"),r.get("읍면동")) or {}
                return {"low":0,"medium":1,"high":3}.get(ctx.get("level"),2)
            eligible["_risk"] = eligible.apply(congestion,axis=1)
            eligible = eligible.sort_values("_risk",kind="stable")
            basis = "과거 혼잡 낮음 → 보통 → 자료 없음 → 높음"
        elif pref == "Plan B 우선":
            def backup_key(r):
                b, status = self._select_plan_b(r,exclude_ids)
                return (0 if status["state"]=="available" else 1 if b else 2, b["from_a_km"] if b else float("inf"))
            eligible["_backup"] = eligible.apply(backup_key,axis=1)
            eligible = eligible.sort_values("_backup",kind="stable")
            basis = "현재 확인된 대안 우선 · 같은 조건은 대체거리 순"
        results = eligible.head(count)
        top = results.iloc[0]
        reach, origin_km = None, None
        if origin:
            origin_km = distance_km(origin["lat"], origin["lon"], float(top["위도"]), float(top["경도"]))
            reach = range_check(remaining, origin_km)
            trace.append({"step": "배터리 확인", "tag": "도착 가능" if reach[0] else "빠듯함",
                          "detail": f"{origin['name']} → {top['충전소명']} 직선 {origin_km:.1f}km"})

        a = self._station(top, dest)
        start = origin or dest
        a["route_straight_km"] = round(origin_km, 2) if origin_km is not None else a.get("from_dest_km")
        a["driving"] = driving_route(start["lat"], start["lon"], a["lat"], a["lon"])
        if origin and reach:
            a["reach"] = {"ok": reach[0], "text": "현재 배터리로 이동 가능" if reach[0] else "배터리 여유 확인 필요",
                          "from": origin["name"], "km": round(origin_km, 1)}
        mark(5)
        b, b_search = self._select_plan_b(top, exclude_ids)
        if b and b["lat"] is not None:
            b["driving"] = driving_route(a["lat"], a["lon"], b["lat"], b["lon"])
        if b and origin and b["lat"] is not None:
            b_km = origin_km + b["from_a_km"]
            b_reach = range_check(remaining, b_km)
            b["reach"] = {"ok": b_reach[0], "text": "현재 배터리로 이동 가능" if b_reach[0] else "배터리 여유 확인 필요",
                          "from": start["name"], "km": round(b_km, 1)}
        b_route_tag = (f"차로 약 {b['driving']['minutes']}분" if b and b.get("driving") else
                       (f"직선 {b['from_a_km']:.1f}km" if b else "없음"))
        trace.append({"step": "Plan B 계산", "tag": b_route_tag,
                      "detail": b["name"] if b else "가까운 독립 대안 없음"})

        notes: list[dict[str, str]] = []
        notes.append({"tone": "info" if b_search["state"] == "available" else "warn", "text": b_search["message"]})
        if reach:
            notes.append({"tone": "ok" if reach[0] else "warn", "text": reach[1]})
        for w in station_warnings(top):
            notes.append({"tone": "warn", "text": w})
        if b and b["from_a_km"] < 0.2 and str(top.get("동일장소검증필요", "N")) != "Y":
            notes.append({"tone": "warn", "text": "Plan B가 같은 건물·단지일 수 있어요. 함께 막힐 수 있으니 다른 후보도 봐 두세요."})
        fix = top.get("좌표보정")
        if isinstance(fix, str) and fix.strip():
            notes.append({"tone": "info", "text": f"위치 안내: {fix}"})

        facts = {
            "가는곳": dest["name"], "배터리": f"{battery}%", "남은주행거리km": round(remaining),
            "추천충전소": a["name"], "추천충전소이동기준": start["name"],
            "추천충전소까지직선거리km": a["route_straight_km"],
            "추천충전소까지도로거리km": (a["driving"] or {}).get("distance_km"),
            "추천충전소까지차량시간분": (a["driving"] or {}).get("minutes"),
            "평소운영": a["reliability"]["text"], "현재상태": a["live"]["text"] if a["live"] else "실시간 미확인",
            "급속충전기수": a["chargers"], "PlanB": b["name"] if b else "없음",
            "PlanB거리km": b["from_a_km"] if b else None,
            "PlanB차량시간분": ((b.get("driving") or {}).get("minutes") if b else None),
            "PlanB현재상태": (b["live"]["text"] if b and b["live"] else "실시간 미확인"),
            "PlanB재탐색": b_search["message"],
            "경고": [n["text"] for n in notes if n["tone"] == "warn"],
        }
        mark(6)
        summary = llm_agent.summarize_with_gemini(facts) if llm_agent.is_configured() else None
        writer = f"Gemini {llm_agent.STATE['model']}" if summary else "정해진 문장"
        if not summary:
            rel = {"평소 잘 운영됨": "평소 운영이 안정적인 곳이에요", "가끔 이용 불가": "가끔 이용이 안 될 때가 있는 곳이에요",
                   "자주 이용 불가": "평소 이용이 안 될 때가 많아 주의가 필요해요", "운영 기록 부족": "운영 기록이 부족한 곳이에요"}
            summary = f"{dest['name']} 근처에서는 {a['name']}을(를) 추천해요. {rel[a['reliability']['text']]}."
            if b:
                route_text = (f"차로 약 {b['driving']['minutes']}분" if b.get("driving") else
                              f"직선 {b['from_a_km']:.1f}km, 차량경로 미확인")
                summary += (f" 막히면 {b['name']}({route_text})를 대안으로 확인해 보세요." if b_search["state"] == "available" else f" 대체 후보는 {b['name']}({route_text})이며 현재 상태는 미확인입니다.")
            if b_search["changed"] or not b:
                summary += " " + b_search["message"]
            if battery <= 35:
                summary += f" 배터리 {battery}%면 약 {remaining:.0f}km 갈 수 있으니 여유 있게 충전해 두세요."
        trace.append({"step": "답변 작성", "tag": writer, "detail": "계산된 사실만 근거로 작성"})

        alts = [self._station(r, dest) for _, r in results.iloc[1:].iterrows()]
        return {
            "ok": True, "preference":pref, "basis":basis, "query": query, "summary": summary, "highlight": [a["name"]] + ([b["name"]] if b else []),
            "dest": {"name": dest["name"], "lat": dest["lat"], "lon": dest["lon"], "source": dest.get("source", "")},
            "origin": ({"name": origin["name"], "lat": origin["lat"], "lon": origin["lon"],
                        "to_a_km": round(origin_km, 1)} if origin else None),
            "A": a, "B": b, "backup_excluded_ids": exclude_ids, "plan_b_search": b_search, "alternatives": alts, "notes": notes, "trace": trace,
            "battery": battery, "remaining_km": round(remaining),
            "insight": {"alt3km": int(_num(top.get("3km이내대체시설수"), 0)), "nearest_alt_km": b["from_a_km"] if b else None,
                        "remaining_km": round(remaining)},
            "live_time": self._live_time if live else None,
        }
