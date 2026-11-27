"""Regression tests for CDR upload + CLI matching (preview/commit kind=cdr, matching, rematch, delete reset, settings window).
SAFE: uses TEST_ lists, 786555xxxx phones, 2026-11-26/27 dates; deletes only uploads it created; restores settings."""
import json
import os
import subprocess

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
REAL_UPLOAD = "d1ab25ef-a044-4317-8e6d-22ff07becbdc"
CREATED = []


@pytest.fixture(scope="module")
def s():
    t = subprocess.check_output(["python", "/app/tests/clerk_token.py"], cwd="/app/tests").decode().strip()
    ss = requests.Session()
    ss.headers.update({"Authorization": f"Bearer {t}"})
    return ss


@pytest.fixture(scope="module", autouse=True)
def cleanup(s):
    orig = s.get(f"{API}/settings").json()
    yield
    for uid in CREATED:
        if uid != REAL_UPLOAD:
            s.delete(f"{API}/uploads/{uid}")
    cur = s.get(f"{API}/settings").json()
    if cur["cdr_match_seconds"] != orig["cdr_match_seconds"]:
        put_settings(s, orig, orig["cdr_match_seconds"])


def put_settings(s, base, window):
    body = {k: base[k] for k in ("timezone", "min_dials", "cli_drop_pct", "list_drop_pct", "disposition_map", "list_costs")}
    body["cdr_match_seconds"] = window
    return s.put(f"{API}/settings", json=body)


CALLS_MAP = {"list": "List Name", "timestamp": "Call Date", "disposition": "Status", "phone": "Phone Number",
             "direction": "Call Type", "talk_time": "Talk Time", "agent": "User", "cli": None, "time": None, "call_id": None}
CDR_MAP = {"from": "Source", "to": "Destination", "timestamp": "Start Time", "duration": "Billsec", "call_id": None, "time": None}


def calls_csv(p, day="2026-11-26", lst="TEST_CDR_A", call_ids=None):
    hdr = "Call Date,List Name,Phone Number,Status,Talk Time,Call Type,User" + (",Call ID" if call_ids else "")
    rows = [f"{day} 10:15:00,{lst},(786) 555-{p}01,SALE,750,Outbound,john",
            f"{day} 10:20:00,{lst},786555{p}02,NA,0,Outbound,john",
            f"{day} 11:20:00,{lst},786555{p}03,NI,40,Inbound,amy",
            f"{day} 12:00:00,{lst},786555{p}04,NA,0,Outbound,amy"]
    if call_ids:
        rows = [r + f",{c}" for r, c in zip(rows, call_ids)]
    return "\n".join([hdr] + rows).encode()


def cdr_csv(p, day="2026-11-26", call_ids=None):
    hdr = "Start Time,Source,Destination,Billsec" + (",Call ID" if call_ids else "")
    rows = [f"{day}T15:15:40Z,+1 305-555-{p}42,1786555{p}01,750",      # 40s off, +1 prefix -> CLI 305555{p}42
            f"{day}T15:20:05Z,305555{p}99,786555{p}02,0",              # 5s off -> CLI 305555{p}99
            f"{day}T16:20:30Z,786555{p}03,888555{p}00,40",             # inbound: CLI = DID 888555{p}00
            f"{day}T19:00:00Z,305555{p}42,786555{p}04,0"]              # 2h off -> unmatched
    if call_ids:
        rows = [r + f",{c}" for r, c in zip(rows, call_ids)]
    return "\n".join([hdr] + rows).encode()


def commit(s, data, payload, name="t.csv"):
    r = s.post(f"{API}/uploads/commit", files={"file": (name, data, "text/csv")}, data={"payload": json.dumps(payload)})
    if r.status_code == 200:
        CREATED.append(r.json()["id"])
    return r


def clis(s):
    return {c["cli"]: c["dials"] for c in s.get(f"{API}/analytics", params={"days": 0}).json()["clis"]}


