"""좌표 오류 보정 스크립트.

같은 주소인데 좌표가 수 km 떨어진 시설 2곳을 같은 장소로 보정하고,
보정에 영향을 받는 시설의 Plan B 정보를 다시 계산한다.

- 영실매표소(F0614): 주소 '영실로 246'이 영실 공영주차장(F0462)과 같지만
  좌표가 한라산 동쪽(남원읍)에 찍혀 있음 → F0462 좌표로 보정
- 성판악 공영주차장(F0382): 주소 '516로 1865'가 성판악(F0774)과 같지만
  좌표가 약 4.8km 떨어져 있음 → F0774 좌표로 보정

보정된 두 쌍은 같은 장소이므로 서로를 Plan B로 보지 않는다.
실행: python tools/fix_coordinates.py
"""
from pathlib import Path
import math
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "stations.csv"
FIX = {"F0614": "F0462", "F0382": "F0774"}          # 보정 대상 → 기준 시설
SAME_SITE = {frozenset(p) for p in FIX.items()}


def km(a, b, c, d):
    p1, p2 = math.radians(a), math.radians(c)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(d - b) / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(h))


def main():
    df = pd.read_csv(PATH)
    idx = df.set_index("시설 ID")
    if "좌표보정" not in df.columns:
        df["좌표보정"] = ""
    for bad, good in FIX.items():
        i = df.index[df["시설 ID"] == bad][0]
        df.loc[i, ["위도", "경도"]] = idx.loc[good, ["위도", "경도"]].values
        df.loc[i, "좌표보정"] = f"주소가 같은 {idx.loc[good, '충전소명']} 좌표로 보정"
    idx = df.set_index("시설 ID")

    affected = set(FIX) | set(FIX.values())
    affected |= set(df.loc[df["PlanB시설그룹아이디"].isin(FIX), "시설 ID"])
    for fid in sorted(affected):
        me = idx.loc[fid]
        others = idx[(idx.index != fid) & (idx["도로권역"] == me["도로권역"])]
        others = others[[frozenset((fid, o)) not in SAME_SITE for o in others.index]]
        dist = others.apply(lambda r: km(me["위도"], me["경도"], r["위도"], r["경도"]), axis=1)
        i = df.index[df["시설 ID"] == fid][0]
        if dist.empty:
            continue
        nb = dist.idxmin()
        df.loc[i, "PlanB시설그룹아이디"] = nb
        df.loc[i, "PlanB대표충전소명"] = idx.loc[nb, "충전소명"]
        df.loc[i, "Plan B 거리(km)"] = round(float(dist.min()), 6)
        df.loc[i, ["PlanB_위도", "PlanB_경도"]] = idx.loc[nb, ["위도", "경도"]].values
        df.loc[i, "PlanB_충전기수"] = idx.loc[nb, "조건충족충전기수"]
        df.loc[i, "PlanB_상태위험축"] = idx.loc[nb, "상태위험축"]
        df.loc[i, "3km이내대체시설수"] = int((dist <= 3).sum())
        df.loc[i, "5km이내대체시설수"] = int((dist <= 5).sum())
        df.loc[i, "절대고립조건"] = "Y" if (dist.min() >= 3 or (dist <= 3).sum() == 0) else "N"
        print(f"{idx.loc[fid, '충전소명']}: Plan B → {idx.loc[nb, '충전소명']} {dist.min():.2f}km, 3km {int((dist <= 3).sum())}곳")
    df.to_csv(PATH, index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
