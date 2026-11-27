"""CDR upload timestamp-style regression (bug: 500 'Mixed timezones detected' on /api/uploads/commit kind=cdr).
SAFE: TEST_ lists, fake phones 78655501xx / CLIs 30555501xx, dates 2026-11-20; deletes only uploads it created."""
import json
import os
import subprocess

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
API = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/") + "/api"
REAL_UPLOAD = "58cbf54b-a15f-40fb-ba4f-38698c7982c4"
CREATED = []
CDR_MAP = {"from": "Source", "to": "Destination", "timestamp": "Start Time", "duration": "Billsec", "call_id": None, "time": None}
CALLS_MAP = {"list": "List Name", "timestamp": "Call Date", "disposition": "Status", "phone": "Phone Number",
             "direction": "Call Type", "talk_time": "Talk Time", "agent": "User", "cli": None, "time": None, "call_id": None}


@pytest.fixture(scope="module")
def s():
    t = subprocess.check_output(["python", "/app/tests/clerk_token.py"], cwd="/app/tests").decode().strip()
    ss = requests.Session()
    ss.headers.update({"Authorization": f"Bearer {t}"})
    return ss


@pytest.fixture(scope="module", autouse=True)
def cleanup(s):
    yield
    for uid in list(CREATED):
        if uid != REAL_UPLOAD:
            s.delete(f"{API}/uploads/{uid}")


def cdr(times, nn="10"):
    rows = ["Start Time,Source,Destination,Billsec"]
    for i, t in enumerate(times):
        rows.append(f"{t},30555501{nn},78655501{(int(nn) + i) % 100:02d},30" if t != "" else ",,,")
    return "\n".join(rows).encode()


def commit(s, data, payload, name="TEST_cdr.csv"):
    r = s.post(f"{API}/uploads/commit", files={"file": (name, data, "text/csv")}, data={"payload": json.dumps(payload)})
    if r.status_code == 200:
        CREATED.append(r.json()["id"])
    return r


def delete(s, uid):
    assert s.delete(f"{API}/uploads/{uid}").status_code == 200
    CREATED.remove(uid)


# (name, timestamps, expected date_from, date_to, expected invalid)
CASES = [
    ("utc_name", ["2026-11-20 10:00:00 UTC", "2026-11-20 11:00:00 UTC"], "2026-11-20T10:00:00", "2026-11-20T11:00:00", 0),
    ("est_name_only", ["2026-11-20 10:00:00 EST", "2026-11-20 11:00:00 EST"], "2026-11-20T15:00:00", "2026-11-20T16:00:00", 0),
    ("est_utc_mixed", ["2026-11-20 10:00:00 EST", "2026-11-20 16:00:00 UTC"], "2026-11-20T15:00:00", "2026-11-20T16:00:00", 0),
    ("iso_mixed_naive", ["2026-11-20T10:00:00-05:00", "2026-11-20T16:00:00+00:00", "2026-11-20T17:00:00Z", "2026-11-20 10:00:00"],
     "2026-11-20T15:00:00", "2026-11-20T17:00:00", 0),
    ("plus0000", ["2026-11-20 15:00:00 +0000", "2026-11-20 10:30:00 -0500", "2026-11-20 10:00:00"], "2026-11-20T15:00:00", "2026-11-20T15:30:00", 0),
    ("us_ampm", ["11/20/2026 10:00 AM", "11/20/2026 03:00 PM"], "2026-11-20T15:00:00", "2026-11-20T20:00:00", 0),
    ("epoch_s", ["1795186800", "1795190400"], "2026-11-20T15:00:00", "2026-11-20T16:00:00", 0),
    ("blank_rows", ["2026-11-20 10:00:00 UTC", "", "2026-11-20 10:00:00"], "2026-11-20T10:00:00", "2026-11-20T15:00:00", 1),
    ("est_and_naive", ["2026-11-20 10:00:00 EST", "2026-11-20 11:00:00"], "2026-11-20T15:00:00", "2026-11-20T16:00:00", 0),
]


