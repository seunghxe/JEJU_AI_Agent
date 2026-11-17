"""제주데이터허브 연결과 혼잡위험 산출.

API가 실패해도 앱은 동봉된 공공데이터 과거 이력으로 계속 동작한다. 서로 다른
데이터셋의 열 이름 차이를 흡수하기 위해 ID·요일·수치 열을 별칭으로 탐색한다.
"""
from __future__ import annotations

import csv
import hashlib
import tempfile
import json
import math
import os
import re
from threading import Lock
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

BASE_URL = "https://open.jejudatahub.net/api/proxy"
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
LABELS = {"weekly": "요일별 충전 이력", "wait": "일별 대기시간",
          "daily": "일별 충전 이력", "floating": "읍면동 유동인구"}
# Initial historical query windows, not source coverage or guaranteed availability.
WINDOWS = {"weekly": ("202206", "202206"), "daily": ("20220601", "20220607"),
           "wait": ("20220701", "20221031"), "floating": ("20220601", "20220601")}
STATION_ID = ("evChargingStationId", "시설ID", "시설그룹아이디", "충전소ID", "충전소아이디", "stationId", "statId", "facilityId", "chrstnId")
STATION_NAME = ("evChargingStationName", "충전소명", "충전소 이름", "시설명", "stationName", "statNm", "chrstnNm")
CHARGE_COUNT = ("chargingCount", "충전횟수", "이용횟수", "충전건수", "사용량", "count", "cnt", "useCount")
DAY = ("baseDayOfTheWeek", "충전요일", "요일", "요일명", "dayOfWeek", "weekDay", "dow")
DONG = ("emd", "읍면동", "행정동", "읍면동명", "emdNm", "areaName")
VISIT = ("visitPop", "방문자수", "방문인구", "유동인구", "총유동인구", "생활인구", "population", "visitPopulation", "flowPopulation")
WAIT = ("대기시간", "평균대기시간", "대기분", "waitTime", "waitingTime", "avgWait")


class HubIssue(ValueError):
    """Only controlled, display-safe messages (never request URL or body)."""


def _norm(value: Any) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", str(value or "").lower())


def _pick(record: dict[str, Any], *names: str) -> Any:
    lowered = {_norm(k): v for k, v in record.items()}
    for name in names:
        value = lowered.get(_norm(name))
        if value not in (None, ""):
            return value
    return None


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(str(value).replace(",", "").replace("분", "").strip())
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def _weekday(value: Any) -> str | None:
    text = str(value or "").strip()
    for day in WEEKDAYS:
        if text.startswith(day):
            return day
    english = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    if text[:3].lower() in english:
        return WEEKDAYS[english.index(text[:3].lower())]
    # Numeric weekday encodings differ between publishers. Do not guess the base.
    return None


def _wait_observation(row):
    """Duration (minutes) and number of waits. A reported zero count is not missing."""
    raw = _pick(row, "waitingTimeTotal")
    if "waitingTimeTotal" not in row:
        value = _number(_pick(row, *WAIT))
        return (value, 1) if value is not None and 0 <= value <= 360 else (None, None)
    m = re.fullmatch(r"(\d{1,3}):([0-5]\d)(?::([0-5]\d))?", str(raw).strip())
    if not m:
        return None, None
    minutes = int(m[1]) * 60 + int(m[2]) + int(m[3] or 0) / 60
    count = _number(_pick(row, "waitingCount"))
    if count is None or count < 0 or not count.is_integer() or (not count and minutes):
        return minutes, None
    return minutes, int(count)


