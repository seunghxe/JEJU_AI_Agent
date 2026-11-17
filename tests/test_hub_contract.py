import json
import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from jejudatahub_client import JejuDataHubClient


class HubContract(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"JEJU_DATAHUB_PROJECT_KEY": "not-a-real-key",
                                      "JEJU_DATAHUB_WEEKLY_CHARGE_CODE": "unit-weekly"}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        self.client = JejuDataHubClient(Path(__file__).resolve().parents[1] / "static/charge_history.json")
        self.client.cache_dir = None
        self.row = {"충전소아이디": "JD110029", "충전요일": "월", "충전횟수": "2"}

    @staticmethod
    def response(payload, status=200):
        return Mock(status_code=status, json=Mock(return_value=payload))

    def test_accepted_fields_and_rank_input(self):
        with patch("jejudatahub_client.requests.get", return_value=self.response({"data":[self.row]})) as get:
            info = self.client.refresh()
        self.assertEqual(get.call_args.kwargs["params"], {"startDate":"202206","endDate":"202206","number":1,"limit":100})
        self.assertEqual(info["loaded"], {"weekly":1})
        ctx = self.client.station_context("F0298", weekday="월")
        self.assertEqual(ctx["source"], "제주데이터허브")
        self.assertGreater(ctx["penalty"], 0)
        self.assertNotEqual((self.client.station_context("F0298", weekday="화") or {}).get("source"), "제주데이터허브")

    def test_failure_erases_old_data_and_hides_key(self):
        with patch("jejudatahub_client.requests.get", return_value=self.response([self.row])):
            self.client.refresh()
        for exc in (self.response(None,500), requests.Timeout("secret-url/not-a-real-key")):
            with patch("jejudatahub_client.requests.get", side_effect=[exc]):
                info = self.client.refresh()
            self.assertEqual(info["loaded"],{})
            self.assertTrue(info["errors"])
            self.assertNotIn("not-a-real-key",json.dumps(info))
            self.assertNotEqual((self.client.station_context("F0298",weekday="월") or {}).get("source"), "제주데이터허브")

    def test_no_false_success(self):
        for payload in ({"data":[]}, {"code":123}, [None], [{"충전소아이디":"unknown","충전요일":"월","충전횟수":1}]):
            with patch("jejudatahub_client.requests.get", return_value=self.response(payload)):
                self.assertFalse(self.client.refresh()["loaded"])

    def test_actual_api_field_names_flow_to_recommendation_input(self):
        self.client.codes.update(wait="wet", daily="day", floating="pop")
        station = {"evChargingStationId": "JD110029", "evChargerId": "unrelated",
                   "evChargingStationName": "other", "chargingCount": "12", "chargingAmount": 999}
        with patch("jejudatahub_client.requests.get", side_effect=[
            self.response([{**station, "baseDayOfTheWeek": "월요일", "baseYearMonth": "202206"}]),
            self.response([]), self.response([{**station, "baseDate": "20220601"}]),
            self.response([{"emd": "애월읍", "resdPop": 999, "visitPop": "20", "workPop": 7}])]):
            status = self.client.refresh()
        self.assertEqual(status["loaded"], {"weekly": 1, "daily": 1, "floating": 1})
        self.assertIn("wait", status["errors"])
        self.assertEqual(self.client.weekly["F0298"]["월"], 12)
        for key in status["loaded"]:
            self.assertEqual(status["details"][key]["row_checks"]["조건 동시 충족"], 1)
        ctx = self.client.station_context("F0298", dong="애월읍", weekday="월")
        self.assertEqual(ctx["source"], "제주데이터허브")
        self.assertEqual(len(ctx["evidence"]), 2)
        self.assertNotIn("대기 ", " ".join(ctx["evidence"]))

    def test_unknowns_not_mapped_to_stations_or_numeric_weekdays(self):
        r = {"evChargerId":"JD110029","id":"JD110029","chargingCount":8,"baseDayOfTheWeek":"월"}
        self.assertFalse(self.client.row_checks("weekly", r)["조건 동시 충족"])
        r.update(evChargingStationName="애월도서관", baseDayOfTheWeek="1")
        self.assertEqual(self.client._station_key(r), "F0785")
        self.assertFalse(self.client.row_checks("weekly",r)["요일 해석"])
        self.assertFalse(self.client.row_checks("floating", {"emd":"미확인", "visitPop":0})["시설/지역 일치"])

    def test_partial_integration(self):
        self.client.codes["floating"] = "unit-floating"
        with patch("jejudatahub_client.requests.get",side_effect=[self.response(None,500),
                   self.response({"data":[{"읍면동":"애월읍","방문자수":20}]})]):
            info = self.client.refresh()
        self.assertEqual(info["loaded"],{"floating":1})
        self.assertIn("500",info["errors"]["weekly"])
        self.assertEqual(self.client.station_context("F0298",dong="애월읍")["source"],"제주데이터허브")

    def test_paging_and_date_override(self):
        with patch.dict(os.environ,{"JEJU_DATAHUB_WEEKLY_START":"202205","JEJU_DATAHUB_WEEKLY_END":"202205"}), patch(
                "jejudatahub_client.requests.get",side_effect=[self.response([self.row]*100), self.response([])]) as get:
            info = self.client.refresh()
        self.assertEqual(get.call_count,2)
        self.assertEqual(get.call_args.kwargs["params"]["startDate"],"202205")
        self.assertEqual(info["details"]["weekly"]["rows"],100)
        self.assertEqual(info["loaded"],{"weekly":1})

    def test_real_wait_schema_and_observed_zero(self):
        def row(duration, count, station="JD110029"):
            return {"evChargingStationId":station,"waitingTimeTotal":duration,"waitingCount":count,
                    "chargingTimeTotal":"00:40","leavingTimeTotal":"00:01"}
        rows = [row("00:02",1), row("00:05",2), row("00:00",0), row("00:00",0,"ME21D111"),
                row("00:70",1), row(None,1), row("00:04",0)]
        self.assertEqual(self.client._merge_wait(rows),2)
        self.assertEqual(self.client.wait,{"F0298":4})
        self.assertEqual(self.client.wait_counts,{"F0298":3,"F0785":0})
        self.assertEqual(sum(self.client.row_checks("wait",r)["조건 동시 충족"] for r in rows),4)
        self.client.history = {}
        self.assertIn("0건", self.client.station_context("F0785")["text"])
        self.assertIsNone(self.client.station_context("unknown"))

    def test_full_pages_cache_and_repeat_guard(self):
        with tempfile.TemporaryDirectory() as d:
            self.client.cache_dir = Path(d)
            batches = [self.response([{**self.row,"id":i}]*100) for i in range(5)] + [self.response([self.row])]
            with patch("jejudatahub_client.requests.get",side_effect=batches):
                info = self.client.refresh()
            self.assertEqual(info["details"]["weekly"]["rows"],501)
            with patch("jejudatahub_client.requests.get") as get:
                self.assertTrue(self.client.refresh()["details"]["weekly"]["cached"])
                get.assert_not_called()
            with patch("jejudatahub_client.requests.get",return_value=batches[0]):
                self.assertFalse(self.client.refresh(force=True)["loaded"])
