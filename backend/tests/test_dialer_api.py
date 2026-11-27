"""Regression tests for Dialer Intelligence API (auth, analytics, uploads, settings, memory, recs, chat)."""
import io
import json
import os
import subprocess
import time

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="session")
def token():
    t = subprocess.check_output(["python", "/app/tests/clerk_token.py"], cwd="/app/tests").decode().strip()
    if not t:
        pytest.skip("no token")
    return t


@pytest.fixture(scope="session")
def s(token):
    ss = requests.Session()
    ss.headers.update({"Authorization": f"Bearer {token}"})
    return ss


def make_csv(n=60):
    lines = ["List Name,Call Date,Disposition,Caller ID,Phone Number,Direction,Talk Time"]
    for i in range(n):
        d = ["SALE", "NA", "AM", "NI", "B"][i % 5]
        lines.append(f"TEST_List_Pytest,2026-11-20 {10 + i % 6}:{i % 60:02d}:00,{d},(555) 010-{1000 + i % 3},555300{i:04d},{'Inbound' if i % 7 == 0 else 'Outbound'},00:{i % 60:02d}")
    return "\n".join(lines).encode()


MAPPING = {"list": "List Name", "timestamp": "Call Date", "disposition": "Disposition", "cli": "Caller ID",
           "phone": "Phone Number", "direction": "Direction", "talk_time": "Talk Time", "time": None, "agent": None}


# ---- auth ----
class TestAuth:
    @pytest.mark.parametrize("method,path", [
        ("get", "/analytics"), ("get", "/uploads"), ("post", "/uploads/preview"), ("post", "/uploads/commit"),
        ("post", "/demo/load"), ("delete", "/uploads/x"), ("get", "/settings"), ("put", "/settings"),
        ("get", "/recommendations"), ("get", "/recommendations/status"), ("post", "/recommendations/generate"),
        ("patch", "/recommendations/x"), ("get", "/memory"), ("post", "/memory"), ("patch", "/memory/x"),
        ("delete", "/memory/x"), ("get", "/chat/messages"), ("delete", "/chat/messages"), ("post", "/chat/stream"),
        ("post", "/uploads/dispositions")])
    def test_requires_auth(self, method, path):
        r = getattr(requests, method)(API + path)
        assert r.status_code == 401, f"{method} {path} -> {r.status_code}"

    def test_bad_token(self):
        r = requests.get(API + "/analytics", headers={"Authorization": "Bearer garbage"})
        assert r.status_code == 401

    def test_public(self):
        assert requests.get(API + "/").status_code == 200
        assert requests.get(API + "/clerk/config").status_code == 200


# ---- analytics ----
class TestAnalytics:
    def test_shape(self, s):
        d = s.get(API + "/analytics", params={"days": 14}).json()
        assert d["has_data"] is True
        for k in ("kpis", "lists", "clis", "pairs", "heatmap", "daily", "hourly", "direction"):
            assert k in d, k
        l0 = d["lists"][0]
        for k in ("score", "status", "reasons", "best_times"):
            assert k in l0
        assert l0["status"] in ("Keep", "Watch", "Rest", "Replace")
        assert d["clis"][0]["status"] in ("Keep", "Watch", "Rest", "Replace")
        assert d["kpis"]["dials"] > 1000

    def test_windows_differ(self, s):
        dials = {w: s.get(API + "/analytics", params={"days": w}).json()["kpis"]["dials"] for w in (7, 14, 30, 0)}
        print(dials)
        assert dials[7] < dials[14] <= dials[30] <= dials[0]

    def test_days_invalid(self, s):
        assert s.get(API + "/analytics", params={"days": -1}).status_code == 422


# ---- uploads ----
class TestUploads:
    def test_flow(self, s):
        data = make_csv()
        p = s.post(API + "/uploads/preview", files={"file": ("test_pytest.csv", data, "text/csv")})
        assert p.status_code == 200, p.text
        pv = p.json()
        assert pv["rows"] == 60
        for f in ("list", "timestamp", "disposition", "cli", "phone", "direction", "talk_time"):
            assert pv["mapping"][f] == MAPPING[f], (f, pv["mapping"][f])
        names = {d["name"]: d["category"] for d in pv["dispositions"]}
        assert names.get("SALE") == "sale"
        # missing required mapping
        bad = {**MAPPING, "disposition": None}
        r = s.post(API + "/uploads/commit", files={"file": ("test_pytest.csv", data, "text/csv")},
                   data={"payload": json.dumps({"mapping": bad, "disposition_map": {}})})
        assert r.status_code == 400 and "disposition" in r.json()["detail"]
        # invalid payload
        r = s.post(API + "/uploads/commit", files={"file": ("test_pytest.csv", data, "text/csv")}, data={"payload": "notjson"})
        assert r.status_code == 400
        # bad extension
        r = s.post(API + "/uploads/preview", files={"file": ("x.pdf", b"abc", "application/pdf")})
        assert r.status_code == 400
        ids = []
        try:
            c = s.post(API + "/uploads/commit", files={"file": ("test_pytest.csv", data, "text/csv")},
                       data={"payload": json.dumps({"mapping": MAPPING, "disposition_map": {}})})
            assert c.status_code == 200, c.text
            u = c.json(); ids.append(u["id"])
            assert u["rows_imported"] == 60 and u["duplicates"] == 0
            ups = s.get(API + "/uploads").json()
            assert any(x["id"] == u["id"] for x in ups)
            an = s.get(API + "/analytics", params={"days": 0}).json()
            row = next((x for x in an["lists"] if x["list"] == "TEST_List_Pytest"), None)
            assert row and row["dials"] == 60 and row["sales"] == 12
            # re-upload -> duplicates
            c2 = s.post(API + "/uploads/commit", files={"file": ("test_pytest.csv", data, "text/csv")},
                        data={"payload": json.dumps({"mapping": MAPPING, "disposition_map": {}})})
            u2 = c2.json(); ids.append(u2["id"])
            assert u2["rows_imported"] == 0 and u2["duplicates"] == 60
            # known format on preview
            assert s.post(API + "/uploads/preview", files={"file": ("t.csv", data, "text/csv")}).json()["known_format"] is True
        finally:
            for i in ids:
                assert s.delete(API + f"/uploads/{i}").status_code == 200
        an = s.get(API + "/analytics", params={"days": 0}).json()
        assert not any(x["list"] == "TEST_List_Pytest" for x in an["lists"])
        assert s.delete(API + f"/uploads/{ids[0]}").status_code == 404