def _percentiles(values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(values.values())
    if not ordered:
        return {}
    return {key: sum(v <= value for v in ordered) / len(ordered) for key, value in values.items()}


class JejuDataHubClient:
    def __init__(self, fallback_path: str | Path):
        self.mode = os.getenv("JEJU_DATAHUB_MODE", "auto").strip().lower()
        if self.mode not in {"auto", "api", "snapshot"}:
            raise ValueError("JEJU_DATAHUB_MODE must be auto, api, or snapshot")
        self.snapshot_loaded = False
        self.project_key = os.getenv("JEJU_DATAHUB_PROJECT_KEY", "").strip()
        self.base_url = os.getenv("JEJU_DATAHUB_BASE_URL", BASE_URL).rstrip("/")
        self.codes = {
            "weekly": os.getenv("JEJU_DATAHUB_WEEKLY_CHARGE_CODE", "").strip()
                      or os.getenv("JEJU_DATAHUB_CHARGE_DATA_CODE", "").strip(),
            "wait": os.getenv("JEJU_DATAHUB_DAILY_WAIT_CODE", "").strip(),
            "daily": os.getenv("JEJU_DATAHUB_DAILY_CHARGE_CODE", "").strip(),
            "floating": os.getenv("JEJU_DATAHUB_FLOATING_DATA_CODE", "").strip(),
        }
        self.fallback_path = Path(fallback_path)
        self.stations = {}
        self.names = {}
        self.dongs = set()
        self.dong_codes = {}
        catalogue = self.fallback_path.parent.parent / "data" / "stations.csv"
        if catalogue.is_file():
            with catalogue.open(encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    fid = row["시설 ID"].strip()
                    for k in (fid, row["대표충전소 ID"].strip()):
                        if k:
                            self.stations.setdefault(k, set()).add(fid)
                    self.names.setdefault(_norm(row["충전소명"]), set()).add(fid)
                    self.dongs.add(_norm(row["읍면동"]))
                    self.dong_codes[_norm(row["읍면동 코드"])] = _norm(row["읍면동"])
        self.rlock = Lock()
        self.details = {}
        self.history: dict[str, dict[str, Any]] = {}
        self.weekly: dict[str, dict[str, float]] = {}
        self.wait: dict[str, float] = {}
        self.wait_counts = {}
        self.cache_dir = self.fallback_path.parent.parent / ".hub-cache"
        self.catalogue_hash = hashlib.sha256(catalogue.read_bytes()).hexdigest() if catalogue.is_file() else ""
        self.snapshot_path = catalogue.parent / "hub_snapshot.json"
        self.daily_percentile: dict[str, float] = {}
        self.floating_percentile: dict[str, float] = {}
        self.source = "동봉 과거 이력"
        self.errors: dict[str, str] = {}
        self.checked_at: str | None = None
        self.loaded: dict[str, int] = {}
        self._load_fallback()
        if self.mode == "snapshot" or (self.mode == "auto" and not self.configured):
            self._load_snapshot()

    @property
    def configured(self) -> bool:
        return self.mode != "snapshot" and bool(self.project_key and any(self.codes.values()))

    def _load_snapshot(self) -> bool:
        """Validate an explicit portable aggregate, never discover key-derived caches."""
        if not self.snapshot_path.is_file():
            if self.mode == "snapshot":
                self.errors["snapshot"] = "동봉 허브 집계 파일 없음"
            return False
        attrs = {"weekly": ("weekly",), "wait": ("wait", "wait_counts"),
                 "daily": ("daily_percentile",), "floating": ("floating_percentile",)}
        try:
            data = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
            if data.get("schema_version") != 1 or data.get("catalogue_sha256") != self.catalogue_hash or not self.catalogue_hash:
                raise ValueError
            datasets = data["datasets"]
            if not isinstance(datasets, dict) or set(datasets) != set(attrs):
                raise ValueError
            known_ids = {fid for ids in self.stations.values() for fid in ids}
            pending, details, loaded = {}, {}, {}
            def valid_number(v, maximum=None, integer=False):
                return (type(v) in (int, float) and math.isfinite(v) and v >= 0
                        and (maximum is None or v <= maximum) and (not integer or int(v) == v))
            for kind, names in attrs.items():
                saved = datasets[kind]
                detail = saved["details"]
                if detail.get("complete") is not True or not valid_number(detail.get("matched"), integer=True) or not detail["matched"]:
                    raise ValueError
                for name in names:
                    values = saved[name]
                    if not isinstance(values, dict):
                        raise ValueError
                    for key, value in values.items():
                        if key not in (self.dongs if kind == "floating" else known_ids):
                            raise ValueError
                        if name == "weekly":
                            if not isinstance(value, dict) or not value or not set(value) <= set(WEEKDAYS) or not all(valid_number(v) for v in value.values()):
                                raise ValueError
                        elif not valid_number(value, 1 if name.endswith("percentile") else None, name == "wait_counts"):
                            raise ValueError
                    pending[name] = values
                count = len(saved["wait_counts"] if kind == "wait" else saved[names[0]])
                if count != detail["matched"]:
                    raise ValueError
                if kind == "wait" and set(saved["wait"]) != {k for k,n in saved["wait_counts"].items() if n > 0}:
                    raise ValueError
                details[kind] = {**detail, "cached": True, "bundled": True}
                loaded[kind] = count
            for name, values in pending.items():
                setattr(self, name, values)
            self.details, self.loaded = details, loaded
            self.source = "제주데이터허브 저장 집계 + 동봉 과거 이력"
            self.snapshot_loaded = True
            return True
        except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
            self.errors["snapshot"] = "동봉 허브 집계 검증 실패 · 파일/시설 목록 확인"
            return False

    def _load_fallback(self) -> None:
        try:
            payload = json.loads(self.fallback_path.read_text(encoding="utf-8"))
            self.history = payload.get("stations", {})
        except (OSError, ValueError, TypeError):
            self.history = {}

    def _request(self, data_code: str, kind: str) -> list[dict[str, Any]]:
        prefix = "JEJU_DATAHUB_" + kind.upper()
        start, end = [os.getenv(prefix + suffix) or default for suffix, default in
                      zip(("_START", "_END"), WINDOWS[kind])]
        if (not re.fullmatch(r"(?:\d{6}|\d{8})", start) or len(start) != len(end)
                or not end.isdigit() or start > end):
            raise HubIssue("조회 기간 설정 오류 (YYYYMM 또는 YYYYMMDD).")
        fmt = "%Y%m" if len(start) == 6 else "%Y%m%d"
        try:
            for date in (start, end):
                datetime.strptime(date, fmt)
        except ValueError:
            raise HubIssue("조회 기간에 존재하지 않는 날짜가 있습니다.") from None
        info = self.details[kind] = {"start": start, "end": end, "rows": 0, "matched": 0}
        url = f"{self.base_url}/{data_code}/{self.project_key}"
        rows = []
        seen = set()
        for page in range(1, 1001):
            response = requests.get(url, params={"startDate": start, "endDate": end,
                                    "number": page, "limit": 100}, timeout=8, allow_redirects=False)
            if response.status_code != 200:
                raise HubIssue(f"HTTP {int(response.status_code)} · 응답 실패")
            try:
                batch = self._rows(response.json())
            except (ValueError, TypeError):
                raise HubIssue("응답이 예상한 JSON 목록 형식이 아닙니다.") from None
            fingerprint = hashlib.sha256(json.dumps(batch, sort_keys=True).encode()).digest()
            if batch and fingerprint in seen:
                raise HubIssue("동일 페이지 반복 · 미완료 자료는 추천에서 제외")
            seen.add(fingerprint)
            rows.extend(batch)
            info["rows"] = len(rows)
            if len(batch) < 100:
                break
        else:
            raise HubIssue("조회 안전 한도 도달 · 기간을 좁혀 주세요 (미완료 자료 제외)")
        info["complete"] = True
        return rows

    @staticmethod
    def _rows(payload):
        if isinstance(payload, list):
            if all(isinstance(row, dict) for row in payload):
                return payload
            raise ValueError
        if not isinstance(payload, dict):
            raise ValueError
        for key in ("data", "items", "results", "rows", "list", "result", "response", "body"):
            if isinstance(payload.get(key), (list, dict)):
                try:
                    return JejuDataHubClient._rows(payload[key])
                except ValueError:
                    continue
        raise ValueError

    def _station_key(self, record: dict[str, Any]) -> str | None:
        value = _pick(record, *STATION_ID)
        name = _pick(record, *STATION_NAME)
        if self.stations:
            ids = self.stations.get(str(value or "").strip()) or self.names.get(_norm(name), set())
            return next(iter(ids)) if len(ids) == 1 else None
        if value is not None:
            return str(value).strip()
        return "name:" + _norm(name) if name else None

    def _merge_weekly(self, records: list[dict[str, Any]]) -> int:
        bucket: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for record in records:
            key = self._station_key(record)
            day = _weekday(_pick(record, *DAY))
            value = _number(_pick(record, *CHARGE_COUNT))
            if key and day and value is not None:
                bucket[key][day] += max(value, 0)
        self.weekly = {key: dict(value) for key, value in bucket.items()}
        return len(self.weekly)

    def _merge_wait(self, records: list[dict[str, Any]]) -> int:
        sums = defaultdict(float)
        counts = defaultdict(int)
        for record in records:
            key = self._station_key(record)
            value, weight = _wait_observation(record)
            if key and value is not None and weight is not None:
                counts[key] += weight
                sums[key] += value * weight
        self.wait = {k: sums[k] / n for k, n in counts.items() if n}
        self.wait_counts = dict(counts)
        return len(counts)

    def _merge_daily(self, records: list[dict[str, Any]]) -> int:
        bucket: dict[str, list[float]] = defaultdict(list)
        for record in records:
            key = self._station_key(record)
            value = _number(_pick(record, *CHARGE_COUNT))
            if key and value is not None:
                bucket[key].append(max(value, 0))
        means = {key: sum(values) / len(values) for key, values in bucket.items() if values}
        self.daily_percentile = _percentiles(means)
        return len(means)

    def _dong_key(self, record):
        raw = _norm(_pick(record, *DONG))
        key = self.dong_codes.get(raw) or re.sub(r"^(?:제주특별자치도)?(?:제주시|서귀포시)", "", raw)
        return key if key and (not self.dongs or key in self.dongs) else None

    def row_checks(self, kind, row):
        if kind == "floating":
            known, matched = bool(_pick(row, *DONG)), bool(self._dong_key(row))
        else:
            known = any(_pick(row, *fields) is not None for fields in (STATION_ID, STATION_NAME))
            matched = bool(self._station_key(row))
        value = _number(_pick(row, *(VISIT if kind == "floating" else WAIT if kind == "wait" else CHARGE_COUNT)))
        ok = value is not None
        if kind == "wait":
            value, weight = _wait_observation(row)
            ok = weight is not None
        checks = {"식별 필드 인식": known, "시설/지역 일치": matched, "숫자 해석": value is not None}
        if kind == "weekly":
            checks["요일 해석"] = bool(_weekday(_pick(row, *DAY)))
            ok = ok and checks["요일 해석"]
        return {**checks, "조건 동시 충족": matched and ok}

    def _merge_floating(self, records: list[dict[str, Any]]) -> int:
        bucket: dict[str, list[float]] = defaultdict(list)
        for record in records:
            dong = self._dong_key(record)
            value = _number(_pick(record, *VISIT))
            if dong and value is not None:
                bucket[_norm(dong)].append(max(value, 0))
        means = {key: sum(values) / len(values) for key, values in bucket.items() if values}
        self.floating_percentile = _percentiles(means)
        return len(means)

    def _cache_file(self, kind, code):
        fields = ("schema6", self.catalogue_hash, self.base_url, self.project_key, code, kind,
                  *(os.getenv("JEJU_DATAHUB_"+kind.upper()+s) or d for s,d in zip(("_START","_END"), WINDOWS[kind])))
        return self.cache_dir / (hashlib.sha256(json.dumps(fields).encode()).hexdigest()+".json")

    def refresh(self, *, force=False) -> dict[str, Any]:
        if not self.rlock.acquire(blocking=False):
            return self.status()
        try:
            return self._refresh(force)
        finally:
            self.rlock.release()

    def _refresh(self, force=False) -> dict[str, Any]:
        self.checked_at = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M")
        self.errors, self.loaded = {}, {}
        self.details = {}
        self.source = "동봉 과거 이력"
        self.snapshot_loaded = False
        self.weekly, self.wait, self.daily_percentile, self.floating_percentile = {}, {}, {}, {}
        self.wait_counts = {}
        if self.mode == "snapshot" or (self.mode == "auto" and not self.configured):
            self._load_snapshot()
            return self.status()
        if not self.project_key:
            self.errors["project"] = "프로젝트 키 미설정"
            return self.status()
        mergers = {"weekly": self._merge_weekly, "wait": self._merge_wait,
                   "daily": self._merge_daily, "floating": self._merge_floating}
        attrs = {"weekly": ("weekly",), "wait": ("wait","wait_counts"),
                 "daily": ("daily_percentile",), "floating": ("floating_percentile",)}
        for kind, code in self.codes.items():
            if not code:
                continue
            try:
                cache = self._cache_file(kind, code) if self.cache_dir is not None else None
                if cache is not None and not force:
                    try:
                        saved = json.loads(cache.read_text(encoding="utf-8"))
                        detail = saved["details"]
                        if detail["complete"] and detail["matched"] > 0 and all(isinstance(saved[a],dict) for a in attrs[kind]):
                            for a in attrs[kind]:
                                setattr(self, a, saved[a])
                            self.details[kind] = {**detail, "cached": True}
                            self.loaded[kind] = detail["matched"]
                            continue
                    except (ValueError, OSError, KeyError, TypeError):
                        pass
                records = self._request(code, kind)
                if not records:
                    raise HubIssue("수신 0행 · 조회 기간 확인")
                matched = mergers[kind](records)
                checks = [self.row_checks(kind, r) for r in records]
                self.details[kind]["row_checks"] = {k: sum(c[k] for c in checks) for k in checks[0]}
                identifiers = {(str(_pick(r,*DONG) if kind=="floating" else
                                    (_pick(r,*STATION_ID) or _pick(r,*STATION_NAME)) or "").strip()) for r in records}
                self.details[kind]["raw_unique"] = len(identifiers - {"", "None"})
                if not matched:
                    raise HubIssue(f"수신 {len(records)}행 · 필드 또는 시설/지역 매칭 0건")
                self.loaded[kind] = matched
                self.details[kind]["matched"] = matched
                if cache is not None:
                    try:
                        cache.parent.mkdir(exist_ok=True, parents=True)
                        with tempfile.NamedTemporaryFile(dir=cache.parent, mode="w", encoding="utf-8", delete=False) as f:
                            json.dump({"details": self.details[kind], **{a:getattr(self,a) for a in attrs[kind]}}, f)
                        os.replace(f.name, cache)
                    except OSError:
                        self.details[kind]["cache_warning"] = True
            except HubIssue as exc:
                self.errors[kind] = f"{LABELS[kind]}: {exc}"
            except (requests.RequestException, ValueError, TypeError, OverflowError):
                self.errors[kind] = f"{LABELS[kind]}: 통신 또는 응답 처리 오류"
        if self.loaded:
            self.source = "제주데이터허브 API + 동봉 과거 이력"
        return self.status()

    def _find_key(self, facility_id: Any, station_name: Any = None) -> str | None:
        fid = str(facility_id or "").strip()
        for key in (fid, "name:" + _norm(station_name)):
            if key and (key in self.weekly or key in self.wait or key in self.daily_percentile or key in self.history):
                return key
        target = _norm(station_name)
        if len(target) >= 4:
            for key in set(self.weekly) | set(self.wait) | set(self.daily_percentile):
                if key.startswith("name:") and (target in key or key[5:] in target):
                    return key
        return fid or None

    def station_context(self, facility_id: Any, station_name: Any = None, dong: Any = None,
                        hour: int | None = None, weekday: str | None = None) -> dict[str, Any] | None:
        key = self._find_key(facility_id, station_name)
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        day = weekday or WEEKDAYS[now.weekday()]
        scores: list[tuple[float, float]] = []
        evidence: list[str] = []

        weekly = self.weekly.get(key or "")
        if weekly and day in weekly:
            ratio = weekly[day] / max(max(weekly.values()), 1)
            scores.append((ratio, .50))
            evidence.append(f"{day}요일 이용집중도 {round(ratio * 100)}%")
        wait = self.wait.get(key or "")
        if wait is not None:
            scores.append((min(wait / 20, 1), .30))
            evidence.append(f"과거 대기 발생 시 평균 {wait:.1f}분 (시:분 해석)")
        elif self.wait_counts.get(key or "") == 0:
            evidence.append("과거 조사에서 대기 관측 0건")
        daily = self.daily_percentile.get(key or "")
        if daily is not None and (not weekly or day not in weekly):
            scores.append((daily, .35))
            evidence.append(f"일별 이용량 상위 {round((1-daily)*100)}% 수준")
        flow = self.floating_percentile.get(_norm(dong))
        facility_scores = bool(scores)
        if flow is not None:
            scores.append((flow, .20))
            evidence.append(f"{dong} 유동수요 상위 {round((1-flow)*100)}% 수준")

        fallback = self.history.get(str(facility_id))
        if not scores and fallback:
            hours = [int(h) for h in fallback.get("peak_hours", []) if str(h).isdigit()]
            current = now.hour if hour is None else hour
            if current in hours:
                score, text = .85, "과거 충전이 몰린 시간대"
            elif any(abs(current - h) <= 1 for h in hours):
                score, text = .60, "과거 혼잡 시간대에 가까움"
            else:
                score, text = .25, "과거 혼잡 시간대 아님"
            fallback_penalty = 7 if score >= .67 else 3 if score >= .40 else 0
            return {"level": "high" if score >= .67 else "medium" if score >= .40 else "low",
                    "penalty": fallback_penalty, "text": text, "evidence": [text],
                    "peak_hours": hours, "confidence": "참고", "source": "동봉 과거 이력"}
        if not scores:
            return ({"level":"unknown", "penalty":0, "text":"대기 관측 0건", "evidence":evidence,
                     "confidence":"참고", "source":"제주데이터허브"} if evidence else None)

        if flow is not None and not facility_scores:
            return {"level":"unknown", "penalty":0, "text":"지역 방문수요 참고",
                    "evidence":evidence, "confidence":"참고", "source":"제주데이터허브"}

        total_weight = sum(weight for _, weight in scores)
        score = sum(value * weight for value, weight in scores) / max(total_weight, .01)
        level = "high" if score >= .67 else "medium" if score >= .40 else "low"
        label = {"high": "혼잡 위험 높음", "medium": "혼잡 위험 보통", "low": "혼잡 위험 낮음"}[level]
        confidence = "높음" if len(scores) >= 3 else "보통" if len(scores) >= 2 else "참고"
        return {"level": level, "penalty": round(score * 7), "score": round(score * 100),
                "text": label, "evidence": evidence[:3], "confidence": confidence,
                "source": "제주데이터허브"}

    def status(self) -> dict[str, Any]:
        if self.loaded:
            text = ("저장 자료 · " if self.snapshot_loaded else "연결됨 · ") + " / ".join(f"{key} {value:,}건" for key, value in self.loaded.items())
            state = "on" if not self.errors else "ready"
        elif self.errors:
            text = next(iter(self.errors.values()))
            state = "error" if self.configured else "off"
        elif self.configured:
            text, state = "설정됨 · 연결 점검 필요", "ready"
        else:
            text, state = f"미연결 · 동봉 과거 이력 {len(self.history):,}곳", "off"
        return {"state": state, "text": text, "checked_at": self.checked_at,
                "mode": "snapshot" if self.snapshot_loaded else "api" if self.configured else "fallback",
                "fallback_count": len(self.history), "source": self.source,
                "loaded": self.loaded, "errors": self.errors,
                "details": self.details, "configured_datasets": [key for key, code in self.codes.items() if code]}