def delete(s, uid):
    r = s.delete(f"{API}/uploads/{uid}")
    assert r.status_code == 200
    CREATED.remove(uid)


class TestCdrCli:
    # preview kind=cdr suggests CDR fields, no dispositions
    def test_preview_cdr(self, s):
        r = s.post(f"{API}/uploads/preview", files={"file": ("c.csv", cdr_csv("01"), "text/csv")}, data={"kind": "cdr"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["kind"] == "cdr"
        assert d["mapping"]["from"] == "Source" and d["mapping"]["to"] == "Destination"
        assert d["mapping"]["timestamp"] == "Start Time" and d["mapping"]["duration"] == "Billsec"
        assert d["dispositions"] == []
        assert "file_tz" in d

    # preview of calls file without CLI column
    def test_preview_calls_no_cli(self, s):
        r = s.post(f"{API}/uploads/preview", files={"file": ("c.csv", calls_csv("01"), "text/csv")}, data={"kind": "calls"})
        assert r.status_code == 200
        assert r.json()["mapping"]["cli"] is None

    # commit validation
    def test_commit_cdr_validation(self, s):
        for m in ({**CDR_MAP, "from": None}, {**CDR_MAP, "to": None}, {**CDR_MAP, "timestamp": None}):
            r = commit(s, cdr_csv("01"), {"kind": "cdr", "file_tz": "UTC", "mapping": m})
            assert r.status_code == 400, r.text
        r = commit(s, cdr_csv("01"), {"kind": "cdr", "file_tz": "Mars/Base", "mapping": CDR_MAP})
        assert r.status_code == 400
        r = commit(s, cdr_csv("01"), {"kind": "bogus", "mapping": CDR_MAP})
        assert r.status_code == 400

    # calls first (no CLI -> Unknown), then CDR in UTC -> 3 matched, then delete CDR resets
    def test_calls_then_cdr_and_delete(self, s):
        rc = commit(s, calls_csv("01"), {"kind": "calls", "file_tz": "America/New_York", "mapping": CALLS_MAP})
        assert rc.status_code == 200, rc.text
        assert rc.json()["clis"] == 0 and rc.json()["cli_matched"] == 0
        assert not any(k.startswith("305555") or k.startswith("888555") for k in clis(s))
        rd = commit(s, cdr_csv("01"), {"kind": "cdr", "file_tz": "UTC", "mapping": CDR_MAP}, "cdr.csv")
        assert rd.status_code == 200, rd.text
        d = rd.json()
        assert d["kind"] == "cdr" and d["cli_matched"] == 3 and d["rows_imported"] == 4
        c = clis(s)
        assert c.get("3055550142") == 1 and c.get("3055550199") == 1 and c.get("8885550100") == 1
        assert "Unknown" not in c
        k = s.get(f"{API}/analytics", params={"days": 0}).json()["kpis"]
        assert k["cli_coverage"] >= 0  # 3/190k rounds to 0.0
        ups = {u["id"]: u for u in s.get(f"{API}/uploads").json()}
        assert ups[d["id"]]["kind"] == "cdr" and ups[d["id"]]["cli_matched"] == 3
        # settings window 10s -> only 5s-off row matches, then restore
        orig = s.get(f"{API}/settings").json()
        assert orig["cdr_rows"] >= 4
        r = put_settings(s, orig, 10)
        assert r.status_code == 200 and r.json()["cdr_match_seconds"] == 10
        c = clis(s)
        assert c.get("3055550199") == 1 and "3055550142" not in c and "8885550100" not in c
        r = put_settings(s, orig, orig["cdr_match_seconds"])
        assert r.status_code == 200 and r.json()["cdr_match_seconds"] == 120
        assert len([x for x in clis(s) if x in ("3055550142", "3055550199", "8885550100")]) == 3
        # rematch endpoint
        r = s.post(f"{API}/cdr/rematch")
        assert r.status_code == 200 and r.json()["matched"] == 3
        # delete CDR -> CLIs back to Unknown
        delete(s, d["id"])
        c = clis(s)
        assert not any(x in c for x in ("3055550142", "3055550199", "8885550100"))
        delete(s, rc.json()["id"])

    # CDR first, then calls upload -> matched on calls commit
    def test_cdr_then_calls(self, s):
        rd = commit(s, cdr_csv("02"), {"kind": "cdr", "file_tz": "UTC", "mapping": CDR_MAP}, "cdr2.csv")
        assert rd.status_code == 200 and rd.json()["cli_matched"] == 0
        rc = commit(s, calls_csv("02", lst="TEST_CDR_B"), {"kind": "calls", "file_tz": "America/New_York", "mapping": CALLS_MAP})
        assert rc.status_code == 200, rc.text
        assert rc.json()["cli_matched"] == 3
        c = clis(s)
        assert c.get("3055550242") == 1 and c.get("8885550200") == 1
        delete(s, rc.json()["id"])
        delete(s, rd.json()["id"])

    # call_id matching: CDR legs with wrong phones/time (1h off, inside +-2h load window) match by id
    def test_call_id_match(self, s):
        cm = {**CALLS_MAP, "call_id": "Call ID"}
        dm = {**CDR_MAP, "call_id": "Call ID"}
        rc = commit(s, calls_csv("03", lst="TEST_CDR_C", call_ids=["TESTCID31", "TESTCID32", "TESTCID33", "TESTCID34"]),
                    {"kind": "calls", "file_tz": "America/New_York", "mapping": cm})
        assert rc.status_code == 200, rc.text
        cdr = ("Start Time,Source,Destination,Billsec,Call ID\n"
               "2026-11-26T16:15:00Z,3055550342,7865559991,10,TESTCID31\n"
               "2026-11-26T17:20:00Z,3055550343,7865559992,10,TESTCID33\n").encode()
        rd = commit(s, cdr, {"kind": "cdr", "file_tz": "UTC", "mapping": dm}, "cdr3.csv")
        assert rd.status_code == 200, rd.text
        assert rd.json()["cli_matched"] == 2, rd.json()
        c = clis(s)
        assert c.get("3055550342") == 1
        assert c.get("7865559992") == 1  # row 3 is inbound -> CLI = CDR destination
        delete(s, rd.json()["id"])
        delete(s, rc.json()["id"])

    # call_id match should not depend on timestamps (e.g. wrong file_tz / CDR a day later) - KNOWN BUG: run_cli_match only loads CDR within +-2h
    def test_call_id_match_far_timestamp(self, s):
        cm = {**CALLS_MAP, "call_id": "Call ID"}
        dm = {**CDR_MAP, "call_id": "Call ID"}
        rc = commit(s, calls_csv("04", lst="TEST_CDR_D", call_ids=["TESTCID41", "TESTCID42", "TESTCID43", "TESTCID44"]),
                    {"kind": "calls", "file_tz": "America/New_York", "mapping": cm})
        assert rc.status_code == 200, rc.text
        cdr = ("Start Time,Source,Destination,Billsec,Call ID\n2026-11-28T15:15:00Z,3055550442,7865550401,10,TESTCID41\n").encode()
        rd = commit(s, cdr, {"kind": "cdr", "file_tz": "UTC", "mapping": dm}, "cdr4.csv")
        assert rd.status_code == 200, rd.text
        matched = rd.json()["cli_matched"]
        delete(s, rd.json()["id"])
        delete(s, rc.json()["id"])
        assert matched == 1, f"call_id match skipped because CDR ts is outside the +-2h load window (matched={matched})"

    # only the real upload remains
    def test_only_real_upload_left(self, s):
        ids = [u["id"] for u in s.get(f"{API}/uploads").json() if u["id"] in CREATED]
        assert ids == []
        assert any(u["id"] == REAL_UPLOAD for u in s.get(f"{API}/uploads").json())