# ---- settings ----
class TestSettings:
    def test_save_and_restore(self, s):
        orig = s.get(API + "/settings").json()
        body = {k: orig[k] for k in ("timezone", "min_dials", "cli_drop_pct", "list_drop_pct", "disposition_map", "list_costs")}
        lst = orig["lists"][0]
        try:
            r = s.put(API + "/settings", json={**body, "timezone": "America/Chicago", "list_costs": {lst: 500}})
            assert r.status_code == 200 and r.json()["timezone"] == "America/Chicago"
            an = s.get(API + "/analytics", params={"days": 14}).json()
            row = next(x for x in an["lists"] if x["list"] == lst)
            assert row["cost"] == 500 and (row["cost_per_sale"] is None or row["cost_per_sale"] > 0)
            assert an["timezone"] == "America/Chicago"
            assert s.put(API + "/settings", json={**body, "timezone": "Mars/Base"}).status_code == 400
            assert s.put(API + "/settings", json={**body, "min_dials": 1}).status_code == 422
        finally:
            assert s.put(API + "/settings", json=body).status_code == 200


# ---- memory ----
class TestMemory:
    def test_crud(self, s):
        m = s.post(API + "/memory", json={"type": "note", "text": "TEST_ pytest note"}).json()
        try:
            assert m["active"] is True and m["type"] == "note"
            p = s.patch(API + f"/memory/{m['id']}", json={"text": "TEST_ edited", "active": False}).json()
            assert p["text"] == "TEST_ edited" and p["active"] is False
            got = next(x for x in s.get(API + "/memory").json() if x["id"] == m["id"])
            assert got["active"] is False
            assert s.post(API + "/memory", json={"type": "bogus", "text": "xx"}).status_code == 422
            assert s.patch(API + "/memory/nope", json={"active": True}).status_code == 404
        finally:
            assert s.delete(API + f"/memory/{m['id']}").status_code == 200
        assert s.delete(API + f"/memory/{m['id']}").status_code == 404


# ---- recommendations feedback ----
class TestRecs:
    def test_feedback(self, s):
        recs = s.get(API + "/recommendations").json()
        if not recs:
            pytest.skip("no active recs")
        r = recs[-1]
        before = {x["id"] for x in s.get(API + "/memory").json()}
        try:
            a = s.patch(API + f"/recommendations/{r['id']}", json={"status": "applied"}).json()
            assert a["status"] == "applied" and a["applied_at"]
            f = s.patch(API + f"/recommendations/{r['id']}", json={"status": "failed", "note": "TEST_ flat"}).json()
            assert f["status"] == "failed"
            new = [x for x in s.get(API + "/memory").json() if x["id"] not in before]
            assert any(x["type"] == "learned" and "TEST_ flat" in x["text"] for x in new)
            assert any(x["id"] == r["id"] for x in s.get(API + "/recommendations", params={"status": "failed"}).json())
        finally:
            u = s.patch(API + f"/recommendations/{r['id']}", json={"status": "new"}).json()
            assert u["status"] == "new"
            for x in s.get(API + "/memory").json():
                if x["id"] not in before and x["source"] == "feedback" and "TEST_ flat" in x["text"]:
                    s.delete(API + f"/memory/{x['id']}")
        assert s.patch(API + "/recommendations/nope", json={"status": "applied"}).status_code == 404
        assert s.patch(API + f"/recommendations/{r['id']}", json={"status": "bogus"}).status_code == 422


# ---- chat (real LLM) ----
class TestChat:
    def test_stream_and_remember(self, s):
        before = {x["id"] for x in s.get(API + "/memory").json()}
        r = s.post(API + "/chat/stream", json={"message": "Remember: never dial GA-AutoWarranty-Aged after 6pm"}, stream=True, timeout=180)
        assert r.status_code == 200
        deltas, done = 0, None
        for line in r.iter_lines(decode_unicode=True):
            if line and line.startswith("data: "):
                ev = json.loads(line[6:])
                assert "error" not in ev, ev
                if "delta" in ev:
                    deltas += 1
                if ev.get("done"):
                    done = ev
        assert deltas > 1 and done
        print("memory_saved", done["memory_saved"])
        new = [x for x in s.get(API + "/memory").json() if x["id"] not in before]
        try:
            assert done["memory_saved"] and any(x["type"] == "rule" and x["source"] == "chat" for x in new)
            msgs = s.get(API + "/chat/messages").json()
            assert msgs[-1]["role"] == "assistant" and msgs[-2]["content"].startswith("Remember")
        finally:
            for x in new:
                if x["source"] == "chat":
                    s.delete(API + f"/memory/{x['id']}")
        assert s.post(API + "/chat/stream", json={"message": ""}).status_code == 422
