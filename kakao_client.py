"""Kakao Local·Mobility API를 이용한 장소 검색과 자동차 경로 조회."""

from __future__ import annotations

import math
import os
from functools import lru_cache
from typing import Any

import requests


KAKAO_LOCAL_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
KAKAO_DIRECTIONS_URL = "https://apis-navi.kakaomobility.com/v1/directions"


def search_place(keyword: str) -> dict[str, Any] | None:
    api_key = os.getenv("KAKAO_REST_API_KEY", "").strip()
    if not api_key or not keyword.strip():
        return None
    try:
        response = requests.get(
            KAKAO_LOCAL_URL,
            headers={"Authorization": f"KakaoAK {api_key}"},
            params={"query": f"제주 {keyword}", "size": 5},
            timeout=6,
        )
        response.raise_for_status()
        documents = response.json().get("documents", [])
        if not documents:
            return None
        # 제주도 안의 결과를 우선한다.
        selected = next((d for d in documents if d.get("address_name", "").startswith("제주")), None)
        if not selected:
            return None
        return {
            "name": selected.get("place_name") or keyword,
            "lat": float(selected["y"]),
            "lon": float(selected["x"]),
            "address": selected.get("road_address_name") or selected.get("address_name", ""),
            "source": "Kakao Local API",
        }
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return None


@lru_cache(maxsize=512)
def _driving_route_cached(origin_lon: float, origin_lat: float, dest_lon: float, dest_lat: float) -> dict[str, Any] | None:
    """카카오모빌리티 추천 자동차 경로의 거리, 시간, 지도 좌표를 반환한다."""
    api_key = os.getenv("KAKAO_REST_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        response = requests.get(
            KAKAO_DIRECTIONS_URL,
            headers={"Authorization": f"KakaoAK {api_key}", "Content-Type": "application/json"},
            params={
                "origin": f"{origin_lon},{origin_lat}",
                "destination": f"{dest_lon},{dest_lat}",
                "priority": "RECOMMEND",
                "summary": "false",
                "alternatives": "false",
                "road_details": "false",
            },
            timeout=8,
        )
        response.raise_for_status()
        routes = response.json().get("routes", [])
        if not routes:
            return None
        route = routes[0]
        if route.get("result_code", 0) != 0:
            return None
        summary = route["summary"]
        seconds, meters = int(summary["duration"]), int(summary["distance"])
        if seconds < 0 or meters < 0:
            return None

        coordinates = []
        for section in route.get("sections", []):
            for road in section.get("roads", []):
                vertices = road.get("vertexes", [])
                if len(vertices) < 2 or len(vertices) % 2:
                    return None
                for lon, lat in zip(vertices[::2], vertices[1::2]):
                    point = [float(lat), float(lon)]
                    if not (-90 <= point[0] <= 90 and -180 <= point[1] <= 180):
                        return None
                    if not coordinates or point != coordinates[-1]:
                        coordinates.append(point)
        result = {
            "minutes": max(1, round(seconds / 60)),
            "distance_km": round(meters / 1000, 1),
            "source": "Kakao Mobility",
        }
        if len(coordinates) >= 2:
            result["coordinates"] = coordinates
        return result
    except (requests.RequestException, AttributeError, KeyError, TypeError, ValueError, OverflowError):
        return None


def driving_route(origin_lat: float | None, origin_lon: float | None,
                  dest_lat: float | None, dest_lon: float | None) -> dict[str, Any] | None:
    """좌표가 유효할 때만 자동차 경로를 조회한다. 캐시 키는 소수점 5자리다."""
    try:
        coordinates = tuple(float(value) for value in (origin_lon, origin_lat, dest_lon, dest_lat))
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in coordinates):
        return None
    origin_x, origin_y, dest_x, dest_y = coordinates
    if abs(origin_x - dest_x) + abs(origin_y - dest_y) < 0.00005:
        return {"minutes": 0, "distance_km": 0.0, "source": "same_location", "coordinates": []}
    if not os.getenv("KAKAO_REST_API_KEY", "").strip():
        return None
    return _driving_route_cached(*(round(value, 5) for value in coordinates))
