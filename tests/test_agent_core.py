from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_core import (
    find_tourist_spot, load_station_data, load_tourist_spots,
    recommend, recommend_near_coordinate,
)

DATA = load_station_data(ROOT / "data" / "stations.csv")
SPOTS = load_tourist_spots(ROOT / "data" / "tourist_spots.csv")


def test_dataset_shape_and_keys():
    assert len(DATA) == 900
    assert DATA["시설 ID"].is_unique


def test_natural_language_place_extraction():
    _, result = recommend(DATA, "성판악 근처에서 안정적인 곳 알려줘", "균형 추천", 3)
    assert not result.empty
    assert result["충전소명"].str.contains("성판악").any()


def test_regional_search():
    _, result = recommend(DATA, "애월읍에서 대체시설이 많은 충전소", "균형 추천", 5)
    assert len(result) == 5
    assert (result["읍면동"] == "애월읍").all()


def test_plan_b_is_attached():
    _, result = recommend(DATA, "어리목 공영주차장이 고장이면 어디로 가?", "균형 추천", 1)
    assert len(result) == 1
    assert result.iloc[0]["PlanB대표충전소명"]


def test_tourist_spot_coordinate_recommendation():
    spot = find_tourist_spot(SPOTS, "내일 성산일출봉에 갈 예정이야")
    assert spot and spot["name"] == "성산일출봉"
    result = recommend_near_coordinate(DATA, spot["name"], spot["lat"], spot["lon"], limit=3)
    assert len(result) == 3
    assert result["목적지거리km"].max() <= 10



from agent_core import (  # noqa: E402
    apply_live, extract_battery, live_text, range_check, reliability_text, resolve_place,
)


def test_coordinate_fix_applied():
    row = DATA[DATA["충전소명"] == "영실매표소"].iloc[0]
    twin = DATA[DATA["충전소명"] == "영실 공영주차장"].iloc[0]
    assert abs(row["위도"] - twin["위도"]) < 1e-6
    assert row["PlanB대표충전소명"] != "영실 공영주차장"


def test_destination_station_is_preferred_when_close():
    spot = find_tourist_spot(SPOTS, "내일 어리목에서 한라산 탐방해")
    result = recommend_near_coordinate(DATA, spot["name"], spot["lat"], spot["lon"], limit=3)
    assert result.iloc[0]["충전소명"] == "어리목 공영주차장"


def test_plain_language_helpers():
    assert reliability_text(0.02)[0] == "평소 잘 운영됨"
    assert reliability_text(0.5)[1] == "bad"
    assert live_text({"available": 2, "charging": 1, "total": 3})[0] == "지금 2대 비어 있음"
    assert live_text({"available": 0, "charging": 3, "total": 3})[0] == "지금 모두 충전 중"
    assert extract_battery("배터리 30%야") == 30
    assert range_check(100, 10)[0] is True
    assert range_check(15, 20)[0] is False


def test_live_status_reorders_candidates():
    spot = find_tourist_spot(SPOTS, "성산일출봉")
    result = recommend_near_coordinate(DATA, spot["name"], spot["lat"], spot["lon"], limit=3)
    first, second = result.iloc[0], result.iloc[1]
    live = {str(first["대표충전소 ID"]): {"available": 0, "charging": 0, "total": 2},
            str(second["대표충전소 ID"]): {"available": 2, "charging": 0, "total": 2}}
    reordered = apply_live(result, live)
    assert reordered.iloc[0]["시설 ID"] == second["시설 ID"]


def test_resolve_place_by_region_name():
    place = resolve_place(DATA, SPOTS, "애월읍 근처")
    assert place and place["name"] == "애월읍"