class TestCdrTimestamps:
    @pytest.mark.parametrize("name,times,dfrom,dto,invalid", CASES, ids=[c[0] for c in CASES])
    def test_style(self, s, name, times, dfrom, dto, invalid):
        r = commit(s, cdr(times), {"kind": "cdr", "file_tz": "America/New_York", "mapping": CDR_MAP}, f"TEST_{name}.csv")
        assert r.status_code != 500, r.text
        assert r.status_code == 200, r.text
        d = r.json()
        try:
            assert d["invalid"] == invalid, d
            assert (d["date_from"], d["date_to"]) == (dfrom, dto), d
        finally:
            delete(s, d["id"])

    # unparseable dates -> 400 not 500
    def test_garbage_400(self, s):
        r = commit(s, cdr(["not a date", "also bad"]), {"kind": "cdr", "file_tz": "UTC", "mapping": CDR_MAP})
        assert r.status_code == 400, r.text


class TestCliMatchFlow:
    # calls first, then EST CDR -> cli_matched>0; delete CDR resets
    def test_calls_then_cdr_match_and_delete(self, s):
        calls = "\n".join(["Call Date,List Name,Phone Number,Status,Talk Time,Call Type,User",
                           "2026-11-20 10:00:30,TEST_TS_A,7865550150,SALE,60,Outbound,tester",
                           "2026-11-20 10:30:00,TEST_TS_A,7865550151,NA,0,Outbound,tester"]).encode()
        rc = commit(s, calls, {"kind": "calls", "file_tz": "America/New_York", "mapping": CALLS_MAP}, "TEST_calls.csv")
        assert rc.status_code == 200, rc.text
        assert rc.json()["cli_matched"] == 0
        cd = "\n".join(["Start Time,Source,Destination,Billsec",
                        "2026-11-20 10:00:00 EST,3055550177,7865550150,60",   # 30s off -> match
                        "2026-11-20 15:35:00 UTC,3055550178,7865550151,0"]).encode()  # 5 min off -> no match
        rd = commit(s, cd, {"kind": "cdr", "file_tz": "America/New_York", "mapping": CDR_MAP}, "TEST_cdr_match.csv")
        assert rd.status_code == 200, rd.text
        assert rd.json()["cli_matched"] == 1, rd.json()
        a = s.get(f"{API}/analytics", params={"days": 0}).json()
        clis = {c["cli"] for c in a["clis"]}
        assert "3055550177" in clis and "3055550178" not in clis
        delete(s, rd.json()["id"])
        a = s.get(f"{API}/analytics", params={"days": 0}).json()
        assert "3055550177" not in {c["cli"] for c in a["clis"]}
        delete(s, rc.json()["id"])

    # CDR first then calls -> match on calls upload
    def test_cdr_then_calls(self, s):
        cd = "Start Time,Source,Destination,Billsec\n1795186800,3055550179,7865550160,60\n".encode()  # 15:00 UTC
        rd = commit(s, cd, {"kind": "cdr", "file_tz": "America/New_York", "mapping": CDR_MAP}, "TEST_cdr_epoch.csv")
        assert rd.status_code == 200, rd.text
        calls = "Call Date,List Name,Phone Number,Status,Talk Time,Call Type,User\n11/20/2026 10:01 AM,TEST_TS_B,7865550160,SALE,60,Outbound,t\n".encode()
        rc = commit(s, calls, {"kind": "calls", "file_tz": "America/New_York", "mapping": CALLS_MAP}, "TEST_calls2.csv")
        assert rc.status_code == 200, rc.text
        assert rc.json()["cli_matched"] == 1, rc.json()
        delete(s, rc.json()["id"])
        delete(s, rd.json()["id"])

    def test_only_real_upload_remains(self, s):
        ups = s.get(f"{API}/uploads").json()
        assert [u["id"] for u in ups if u["id"] not in CREATED] == [REAL_UPLOAD]
