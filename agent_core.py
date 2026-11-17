"""제주 EV Plan B Agent의 데이터 검색·판단 로직."""

from __future__ import annotations

import re
import math
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd


NUMERIC_COLUMNS = [
    "위도", "경도", "Plan B 거리(km)", "조건충족충전기수", "상태위험축",
    "예측이용가능성", "3km이내대체시설수", "In-degree", "영향축백분위",
    "수요노출백분위", "PlanB_충전기수", "PlanB_상태위험축", "PlanB_위도",
    "PlanB_경도", "미확인비율",
]


@dataclass(frozen=True)
class AgentPlan:
    intent: str
    place: str
    preference: str
    explanation: str


def load_station_data(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    for column in NUMERIC_COLUMNS:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    validate_data(df)
    return df


def load_tourist_spots(path: str | Path) -> pd.DataFrame:
    spots = pd.read_csv(path)
    for column in ["위도", "경도"]:
        spots[column] = pd.to_numeric(spots[column], errors="coerce")
    return spots.dropna(subset=["관광지명", "위도", "경도"])


def find_tourist_spot(spots: pd.DataFrame, query: str) -> dict[str, Any] | None:
    q = normalize(query)
    matches = []
    for _, row in spots.iterrows():
        terms = [row["관광지명"]] + str(row.get("검색별칭", "")).split()
        for term in terms:
            token = normalize(term)
            if len(token) >= 2 and token in q:
                matches.append((len(token), row))
    if not matches:
        return None
    row = max(matches, key=lambda item: item[0])[1]
    return {
        "name": row["관광지명"], "lat": float(row["위도"]), "lon": float(row["경도"]),
        "address": "", "source": row.get("좌표근거", "내장 관광지 데이터"),
    }


def validate_data(df: pd.DataFrame) -> None:
    required = {
        "시설 ID", "충전소명", "주소", "읍면동", "위도", "경도", "상태위험축",
        "조건충족충전기수", "PlanB대표충전소명", "Plan B 거리(km)",
        "3km이내대체시설수", "절대고립조건", "동일장소검증필요",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"필수 데이터 열이 없습니다: {', '.join(missing)}")
    if df.empty:
        raise ValueError("충전소 데이터가 비어 있습니다.")
    if df["시설 ID"].duplicated().any():
        raise ValueError("시설 ID가 중복되어 있습니다.")


def normalize(value: Any) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", str(value or "").lower())


def detect_preference(query: str, default: str = "균형 추천") -> str:
    q = normalize(query)
    if any(word in q for word in ["안정", "고장적", "잘되는", "운영", "안전"]):
        return "운영 안정성"
    if any(word in q for word in ["대체", "플랜b", "planb", "여유", "여러곳"]):
        return "대체시설 여유"
    return default


def build_plan(df: pd.DataFrame, query: str, default_preference: str) -> AgentPlan:
    q = normalize(query)
    intent = "plan_b" if any(x in q for x in ["플랜b", "planb", "대체", "못쓰", "고장"]) else "recommend"
    places: list[str] = []
    for column in ["충전소명", "읍면동"]:
        for value in df[column].dropna().astype(str).unique():
            token = normalize(value)
            if len(token) >= 2 and token in q:
                places.append(value)
    place = max(places, key=lambda x: len(normalize(x)), default=query.strip())
    preference = detect_preference(query, default_preference)
    if intent == "plan_b" and preference == "균형 추천":
        preference = "대체시설 여유"
    return AgentPlan(intent, place, preference, f"장소 ‘{place}’를 찾고 {preference} 기준으로 후보를 비교합니다.")


def _match_candidates(df: pd.DataFrame, place: str) -> pd.DataFrame:
    p = normalize(place)
    matched = pd.Series(False, index=df.index)
    for column in ["충전소명", "주소", "읍면동"]:
        values = df[column].fillna("").map(normalize)
        matched |= values.str.contains(p, regex=False)
        matched |= values.map(lambda value: bool(value) and value in p)
    direct = df[matched].copy()
    if not direct.empty:
        direct["검색일치도"] = 1.0
        return direct

    tokens = [normalize(t) for t in re.findall(r"[0-9A-Za-z가-힣]+", place) if len(normalize(t)) >= 2]
    if not tokens:
        return df.iloc[0:0].copy()
    scored = df.copy()
    scored["검색일치도"] = scored["충전소명"].fillna("").map(
        lambda name: max(SequenceMatcher(None, token, normalize(name)).ratio() for token in tokens)
    )
    return scored[scored["검색일치도"] >= 0.55].sort_values("검색일치도", ascending=False).head(20)


def _haversine_km(lat1: float, lon1: float, lat2: pd.Series, lon2: pd.Series) -> pd.Series:
    """기준 좌표에서 모든 시설까지의 직선거리를 계산한다."""
    phi1 = math.radians(lat1)
    phi2 = lat2.map(math.radians)
    dphi = phi2 - phi1
    dlambda = lon2.map(math.radians) - math.radians(lon1)
    a = (dphi / 2).map(math.sin) ** 2 + math.cos(phi1) * phi2.map(math.cos) * (dlambda / 2).map(math.sin) ** 2
    return 6371.0088 * 2 * a.map(lambda value: math.asin(min(1, math.sqrt(max(0, value)))))


def score_station(row: pd.Series, preference: str) -> float:
    risk = row.get("상태위험축")
    risk = 0.5 if pd.isna(risk) else min(max(float(risk), 0), 1)
    availability = 1 - risk
    chargers = min(float(row.get("조건충족충전기수", 0) or 0) / 4, 1)
    alternatives = min(float(row.get("3km이내대체시설수", 0) or 0) / 10, 1)
    distance = row.get("Plan B 거리(km)")
    distance = 5 if pd.isna(distance) else max(float(distance), 0)
    proximity = 1 - min(distance / 5, 1)
    weights = {
        "운영 안정성": (0.55, 0.15, 0.15, 0.15),
        "대체시설 여유": (0.30, 0.15, 0.35, 0.20),
        "균형 추천": (0.35, 0.20, 0.20, 0.25),
    }.get(preference, (0.35, 0.20, 0.20, 0.25))
    score = 100 * sum(w * v for w, v in zip(weights, [availability, chargers, alternatives, proximity]))
    if str(row.get("동일장소검증필요", "N")) == "Y":
        score -= 12
    elif not pd.isna(row.get("Plan B 거리(km)")) and float(row.get("Plan B 거리(km)")) < 0.2:
        score -= 8   # 200m 안의 Plan B는 같은 건물·단지일 가능성이 있어 함께 막힐 수 있다
    if str(row.get("절대고립조건", "N")) == "Y":
        score -= 15
    return round(max(score, 0), 1)


def recommend(df: pd.DataFrame, query: str, preference: str = "균형 추천", limit: int = 5):
    plan = build_plan(df, query, preference)
    candidates = _match_candidates(df, plan.place)
    if candidates.empty:
        return plan, candidates
    # 특정 시설·관광지가 검색된 일반 추천은 주변 5km 후보까지 확장한다.
    # Plan B를 직접 묻거나 읍면동을 입력한 경우에는 해당 범위만 유지한다.
    is_region = plan.place in set(df["읍면동"].dropna().astype(str))
    if plan.intent == "recommend" and not is_region:
        anchor = candidates.sort_values("검색일치도", ascending=False).iloc[0]
        distances = _haversine_km(float(anchor["위도"]), float(anchor["경도"]), df["위도"], df["경도"])
        nearby = df[distances <= 5].copy()
        nearby["검색거리km"] = distances[distances <= 5]
        nearby["검색일치도"] = (1 - nearby["검색거리km"] / 5).clip(lower=0)
        exact_ids = set(candidates["시설 ID"])
        nearby.loc[nearby["시설 ID"].isin(exact_ids), "검색일치도"] = 1.0
        candidates = nearby
    candidates = candidates.copy()
    candidates["사용자추천점수"] = candidates.apply(lambda row: score_station(row, plan.preference), axis=1)
    candidates = candidates.sort_values(
        ["검색일치도", "사용자추천점수", "상태위험축"],
        ascending=[False, False, True], na_position="last",
    ).head(limit)
    return plan, candidates


def recommend_near_coordinate(
    df: pd.DataFrame,
    place_name: str,
    latitude: float,
    longitude: float,
    preference: str = "균형 추천",
    limit: int = 5,
    radius_km: float = 10,
):
    distances = _haversine_km(float(latitude), float(longitude), df["위도"], df["경도"])
    candidates = df[distances <= radius_km].copy()
    if candidates.empty:
        return candidates
    candidates["목적지거리km"] = distances[distances <= radius_km]
    candidates["사용자추천점수"] = candidates.apply(lambda row: score_station(row, preference), axis=1)
        # 관광객은 가는 곳에서 가까운 충전소를 원하므로 5km 안 근접성을 40% 반영한다.
    distance_score = (1 - candidates["목적지거리km"] / 5).clip(lower=0) * 100
    candidates["최종추천점수"] = (0.6 * candidates["사용자추천점수"] + 0.4 * distance_score).round(1)
    candidates["검색기준장소"] = place_name
    return candidates.sort_values(
        ["최종추천점수", "목적지거리km", "상태위험축"],
        ascending=[False, True, True], na_position="last",
    ).head(limit)


def risk_label(value: Any) -> str:
    if pd.isna(value):
        return "자료 부족"
    if float(value) >= 0.5:
        return "높음"
    if float(value) >= 0.2:
        return "주의"
    return "낮음"


def station_reasons(row: pd.Series) -> list[str]:
    reasons: list[str] = []
    if pd.notna(row.get("상태위험축")):
        reasons.append(f"관측 운영위험 {risk_label(row.get('상태위험축'))}")
    if pd.notna(row.get("조건충족충전기수")):
        reasons.append(f"분석 대상 급속충전기 {int(row.get('조건충족충전기수'))}기")
    if pd.notna(row.get("3km이내대체시설수")):
        reasons.append(f"3km 안 대체시설 {int(row.get('3km이내대체시설수'))}곳")
    return reasons


def station_warnings(row: pd.Series) -> list[str]:
    warnings: list[str] = []
    if str(row.get("절대고립조건", "N")) == "Y":
        warnings.append("주변의 독립적인 대체시설이 부족합니다. 출발 전에 배터리 여유를 확보하세요.")
    if str(row.get("동일장소검증필요", "N")) == "Y":
        warnings.append("가장 가까운 대안이 같은 장소일 가능성이 있어 별도 대안 확인이 필요합니다.")
    unknown = row.get("미확인비율")
    if pd.notna(unknown) and float(unknown) >= 0.3:
        warnings.append("상태 미확인 비율이 높아 실제 이용 가능 여부를 반드시 확인하세요.")
    return warnings


def kakao_link(name: str, lat: Any, lon: Any) -> str:
    if pd.isna(lat) or pd.isna(lon):
        return f"https://map.kakao.com/?q={quote(str(name))}"
    return f"https://map.kakao.com/link/to/{quote(str(name))},{lat},{lon}"



# ---------------------------------------------------------------------------
# 사용자 화면용 도우미 (v4)
# ---------------------------------------------------------------------------
ROAD_FACTOR = 1.3      # 직선거리 → 도로거리 보정 계수 (참고값)
RESERVE_KM = 10        # 도착 후 남겨둘 최소 여유 주행거리


def reliability_text(value: Any) -> tuple[str, str]:
    """과거 관측 상태위험을 관광객이 이해할 말로 바꾼다. (문구, 톤)"""
    if pd.isna(value):
        return "운영 기록 부족", "muted"
    v = float(value)
    if v < 0.1:
        return "평소 잘 운영됨", "good"
    if v < 0.3:
        return "가끔 이용 불가", "warn"
    return "자주 이용 불가", "bad"


def live_text(info: dict | None) -> tuple[str, str] | None:
    """실시간 요약을 (문구, 톤)으로 바꾼다. 정보가 없으면 None."""
    if not info or not info.get("total"):
        return None
    if info["available"] > 0:
        return f"지금 {info['available']}대 비어 있음", "good"
    if info.get("charging", 0) > 0:
        return "지금 모두 충전 중", "warn"
    return "지금 이용 불가 표시", "bad"


def apply_live(candidates: pd.DataFrame, live: dict[str, dict]) -> pd.DataFrame:
    """실시간 상태를 후보 순위에 반영한다. 비어 있으면 가점, 모두 막혀 있으면 감점."""
    if candidates.empty or not live:
        return candidates
    out = candidates.copy()
    infos = out["대표충전소 ID"].astype(str).map(lambda sid: live.get(sid))
    bonus = infos.map(lambda i: 0 if not isinstance(i, dict) or not i.get("total") else (10 if i["available"] > 0 else -25))
    score_col = "최종추천점수" if "최종추천점수" in out else "사용자추천점수"
    out[score_col] = (out[score_col] + bonus).round(1)
    out["실시간반영"] = bonus
    return out.sort_values(score_col, ascending=False)


def road_km(straight_km: float) -> float:
    return straight_km * ROAD_FACTOR


def range_check(remaining_km: float, straight_km: float | None) -> tuple[bool, str] | None:
    """남은 주행거리로 도착 가능한지 참고 판단한다."""
    if straight_km is None or pd.isna(straight_km):
        return None
    need = road_km(float(straight_km)) + RESERVE_KM
    if remaining_km >= need:
        return True, f"남은 배터리로 충분히 갈 수 있어요 (필요 약 {need:.0f}km / 남은 약 {remaining_km:.0f}km)"
    return False, f"배터리가 빠듯해요. 도로 기준 약 {road_km(float(straight_km)):.0f}km 거리라 먼저 가까운 곳에서 충전하세요."


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(h))


def resolve_place(stations: pd.DataFrame, spots: pd.DataFrame, text: str, kakao_search=None) -> dict[str, Any] | None:
    """관광지 → Kakao 장소검색 → 충전소명·읍면동 순으로 위치를 찾는다."""
    if not text or not str(text).strip():
        return None
    spot = find_tourist_spot(spots, text)
    if spot:
        return spot
    if kakao_search:
        found = kakao_search(text)
        if found:
            return found
    q = normalize(text)
    for column in ["충전소명", "읍면동"]:
        names = stations[column].dropna().astype(str)
        hits = names[names.map(lambda v: len(normalize(v)) >= 2 and (normalize(v) in q or q in normalize(v)))]
        if not hits.empty:
            best = max(hits.unique(), key=lambda v: len(normalize(v)))
            rows = stations[stations[column].astype(str) == best]
            return {"name": best, "lat": float(rows["위도"].mean()), "lon": float(rows["경도"].mean()),
                    "address": "", "source": "충전소·읍면동 데이터"}
    return None


def extract_battery(text: str) -> int | None:
    m = re.search(r"(\d{1,3})\s*(%|퍼센트|프로)", text or "")
    if m and 0 < int(m.group(1)) <= 100:
        return int(m.group(1))
    return None
